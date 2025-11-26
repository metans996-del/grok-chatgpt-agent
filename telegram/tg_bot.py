import os
import logging
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


def start(update: Update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Hi! I'm a Telegram bot.")


def echo(update: Update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text=update.message.text)


def main():
    updater = Updater(token=os.environ["TELEGRAM_BOT_TOKEN"], use_context=True)
    dispatcher = updater.dispatcher

    start_handler = CommandHandler('start', start)
    echo_handler = MessageHandler(Filters.text & ~Filters.command, echo)

    dispatcher.add_handler(start_handler)
    dispatcher.add_handler(echo_handler)

    updater.start_webhook(listen="0.0.0.0",
                          port=int(os.environ.get('PORT', '8443')),
                          url_path=os.environ["TELEGRAM_BOT_TOKEN"],
                          webhook_url=f"https://{os.environ['HEROKU_APP_NAME']}.herokuapp.com/{os.environ['TELEGRAM_BOT_TOKEN']}")

    updater.idle()


if __name__ == '__main__':
    main()
