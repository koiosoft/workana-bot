from telegram import Update

TELEGRAM_MAX_MESSAGE = 4000


async def send_long_message(update: Update, text: str):
    if not update.message:
        return

    current = ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > TELEGRAM_MAX_MESSAGE:
            await update.message.reply_text(current)
            current = line
        else:
            current += line

    if current:
        await update.message.reply_text(current)
