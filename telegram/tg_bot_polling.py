import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from agent.agent_pr_proposer import AgentPRProposer

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ALLOWED_USERS = os.getenv('ALLOWED_TELEGRAM_USER_IDS', '').split(',')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")

async def run_issue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) not in ALLOWED_USERS:
        logger.warning(f'Unauthorized access attempt by user {update.effective_user.id}')
        await context.bot.send_message(chat_id=update.effective_chat.id, 
                                       text="You are not authorized to use this bot.")
        return

    if len(context.args) < 1:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Please provide an issue number.")
        return

    issue_number = context.args[0]
    agent = AgentPRProposer()
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Working on issue #{issue_number}...")
    
    try:
        result = await agent.run(issue_number)
        for file_change in result:
            file_path = file_change['file']
            action = file_change['action']
            if action == 'create' or action == 'modify':
                content = file_change['content']
                agent.repo.create_file(file_path, f"Create/modify {file_path}", content, branch=agent.new_branch_name)
            elif action == 'delete':
                sha = agent.repo.get_contents(file_path, ref=agent.new_branch_name).sha
                agent.repo.delete_file(file_path, f"Delete {file_path}", sha, branch=agent.new_branch_name)
            else:
                raise ValueError(f"Unknown action: {action}")

        pr_url = agent.commit_and_create_pr()
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"PR created: {pr_url}")
    except Exception as e:
        logger.exception(e)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"An error occurred: {str(e)}")

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    
    start_handler = CommandHandler('start', start)
    application.add_handler(start_handler)

    issue_handler = CommandHandler('issue', run_issue_command)
    application.add_handler(issue_handler)

    application.run_polling()