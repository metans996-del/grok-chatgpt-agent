import asyncio
import time
import json
import re
import textwrap
import logging
import sys
import os
import httpx
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from github import Github, GithubException, RateLimitExceededException
from typing import List, Dict, Any, Tuple

# ========================= ЗАГРУЗКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ =========================
# load_dotenv()

# ========================= НАСТРОЙКА ЛОГИРОВАНИЯ =========================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),  # Логи в файл
        logging.StreamHandler(sys.stdout)  # Логи в консоль
    ]
)
logger = logging.getLogger(__name__)

# ========================= НАСТРОЙКИ =========================
TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = os.getenv("REPO_NAME")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

# Проверка наличия всех необходимых переменных
required_vars = {
    "TELEGRAM_TOKEN": TOKEN,
    "OPENROUTER_KEY": OPENROUTER_KEY,
    "GITHUB_TOKEN": GITHUB_TOKEN,
    "REPO_NAME": REPO_NAME
}

missing_vars = [key for key, value in required_vars.items() if not value]
if missing_vars:
    logger.critical(f"❌ Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")
    logger.critical("Создайте файл .env с необходимыми переменными или настройте Systemd EnvironmentFile")
    sys.exit(1)

# Цепочка моделей
MODEL_CHAIN = [
    "anthropic/claude-3-opus",
    "openai/gpt-4o",
    "google/gemini-1.5-pro",
    "meta-llama/llama-3.1-405b-instruct",
    "mistral/mistral-large",
]

# ========================= ГЛОБАЛЬНЫЕ СЧЕТЧИКИ И СТАРТОВОЕ ВРЕМЯ =========================
START_TIME = time.time()
PROCESSED_ISSUES_COUNT = 0
BOT_VERSION = "v0.1.0"

# ========================= УТИЛИТЫ ФОРМАТИРОВАНИЯ =========================

def escape_html(text: str) -> str:
    """
    Экранирует специальные символы HTML. Используется для безопасного вывода
    в режиме parse_mode='HTML'.
    """
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


# ========================= GITHUB (АСИНХРОННАЯ ЧАСТЬ) =========================

gh = Github(GITHUB_TOKEN)

async def get_repo_with_wait(name):
    """
    Получает репозиторий с обработкой лимитов GitHub (асинхронная функция).
    """
    while True:
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, gh.get_repo, name)
        except RateLimitExceededException:
            reset = gh.get_rate_limit().core.reset.timestamp()
            wait = max(0, int(reset - time.time()) + 10)
            logger.warning(f"🚨 GitHub Rate Limit исчерпан. Ожидание {wait} сек...")
            await asyncio.sleep(wait)
        except GithubException as e:
            logger.error(f"❌ Ошибка GitHub API: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка при получении репозитория: {e}")
            raise

async def get_repo_files(repo) -> List[str]:
    """
    Получает список всех файлов в репозитории (рекурсивно).
    """
    try:
        loop = asyncio.get_event_loop()
        contents = await loop.run_in_executor(None, repo.get_contents, "")
        files_list = []
        
        while contents:
            file_content = contents.pop(0)
            if file_content.type == "dir":
                contents.extend(await loop.run_in_executor(None, repo.get_contents, file_content.path))
            else:
                files_list.append(file_content.path)
        
        return files_list
    except Exception as e:
        logger.error(f"❌ Ошибка при получении списка файлов: {e}")
        return ["README.md", "LICENSE"]

async def create_branch(repo, base_branch: str, new_branch_name: str):
    """Создает новую ветку на основе базовой."""
    try:
        loop = asyncio.get_event_loop()
        # Получаем объект базовой ветки
        base_branch_ref = await loop.run_in_executor(None, repo.get_git_ref, f"heads/{base_branch}")
        
        # Создаем новую ветку
        new_ref = await loop.run_in_executor(
            None, 
            repo.create_git_ref, 
            f"refs/heads/{new_branch_name}", 
            base_branch_ref.object.sha
        )
        logger.info(f"✅ Ветка {new_branch_name} успешно создана.")
        return new_ref
    except GithubException as e:
        # Если ветка уже существует, это нормально, просто пропускаем
        if e.status == 422 and "Reference already exists" in str(e):
             logger.warning(f"⚠️ Ветка {new_branch_name} уже существует. Продолжаем.")
             return await loop.run_in_executor(None, repo.get_git_ref, f"heads/{new_branch_name}")
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка при создании ветки {new_branch_name}: {e}")
        raise

# ========================= OPENROUTER (АСИНХРОННАЯ ЧАСТЬ) =========================

def parse_model_response(content: str) -> str:
    """
    Надёжно извлекает чистый JSON из ответа модели, удаляя обертки ```json/```.
    """
    content = content.strip()
    
    match = re.search(r"```(?:\w*\s*)?(.*)```", content, re.DOTALL)
    
    if match:
        content = match.group(1).strip()
    
    return content


async def call_openrouter(issue, files_list) -> Tuple[List[Dict[str, Any]], str]:
    """
    Последовательно вызывает модели из MODEL_CHAIN, пока одна из них не вернёт
    валидный и парсируемый JSON.
    """
    if not MODEL_CHAIN:
        raise Exception("❌ Цепочка моделей пуста! Добавьте модели в MODEL_CHAIN.")
    
    prompt = f"""
Ты — автономный ИИ-агент, решающий задачи в репозитории {REPO_NAME}.

Задача:
#{issue.number} {issue.title}
{issue.body or "Нет описания"}

Файлы в репозитории: {', '.join(files_list) or "пусто"}

Верни ТОЛЬКО валидный JSON-массив изменений. ТВОЙ ОТВЕТ ДОЛЖЕН БЫТЬ ТОЛЬКО ЧИСТЫМ JSON, 
БЕЗ ЛЮБЫХ ПОЯСНЕНИЙ, БЕЗ ```json или ```.

Формат:
[
  {{
    "file": "bot.py",
    "action": "create или modify",
    "content": "полный код файла после изменений"
  }}
]
"""
    
    async with httpx.AsyncClient(timeout=180.0) as client:
        for model in MODEL_CHAIN:
            logger.info(f"⏳ Попытка вызова модели: {model}...")
            
            try:
                request_data = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 8000,
                }
                
                if "openai" in model.lower() or "gpt" in model.lower() or "gemini" in model.lower():
                    request_data["response_format"] = {"type": "json_object"}
                
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_KEY}",
                        "Content-Type": "application/json",
                    },
                    json=request_data
                )
                
                resp.raise_for_status() 
                
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                if not content:
                    logger.warning(f"⚠️ Модель {model} вернула **пустой** ответ. Переход к следующей.")
                    continue

                clean_content = parse_model_response(content)
                changes = json.loads(clean_content)
                
                if not isinstance(changes, list):
                    logger.warning(f"⚠️ Модель {model} вернула JSON, но это не массив. Переход к следующей.")
                    continue
                
                logger.info(f"✅ Успешно: Получен валидный ответ от модели **{model}**")
                return changes, model

            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ Модель {model} вернула **невалидный JSON**. Ошибка: {e}")
                logger.debug(f"   Полученный контент (первые 200 символов): {clean_content[:200]}...")
                continue
            except httpx.HTTPStatusError as e:
                error_text = e.response.text[:500] if e.response.text else "нет текста ошибки"
                logger.warning(f"⚠️ Модель {model} вернула HTTP {e.response.status_code}. Текст: {error_text}")
                continue
            except httpx.RequestError as e:
                logger.warning(f"⚠️ Сетевая ошибка при вызове {model}: {e}")
                continue
            except Exception as e:
                logger.error(f"⚠️ Неизвестная ошибка при работе с моделью {model}: {type(e).__name__}: {e}")
                continue

    raise Exception("❌ Все модели в цепочке недоступны или вернули ошибки.")


# ========================= TELEGRAM HANDLERS =========================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    if not update.effective_message:
        return
        
    logger.info(f"Команда /start от пользователя {update.effective_user.id}")
    await update.message.reply_text(
        "🤖 Бот запущен!\n\n"
        "Доступные команды:\n"
        "/start - Запуск бота\n"
        "/runissue &lt;номер&gt; - Запустить задачу GitHub Issue\n" 
        "/test - Тестовый запрос к моделям\n"
        "/status - Показать текущий статус бота\n"
        "/health - Проверка состояния внешних сервисов\n"
        "/models - Список доступных моделей",
        parse_mode='HTML'
    )

async def internal_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показывает внутренний статус бота: время работы, количество обработанных задач и режим.
    """
    if not update.effective_message:
        return
        
    logger.info(f"Команда /status от пользователя {update.effective_user.id}")
    
    # Расчет Uptime
    uptime_seconds = int(time.time() - START_TIME)
    hours = uptime_seconds // 3600
    minutes = (uptime_seconds % 3600) // 60
    
    uptime_str = f"{hours}ч {minutes}мин"
    
    status_text = f"Агент {BOT_VERSION}\n"
    status_text += f"Uptime: {uptime_str}\n"
    status_text += f"Обработано задач: {PROCESSED_ISSUES_COUNT}\n"
    status_text += "Режим: <b>polling (VPS)</b>\n"
    status_text += "Готов к работе ✅"
    
    await update.message.reply_text(
        status_text,
        parse_mode='HTML'
    )

async def run_issue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запускает LLM-агента для решения задачи (Issue) по номеру, коммитит и создает PR."""
    if not update.effective_message:
        return

    logger.info(f"Команда /runissue от пользователя {update.effective_user.id}")
    
    if not context.args:
        await update.message.reply_text("⚠️ Не указан номер задачи. Используйте: <code>/runissue &lt;номер&gt;</code>", parse_mode='HTML')
        return

    try:
        issue_number = int(context.args[0])
    except ValueError:
        await update.message.reply_text("⚠️ Неверный формат номера задачи. Номер должен быть числом.")
        return

    message = await update.message.reply_text(f"⏳ Запускаю выполнение задачи <b>#{issue_number}</b>...", parse_mode='HTML')

    try:
        # 2. Получение репозитория и Issue
        repo = await get_repo_with_wait(REPO_NAME)
        loop = asyncio.get_event_loop()
        issue = await loop.run_in_executor(None, repo.get_issue, issue_number)
        
        if not issue:
            await context.bot.edit_message_text(
                chat_id=message.chat_id,
                message_id=message.message_id,
                text=f"❌ Задача <b>#{issue_number}</b> не найдена в репозитории {REPO_NAME}.",
                parse_mode='HTML'
            )
            return

        # 3. Получение списка файлов
        files_list = await get_repo_files(repo)
        
        # 4. Вызов LLM
        await context.bot.edit_message_text(
            chat_id=message.chat_id,
            message_id=message.message_id,
            text=f"⚙️ Задача <b>#{issue_number}</b> найдена. Передаю в LLM-цепочку...",
            parse_mode='HTML'
        )
        
        changes, model_used = await call_openrouter(issue, files_list)
        
        # --- ЛОГИКА PULL REQUEST ---
        
        base_branch = repo.default_branch
        new_branch_name = f"agent-fix-issue-{issue_number}"
        commit_message = f"Fix: #{issue_number} - {issue.title}"
        
        # A. Создание новой ветки
        await context.bot.edit_message_text(
            chat_id=message.chat_id,
            message_id=message.message_id,
            text=f"⚙️ Создаю ветку <b>{new_branch_name}</b>...",
            parse_mode='HTML'
        )
        await create_branch(repo, base_branch, new_branch_name)
        
        # B. Коммит изменений
        await context.bot.edit_message_text(
            chat_id=message.chat_id,
            message_id=message.message_id,
            text=f"⚙️ Коммичу {len(changes)} изменений в ветку <b>{new_branch_name}</b>...",
            parse_mode='HTML'
        )

        for change in changes:
            file_path = change['file']
            action = change['action']
            content = change['content'] 
            
            try:
                if action == 'create':
                    await loop.run_in_executor(
                        None, 
                        repo.create_file, 
                        file_path, 
                        commit_message, 
                        content, 
                        branch=new_branch_name
                    )
                
                elif action == 'modify':
                    file_info = await loop.run_in_executor(None, repo.get_contents, file_path, ref=base_branch)
                    
                    await loop.run_in_executor(
                        None, 
                        repo.update_file, 
                        file_path, 
                        commit_message, 
                        content, 
                        file_info.sha, 
                        branch=new_branch_name
                    )
                logger.info(f"💾 Файл {file_path} успешно {action} в ветке {new_branch_name}")
                
            except Exception as e:
                error_commit = f"❌ Ошибка коммита: Не удалось изменить файл {file_path}. Проверьте лог."
                logger.error(error_commit, exc_info=True)
                await context.bot.edit_message_text(
                    chat_id=message.chat_id,
                    message_id=message.message_id,
                    text=error_commit,
                    parse_mode='HTML'
                )
                return

        # C. Создание Pull Request
        await context.bot.edit_message_text(
            chat_id=message.chat_id,
            message_id=message.message_id,
            text="🤝 Коммиты готовы. Создаю Pull Request...",
            parse_mode='HTML'
        )
        
        pr_title = f"[Agent] Fix for Issue #{issue_number}: {issue.title}"
        pr_body = f"Автоматически сгенерировано LLM-агентом (<code>{model_used}</code>) для решения задачи #{issue_number}.\n\n{issue.body or ''}"
        
        pull_request = await loop.run_in_executor(
            None,
            repo.create_pull,
            pr_title,
            pr_body,
            base=base_branch,
            head=new_branch_name
        )
        
        # 5. Финальное сообщение
        
        # УВЕЛИЧИВАЕМ СЧЕТЧИК УСПЕШНО ОБРАБОТАННЫХ ЗАДАЧ
        global PROCESSED_ISSUES_COUNT
        PROCESSED_ISSUES_COUNT += 1
        
        result_text = f"✅ Задача <b>#{issue_number}</b> выполнена и интегрирована!\n"
        result_text += f"🤖 Модель: <b>{escape_html(model_used)}</b>\n"
        result_text += f"📝 Коммитов: <b>{len(changes)}</b>\n\n"
        result_text += "<b>Pull Request создан!</b>\n"
        result_text += f"🔗 <a href='{pull_request.html_url}'>Перейти к PR #{pull_request.number}</a>"
        
        await context.bot.edit_message_text(
            chat_id=message.chat_id,
            message_id=message.message_id,
            text=result_text,
            parse_mode='HTML'
        )

    except GithubException as e:
        error_msg_raw = f"❌ Ошибка GitHub API при работе с Issue #{issue_number}: {e.status} - {e.data.get('message', 'Нет сообщения')}"
        error_msg_safe = escape_html(error_msg_raw)
        logger.error(error_msg_raw)
        
        await context.bot.edit_message_text(
            chat_id=message.chat_id, message_id=message.message_id, text=error_msg_safe, parse_mode='HTML'
        )
    except Exception as e:
        error_msg_raw = f"❌ Критическая ошибка при обработке Issue #{issue_number}: {type(e).__name__}: {e}"
        error_msg_safe = escape_html(error_msg_raw)
        logger.error(error_msg_raw, exc_info=True)
        
        await context.bot.edit_message_text(
            chat_id=message.chat_id, message_id=message.message_id, text=error_msg_safe, parse_mode='HTML'
        )
        

async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тестовая команда для проверки работы моделей"""
    logger.info(f"Команда /test от пользователя {update.effective_user.id}")
    await update.message.reply_text("⏳ Запускаю тестовый запрос к моделям...")
    
    class MockIssue:
        number = 1
        title = "Тестовая задача"
        body = "Создай простой файл hello.py с функцией приветствия."
    
    mock_issue = MockIssue()
    mock_files = ["README.md"]
    
    try:
        changes, model_used = await call_openrouter(mock_issue, mock_files)
        
        escaped_model_used = escape_html(model_used)
        
        result_text = f"✅ Успешно!\n\n"
        result_text += f"🤖 Модель: <b>{escaped_model_used}</b>\n"
        result_text += f"📝 Изменений: <b>{len(changes)}</b>\n\n"
        result_text += "<b>Предложенные файлы:</b>\n"
        
        for change in changes:
            file_name = escape_html(change.get('file', 'unknown'))
            action = escape_html(change.get('action', 'unknown'))
            content_len = len(change.get('content', ''))
            result_text += f"• <b>{file_name}</b> ({action}, {content_len} байт)\n"
        
        await update.message.reply_text(result_text, parse_mode='HTML')
        logger.info(f"Тест успешно выполнен с моделью {model_used}")
        
    except Exception as e:
        error_msg_safe = escape_html(f"❌ Ошибка при выполнении теста: {e}")
        logger.error(f"Ошибка при выполнении теста: {e}")
        await update.message.reply_text(error_msg_safe, parse_mode='HTML')


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка статуса подключения к GitHub"""
    logger.info(f"Команда /status от пользователя {update.effective_user.id}")
    await update.message.reply_text("⏳ Проверяю подключение к GitHub...")
    
    try:
        repo = await get_repo_with_wait(REPO_NAME)
        rate_limit = gh.get_rate_limit()
        
        escaped_repo_full_name = escape_html(repo.full_name)
        
        status_text = f"✅ Подключение успешно!\n\n"
        status_text += f"📦 Репозиторий: <b>{escaped_repo_full_name}</b>\n"
        status_text += f"⭐️ Звёзд: {repo.stargazers_count}\n"
        status_text += f"🔀 Форков: {repo.forks_count}\n\n"
        status_text += f"📊 Rate Limit:\n"
        status_text += f"• Осталось: {rate_limit.core.remaining}/{rate_limit.core.limit}\n"
        status_text += f"• Сброс: {rate_limit.core.reset.strftime('%H:%M:%S')}\n"
        
        await update.message.reply_text(status_text, parse_mode='HTML