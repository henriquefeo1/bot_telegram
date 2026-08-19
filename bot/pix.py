"""
Integração com o Mercado Pago para criar cobranças via Pix e consultar status de pagamento.

Por que Mercado Pago? É o gateway mais simples de integrar Pix via API + webhook no Brasil,
sem precisar de conta bancária PJ com API própria. Se preferir outro provedor (Gerencianet/Efi,
PagSeguro, Asaas, etc.), basta reescrever as duas funções abaixo mantendo a mesma assinatura.
"""
import logging
import mercadopago

from bot.config import settings

logger = logging.getLogger("pix")

sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)


def create_pix_payment(telegram_id: int, amount: float, description: str) -> dict:
    """Cria uma cobrança Pix e retorna os dados necessários para o usuário pagar."""
    payment_data = {
        "transaction_amount": round(float(amount), 2),
        "description": description,
        "payment_method_id": "pix",
        "payer": {
            "email": f"user{telegram_id}@telegrambot.local",
            "first_name": "Assinante",
        },
        "notification_url": settings.WEBHOOK_URL,
        "external_reference": str(telegram_id),
    }

    result = sdk.payment().create(payment_data)
    payment = result["response"]

    if "point_of_interaction" not in payment:
        logger.error(f"Resposta inesperada do Mercado Pago: {payment}")
        raise RuntimeError(payment.get("message", "Falha ao gerar Pix"))

    transaction_data = payment["point_of_interaction"]["transaction_data"]

    return {
        "id": payment["id"],
        "status": payment["status"],
        "qr_code": transaction_data["qr_code"],                 # código "copia e cola"
        "qr_code_base64": transaction_data["qr_code_base64"],   # imagem do QR Code em base64
    }


def get_payment_status(payment_id) -> str:
    """Consulta o status atual de um pagamento no Mercado Pago (pending/approved/rejected...)."""
    result = sdk.payment().get(payment_id)
    return result["response"]["status"]
