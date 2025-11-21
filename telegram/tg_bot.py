from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import os


TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0") or "0")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    await message.reply_text("Agent notifier online.")


async def notify_pr(context: ContextTypes.DEFAULT_TYPE, pr_url: str, title: str, summary: str) -> None:
    keyboard = [
        [
            InlineKeyboardButton("Approve", callback_data=f"approve|{pr_url}"),
            InlineKeyboardButton("Reject", callback_data=f"reject|{pr_url}"),
        ]
    ]
    text = f"*New PR proposed*\n{title}\n\n{summary}\n\n{pr_url}"

    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.data is None:
        return

    await query.answer()

    action, pr_url = query.data.split("|", 1)

    if query.message is None:
        return

    user_name = query.from_user.full_name if query.from_user else "Unknown user"

    if action == "approve":
        await query.edit_message_text(text=f"PR approved by {user_name}\n{pr_url}")
    elif action == "reject":
        await query.edit_message_text(text=f"PR rejected by {user_name}\n{pr_url}")


def main() -> None:
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN is not set in environment variables!")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()
