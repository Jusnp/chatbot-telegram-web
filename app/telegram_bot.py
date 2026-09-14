import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from app.services.ai_service import responder_pregunta

load_dotenv()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hola. Soy tu asistente virtual. Envíame una pregunta y trataré de ayudarte."
    )


async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    await update.message.chat.send_action("typing")
    respuesta = await responder_pregunta(update.message.text)
    await update.message.reply_text(respuesta)


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token or token == "pon_aqui_el_token_de_botfather":
        raise RuntimeError("Configura TELEGRAM_BOT_TOKEN en el archivo .env")

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

    print("Bot de Telegram iniciado. Presiona Ctrl+C para detenerlo.")
    app.run_polling()


if __name__ == "__main__":
    main()
