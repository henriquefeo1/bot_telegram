"""
Servidor HTTP (FastAPI) que recebe as notificações (IPN) do Mercado Pago quando um
pagamento Pix muda de status. Quando o pagamento é aprovado, o usuário é liberado
automaticamente: a assinatura é estendida e um link de convite de uso único é enviado.

IMPORTANTE (produção): valide a assinatura do webhook (header "x-signature") antes de
confiar no payload. Veja: https://www.mercadopago.com.br/developers/pt/docs/your-integrations/notifications/webhooks
Aqui mantemos a validação simplificada para focar na lógica de negócio do bot.
"""
import logging
from fastapi import FastAPI, Request
from telegram import Bot
from telegram.error import TelegramError

from bot import database as db
from bot.pix import get_payment_status
from bot.config import settings

logger = logging.getLogger("webhook")

app = FastAPI(title="Webhook Pix - Assinaturas do Canal")

_bot = Bot(settings.BOT_TOKEN)


@app.get("/health")
async def health():
    """Endpoint simples para checagem de que o serviço está de pé (útil em Docker/monitoramento)."""
    return {"status": "ok"}


@app.post("/webhook/mercadopago")
async def mercadopago_webhook(request: Request):
    try:
        body = await request.json()
    except Exception:
        return {"status": "invalid_body"}

    logger.info(f"Webhook recebido: {body}")

    payment_id = None
    if body.get("type") == "payment":
        payment_id = body.get("data", {}).get("id")

    # Alguns formatos antigos do MP mandam ?topic=payment&id=... na query string
    if not payment_id:
        payment_id = request.query_params.get("id")

    if not payment_id:
        return {"status": "ignored"}

    try:
        mp_status = get_payment_status(payment_id)
    except Exception:
        logger.exception(f"Erro ao consultar pagamento {payment_id} no Mercado Pago")
        return {"status": "error_checking_payment"}

    if mp_status == "approved":
        await _liberar_acesso(payment_id)

    return {"status": "ok"}


async def _liberar_acesso(payment_id):
    payment = db.get_payment_by_mp_id(payment_id)
    if not payment:
        logger.warning(f"Pagamento {payment_id} aprovado mas não encontrado no banco local.")
        return

    if payment["status"] == "approved":
        return  # já processado antes (evita liberar/duplicar em reenvios do webhook)

    telegram_id = payment["telegram_id"]
    db.update_payment_status(payment_id, "approved")
    new_end = db.extend_subscription(telegram_id, settings.SUBSCRIPTION_DAYS)

    try:
        invite_link = await _bot.create_chat_invite_link(
            chat_id=settings.CHANNEL_ID, member_limit=1
        )
        await _bot.send_message(
            chat_id=telegram_id,
            text=(
                "✅ Pagamento confirmado!\n\n"
                f"Sua assinatura foi ativada até {new_end.strftime('%d/%m/%Y')}.\n\n"
                f"Acesse o canal pelo link (uso único): {invite_link.invite_link}"
            ),
        )
        logger.info(f"Acesso liberado para {telegram_id} até {new_end}.")
    except TelegramError:
        logger.exception(f"Erro ao liberar acesso para {telegram_id}")
