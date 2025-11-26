import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

from agent.agent_pr_proposer import AgentPRProposer
from agent.utils import setup_logging

setup_logging()

logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self, token, repo, base_branch, head_branch):
        self.token = token
        self.repo = repo
        self.base_branch = base_branch
        self.head_branch = head_branch
        self.agent = AgentPRProposer(repo, base_branch, head_branch)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Hi! I'm an AI agent. How can I assist you today?")

    async def echo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(chat_id=update.effective_chat.id, text=update.message.text)

    async def propose_pr(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        task_description = update.message.text
        logger.info(f"Received task: {task_description}")
        
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Working on your pull request...")
        
        result = self.agent.propose_pr(task_description)
        
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"PR proposal result: {result}")

    def run(self):
        application = ApplicationBuilder().token(self.token).build()
        
        start_handler = CommandHandler('start', self.start)
        echo_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), self.echo)
        propose_pr_handler = CommandHandler('propose_pr', self.propose_pr)

        application.add_handler(start_handler)
        application.add_handler(echo_handler)
        application.add_handler(propose_pr_handler)
        
        application.run_polling()

if __name__ == '__main__':
    import os
    
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    base_branch = os.environ.get("BASE_BRANCH")
    head_branch = os.environ.get("HEAD_BRANCH")
    
    bot = TelegramBot(token, repo, base_branch, head_branch)
    bot.run()
