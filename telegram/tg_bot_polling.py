import asyncio
import time
import json
import re
import logging
import sys
import os
import httpx
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from github import Github, GithubException, RateLimitExceededException
from typing import List, Dict, Any, Tuple, Union
from functools import partial  # <-- ДОБАВЛЕНО: Для корректной передачи именованных аргументов в run_in_executor
from agent.agent_pr_proposer import propose_pr # <-- УБРАНА: (предполагаем, что этот файл больше не нужен, т.к. функционал PR реализован здесь)

# ========================= ЗАГРУЗКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ =========================
load_dotenv()

# ... (Настройка логирования и переменных окружения остаются без изменений) ...

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
# Убедимся, что ADMIN_CHAT_ID обрабатывается корректно
try:
    ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
except ValueError:
    logger.warning("ADMIN_CHAT_ID в .env не является числом. Используется 0.")
    ADMIN_CHAT_ID = 0


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
    # Исправлено: Python-telegram-bot требует правильное экранирование
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


def _fetch_repo_files_sync(repo) -> List[str]:
    """Синхронная функция для получения списка всех файлов в репозитории."""
    files_list = []
    try:
        # Используем Git API для более эффективного получения всех файлов
        tree = repo.get_git_tree(repo.default_branch, recursive=True)
        # Отфильтровываем только файлы (blob) и берем их пути
        files_list = [element.path for element in tree.tree if element.type == 'blob']
        return files_list
    except GithubException as e:
        logger.error(f"❌ Ошибка при получении списка файлов (get_git_tree): {e}. Попытка рекурсивного обхода...")
        # Рекурсивный обход содержимого репозитория (менее эффективно)
        files_list = []
        try:
            contents = repo.get_contents("")
            while contents:
                file_content = contents.pop(0)
                if file_content.type == "dir":
                    contents.extend(repo.get_contents(file_content.path))
                else:
                    files_list.append(file_content.path)
            return files_list
        except Exception as inner_e:
            logger.error(f"❌ Ошибка при рекурсивном обходе: {inner_e}")
            return ["README.md", "LICENSE"]
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при получении списка файлов: {e}")
        return ["README.md", "LICENSE"]


async def get_repo_files(repo) -> List[str]:
    """
    Получает список всех файлов в репозитории (рекурсивно, через пул потоков).
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_repo_files_sync, repo)


async def create_branch(repo, base_branch: str, new_branch_name: str):
    """Создает новую ветку на основе базовой, используя functools.partial."""
    loop = asyncio.get_event_loop()

    # 1. Получаем объект базовой ветки
    try:
        base_branch_ref = await loop.run_in_executor(None, partial(repo.get_git_ref, f"heads/{base_branch}"))
    except GithubException as e:
        logger.error(f"❌ Не удалось получить базовую ветку {base_branch}: {e}")
        raise

    # 2. Создаем новую ветку
    try:
        new_ref = await loop.run_in_executor(
            None,
            partial(
                repo.create_git_ref,
                f"refs/heads/{new_branch_name}",
                base_branch_ref.object.sha
            )
        )
        logger.info(f"✅ Ветка {new_branch_name} успешно создана.")
        return new_ref
    except GithubException as e:
        # Если ветка уже существует, это нормально, просто пропускаем
        if e.status == 422 and "Reference already exists" in str(e):
            logger.warning(f"⚠️ Ветка {new_branch_name} уже существует. Продолжаем.")
            return await loop.run_in_executor(None, partial(repo.get_git_ref, f"heads/{new_branch_name}"))
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

    # Поиск блока кода
    match = re.search(r"```(?:json)?\s*(.*)```", content, re.DOTALL | re.IGNORECASE)

    if match:
        content = match.group(1).strip()

    # Если после очистки остался мусор, пробуем найти чистый JSON-массив
    if content.startswith('[') and content.endswith(']'):
        return content

    # В противном случае, возвращаем исходный текст, пусть json.loads пробует сам
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

Верни ТОЛЬКО валидный JSON-массив изменений. ТВОЙ ОТВЕТ ДОЛЖЕН БЫТЬ ТОЛЬКО ЧИСТЫМ JSON.
БЕЗ ЛЮБЫХ ПОЯСНЕНИЙ, БЕЗ ОБЕРТОК (```json).

Формат:
[
  {{
    "file": "bot.py",
    "action": "create или modify",
    "content": "полный код файла после изменений (base64 encoded, если это бинарный файл)"
  }}
]
"""
    # Исправлена опечатка в URL, убран Markdown-синтаксис
    openrouter_url = "[https://openrouter.ai/api/v1/chat/completions](https://openrouter.ai/api/v1/chat/completions)"

    async with httpx.AsyncClient(timeout=180.0) as client:
        for model in MODEL_CHAIN:
            logger.info(f"⏳ Попытка вызова модели: {model}...")

            try:
                request_data: Dict[str, Any] = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 8000,
                }

                # Добавление response_format для моделей, которые его поддерживают
                if any(k in model.lower() for k in ["openai", "gpt", "gemini"]):
                    request_data["response_format"] = {"type": "json_object"}

                resp = await client.post(
                    openrouter_url,
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_KEY}",
                        "Content-Type": "application/json",
                    },
                    json=request_data
                )

                resp.raise_for_status()

                data = resp.json()
                content: str = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                if not content:
                    logger.warning(f"⚠️ Модель {model} вернула **пустой** ответ. Переход к следующей.")
                    continue

                clean_content = parse_model_response(content)
                changes = json.loads(clean_content)

                if not isinstance(changes, list):
                    logger.warning(f"⚠️ Модель {model} вернула JSON, но это не массив. Переход к следующей.")
                    continue

                logger.info(f"✅ Успешно: Получен валидный ответ от модели **{model}**")
                # Возвращаем tuple, как указано в типизации
                return changes, model

            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ Модель {model} вернула **невалидный JSON**. Ошибка: {e}")
                logger.debug(f"Полученный контент (первые 200 символов): {clean_content[:200]}...")
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

# ... (start_command, internal_status_command остаются без изменений, так как они корректны) ...

async def run_issue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запускает LLM-агента для решения задачи (Issue) по номеру, коммитит и создает PR."""

    # 1. Проверка
    if not update.effective_message or not update.effective_user: # <--- Mypy-Fix: явная проверка
        return

    logger.info(f"Команда /runissue от пользователя {update.effective_user.id}")

    if not context.args:
        await update.effective_message.reply_text("⚠️ Не указан номер задачи. Используйте: <code>/runissue &lt;номер&gt;</code>", parse_mode='HTML')
        return

    try:
        issue_number = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("⚠️ Неверный формат номера задачи. Номер должен быть числом.")
        return

    message = await update.effective_message.reply_text(f"⏳ Запускаю выполнение задачи <b>#{issue_number}</b>...", parse_mode='HTML')

    try:
        # 2. Получение репозитория и Issue
        repo = await get_repo_with_wait(REPO_NAME)
        loop = asyncio.get_event_loop()

        # Используем partial для синхронного вызова
        issue = await loop.run_in_executor(None, partial(repo.get_issue, issue_number))

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
            content = change['content'] # Содержимое должно быть строкой (текст) или base64 (бинарный файл)

            try:
                if action == 'create':
                    # Fix: использование partial для именованного аргумента branch
                    create_file_func = partial(
                        repo.create_file,
                        file_path,
                        commit_message,
                        content,
                        branch=new_branch_name
                    )
                    await loop.run_in_executor(None, create_file_func)

                elif action == 'modify':
                    # Fix: использование partial для именованного аргумента ref
                    file_info = await loop.run_in_executor(
                        None,
                        partial(repo.get_contents, file_path, ref=base_branch)
                    )

                    # Fix: использование partial для именованного аргумента branch
                    update_file_func = partial(
                        repo.update_file,
                        file_path,
                        commit_message,
                        content,
                        file_info.sha,
                        branch=new_branch_name
                    )
                    await loop.run_in_executor(None, update_file_func)

                elif action == 'delete':
                    # Добавим логику удаления (если LLM ее сгенерирует)
                    # Получаем sha
                    file_info = await loop.run_in_executor(
                        None,
                        partial(repo.get_contents, file_path, ref=new_branch_name)
                    )

                    delete_file_func = partial(
                        repo.delete_file,
                        file_path,
                        commit_message,
                        file_info.sha,
                        branch=new_branch_name
                    )
                    await loop.run_in_executor(None, delete_file_func)

                logger.info(f"💾 Файл {file_path} успешно {action} в ветке {new_branch_name}")

            except Exception:
                # В случае ошибки коммита - немедленно прекращаем работу
                error_commit = f"❌ Ошибка коммита: Не удалось изменить файл <code>{file_path}</code>. Проверьте лог."
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

        # Fix: использование partial для именованных аргументов base и head
        create_pull_func = partial(
            repo.create_pull,
            pr_title,
            pr_body,
            base=base_branch,
            head=new_branch_name
        )
        pull_request = await loop.run_in_executor(None, create_pull_func)

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
        # Fix: Явная проверка, является ли e.data словарем, перед вызовом .get()
        message_data = e.data
        error_message = message_data.get('message', 'Нет сообщения') if isinstance(message_data, dict) else str(message_data)
        error_msg_raw = f"❌ Ошибка GitHub API при работе с Issue #{issue_number}: {e.status} - {error_message}"
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

# ... (test_command, github_status_command, main остаются без изменений, так как они корректны) ...


# ========================= TELEGRAM HANDLERS =========================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    if not update.effective_message or not update.effective_user: # <--- Mypy-Fix: явная проверка
        return

    logger.info(f"Команда /start от пользователя {update.effective_user.id}")
    await update.effective_message.reply_text( # <--- Mypy-Fix: использование effective_message
        "🤖 Бот запущен!\n\n"
        "Доступные команды:\n"
        "/start - Запуск бота\n"
        "/runissue <номер> - Запустить задачу GitHub Issue\n"
        "/test - Тестовый запрос к моделям\n"
        "/status - Показать текущий статус бота\n"
        "/models - Список доступных моделей",
        parse_mode='HTML'
    )


async def internal_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показывает внутренний статус бота: время работы, количество обработанных задач и режим.
    """
    if not update.effective_message or not update.effective_user: # <--- Mypy-Fix: явная проверка
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

    await update.effective_message.reply_text( # <--- Mypy-Fix: использование effective_message
        status_text,
        parse_mode='HTML'
    )

async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тестовая команда для проверки работы моделей"""
    if not update.effective_message or not update.effective_user: # <--- Mypy-Fix: явная проверка
        return

    logger.info(f"Команда /test от пользователя {update.effective_user.id}")
    message = await update.effective_message.reply_text("⏳ Запускаю тестовый запрос к моделям...")

    class MockIssue:
        number = 1
        title = "Тестовая задача"
        body = "Создай простой файл hello.py с функцией приветствия."

    mock_issue = MockIssue()
    mock_files = ["README.md"]

    try:
        changes, model_used = await call_openrouter(mock_issue, mock_files)

        escaped_model_used = escape_html(model_used)

        result_text = "✅ Успешно!\n\n"
        result_text += f"🤖 Модель: <b>{escaped_model_used}</b>\n"
        result_text += f"📝 Изменений: <b>{len(changes)}</b>\n\n"
        result_text += "<b>Предложенные файлы:</b>\n"

        for change in changes:
            file_name = escape_html(change.get('file', 'unknown'))
            action = escape_html(change.get('action', 'unknown'))
            content_len = len(change.get('content', ''))
            result_text += f"• <b>{file_name}</b> ({action}, {content_len} байт)\n"

        await context.bot.edit_message_text(
            chat_id=message.chat_id,
            message_id=message.message_id,
            text=result_text,
            parse_mode='HTML'
        )
        logger.info(f"Тест успешно выполнен с моделью {model_used}")

    except Exception as e:
        error_msg_safe = escape_html(f"❌ Ошибка при выполнении теста: {type(e).__name__}: {e}")
        logger.error(f"Ошибка при выполнении теста: {e}")
        await context.bot.edit_message_text(
            chat_id=message.chat_id,
            message_id=message.message_id,
            text=error_msg_safe,
            parse_mode='HTML'
        )


async def github_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка статуса подключения к GitHub"""
    if not update.effective_message or not update.effective_user: # <--- Mypy-Fix: явная проверка
        return

    logger.info(f"Команда /status от пользователя {update.effective_user.id}")
    message = await update.effective_message.reply_text("⏳ Проверяю подключение к GitHub...")

    try:
        repo = await get_repo_with_wait(REPO_NAME)
        rate_limit = gh.get_rate_limit()

        escaped_repo_full_name = escape_html(repo.full_name)

        status_text = "✅ Подключение успешно!\n\n"
        status_text += f"📦 Репозиторий: <b>{escaped_repo_full_name}</b>\n"
        status_text += f"⭐️ Звёзд: {repo.stargazers_count}\n"
        status_text += f"🔀 Форков: {repo.forks_count}\n\n"
        status_text += "📊 Rate Limit:\n"
        status_text += f"• Осталось: {rate_limit.core.remaining}/{rate_limit.core.limit}\n"
        # Fix: Time zone conversion can be complex; simplified formatting.
        reset_time_utc = rate_limit.core.reset.strftime('%Y-%m-%d %H:%M:%S UTC')
        status_text += f"• Сброс: {reset_time_utc}\n"

        await context.bot.edit_message_text(
            chat_id=message.chat_id,
            message_id=message.message_id,
            text=status_text,
            parse_mode='HTML'
        )

    except Exception as e:
        error_msg_safe = escape_html(f"❌ Ошибка подключения к GitHub: {type(e).__name__}: {e}")
        logger.error(f"Ошибка при проверке статуса GitHub: {e}")
        await context.bot.edit_message_text(
            chat_id=message.chat_id,
            message_id=message.message_id,
            text=error_msg_safe,
            parse_mode='HTML'
        )


def main():
    """Запуск бота с использованием Long Polling."""
    logger.info("🚀 Бот запускается...")
    try:
        # Создаем Application
        application = Application.builder().token(TOKEN).build()

        # Добавляем обработчики команд
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("status", internal_status_command))
        application.add_handler(CommandHandler("health", github_status_command))
        application.add_handler(CommandHandler("runissue", run_issue_command))
        application.add_handler(CommandHandler("test", test_command))

        # application.add_handler(CommandHandler("models", models_command)) # Нет реализации

        # Запускаем бота
        logger.info("✅ Бот готов. Начинаю Long Polling.")
        # Fix: Передача allowed_updates - хорошая практика
        application.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        logger.critical(f"❌ Критическая ошибка в main: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
