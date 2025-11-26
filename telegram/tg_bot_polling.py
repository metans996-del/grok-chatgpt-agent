import logging

from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from telegram.tg_bot import start, help_command, handle_message

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    application = ApplicationBuilder().token('YOUR_BOT_TOKEN').build()

    start_handler = CommandHandler('start', start)
    help_handler = CommandHandler('help', help_command)
    message_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)

    application.add_handler(start_handler)
    application.add_handler(help_handler)
    application.add_handler(message_handler)

    application.run_polling()


if __name__ == '__main__':
    main()
