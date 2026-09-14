import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from app.services.ai_service import responder_pregunta

load_dotenv()


def _usuarios_permitidos() -> set[int]:
    crudo = os.getenv("TELEGRAM_ALLOWED_IDS", "")
    return {int(x.strip()) for x in crudo.split(",") if x.strip()}


def _autorizado(update: Update) -> bool:
    permitidos = _usuarios_permitidos()
    if not permitidos:
        return False
    return update.effective_user is not None and update.effective_user.id in permitidos


async def _rechazar(update: Update) -> None:
    # La base de conocimiento incluye accesos a plataformas, por eso el bot
    # solo responde a IDs de Telegram en TELEGRAM_ALLOWED_IDS.
    uid = update.effective_user.id if update.effective_user else "desconocido"
    print(f"Acceso rechazado para el usuario de Telegram con ID: {uid}")
    await update.message.reply_text(
        "No tienes autorización para usar este bot. "
        f"Pide al administrador que agregue tu ID de Telegram ({uid}) a TELEGRAM_ALLOWED_IDS."
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _autorizado(update):
        await _rechazar(update)
        return

    await update.message.reply_text(
        "Hola. Soy tu asistente virtual. Envíame una pregunta y trataré de ayudarte."
    )


async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    if not _autorizado(update):
        await _rechazar(update)
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
