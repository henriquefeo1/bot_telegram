"""
Comandos do bot: comandos de usuário (/start, /assinar, /status) e
comandos administrativos (/listar, /add_dias, /remover).
"""
import base64
import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from bot import database as db
from bot.pix import create_pix_payment
from bot.config import settings

logger = logging.getLogger("handlers")


# ---------------------------------------------------------------------------
# Comandos de usuário
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.create_user_if_not_exists(user.id, user.username, user.full_name)
    await update.message.reply_text(
        f"Olá, {user.first_name}! 👋\n\n"
        "Este bot gerencia o acesso ao canal privado.\n\n"
        "🔹 /assinar — gerar cobrança Pix e liberar seu acesso\n"
        "🔹 /status — ver sua situação atual"
    )


async def assinar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.create_user_if_not_exists(user.id, user.username, user.full_name)

    await update.message.reply_text("Gerando cobrança Pix, aguarde...")

    try:
        payment = create_pix_payment(
            telegram_id=user.id,
            amount=settings.SUBSCRIPTION_PRICE,
            description=f"Assinatura canal - {settings.SUBSCRIPTION_DAYS} dias",
        )
    except Exception:
        logger.exception("Erro ao criar pagamento Pix")
        await update.message.reply_text(
            "❌ Não foi possível gerar o Pix agora. Tente novamente em instantes."
        )
        return

    db.register_payment(user.id, payment["id"], settings.SUBSCRIPTION_PRICE)

    await update.message.reply_text(
        f"💰 Valor: R$ {settings.SUBSCRIPTION_PRICE:.2f}\n"
        f"📅 Duração: {settings.SUBSCRIPTION_DAYS} dias\n\n"
        "Escaneie o QR Code abaixo ou use o código Pix Copia e Cola:"
    )

    try:
        qr_bytes = base64.b64decode(payment["qr_code_base64"])
        await update.message.reply_photo(photo=qr_bytes, caption="QR Code Pix")
    except Exception:
        logger.exception("Falha ao enviar imagem do QR Code")

    await update.message.reply_text(payment["qr_code"])
    await update.message.reply_text(
        "Assim que o pagamento for identificado, você receberá o link de acesso "
        "ao canal automaticamente aqui, sem precisar fazer mais nada. ✅"
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = db.get_user(user.id)

    if not data or not data.get("subscription_end"):
        await update.message.reply_text(
            "Você ainda não possui assinatura ativa. Use /assinar para começar."
        )
        return

    end = datetime.fromisoformat(data["subscription_end"])
    if end > datetime.now() and data["status"] == "active":
        await update.message.reply_text(
            f"✅ Assinatura ativa até {end.strftime('%d/%m/%Y')}."
        )
    else:
        await update.message.reply_text(
            "❌ Sua assinatura está expirada. Use /assinar para renovar."
        )


# ---------------------------------------------------------------------------
# Comandos administrativos
# ---------------------------------------------------------------------------

def is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS


async def listar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    users = db.get_all_users()
    if not users:
        await update.message.reply_text("Nenhum usuário cadastrado.")
        return

    linhas = [
        f"{u['telegram_id']} (@{u['username']}) — {u['status']} — vence: {u['subscription_end']}"
        for u in users
    ]
    texto = "\n".join(linhas)
    for i in range(0, len(texto), 4000):
        await update.message.reply_text(texto[i:i + 4000])


async def add_dias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Uso: /add_dias <telegram_id> <dias>  — adiciona dias manualmente (ex.: cortesia)."""
    if not is_admin(update.effective_user.id):
        return

    try:
        telegram_id = int(context.args[0])
        dias = int(context.args[1])
    except (IndexError, ValueError):
        await update.message.reply_text("Uso: /add_dias <telegram_id> <dias>")
        return

    new_end = db.extend_subscription(telegram_id, dias)
    await update.message.reply_text(
        f"Assinatura de {telegram_id} estendida até {new_end.strftime('%d/%m/%Y')}."
    )


async def remover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Uso: /remover <telegram_id> — remove manualmente um usuário do canal."""
    if not is_admin(update.effective_user.id):
        return

    try:
        telegram_id = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Uso: /remover <telegram_id>")
        return

    await context.bot.ban_chat_member(chat_id=settings.CHANNEL_ID, user_id=telegram_id)
    await context.bot.unban_chat_member(chat_id=settings.CHANNEL_ID, user_id=telegram_id)
    db.set_user_status(telegram_id, "expired")
    await update.message.reply_text(f"Usuário {telegram_id} removido do canal.")
