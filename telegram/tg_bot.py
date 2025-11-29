import logging
import os

import telegram
from telegram.ext import Updater, CommandHandler


logger = logging.getLogger(__name__)


def start(update: telegram.Update, context: telegram.ext.CallbackContext) -> None:
    context.bot.send_message(chat_id=update.effective_chat.id, text='Hello!')


def main() -> None:
    token = os.environ['TELEGRAM_TOKEN']
    updater = Updater(token, use_context=True)
    dispatcher = updater.dispatcher
    start_handler = CommandHandler('start', start)
    dispatcher.add_handler(start_handler)
    updater.start_polling()
    updater.idle()
