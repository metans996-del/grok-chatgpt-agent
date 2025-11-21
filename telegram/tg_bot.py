from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import os


TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Agent notifier online.")


async def notify_pr(context: ContextTypes.DEFAULT_TYPE, pr_url: str, title: str, summary: str):
    keyboard = [
        [
            InlineKeyboardButton("Approve", callback_data=f"approve|{pr_url}"),
            InlineKeyboardButton("Reject", callback_data=f"reject|{pr_url}")
        ]
    ]
    text = (
        f"*New PR proposed*\n"
        f"{title}\n"
        f"{summary}\n"
        f"{pr_url}"
    )
    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, pr = query.data.split("|", 1)

    if action == "approve":
        await query.edit_message_text(
            text=f"PR approved by {query.from_user.full_name}\n{pr}"
        )
    else:
        await query.edit_message_text(
            text=f"PR rejected by {query.from_user.full_name}\n{pr}"
        )


if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.run_polling()
