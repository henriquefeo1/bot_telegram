"""
Carrega e valida todas as configurações do bot a partir de variáveis de ambiente (.env).
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Telegram
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
    ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

    # Mercado Pago
    MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN")
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "0.0.0.0")
    WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8000"))

    # Regras de assinatura
    SUBSCRIPTION_PRICE = float(os.getenv("SUBSCRIPTION_PRICE", "29.90"))
    SUBSCRIPTION_DAYS = int(os.getenv("SUBSCRIPTION_DAYS", "30"))
    WARNING_DAYS_BEFORE = int(os.getenv("WARNING_DAYS_BEFORE", "3"))

    # Agendamento
    CHECK_HOUR = int(os.getenv("CHECK_HOUR", "9"))
    DAILY_MESSAGE_HOUR = int(os.getenv("DAILY_MESSAGE_HOUR", "12"))
    TIMEZONE = os.getenv("TIMEZONE", "America/Sao_Paulo")

    # Banco de dados
    DATABASE_PATH = os.getenv("DATABASE_PATH", "subscriptions.db")


settings = Settings()


def validate_settings():
    """Garante que as variáveis obrigatórias foram configuradas antes de subir o serviço."""
    missing = []
    if not settings.BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if not settings.CHANNEL_ID:
        missing.append("CHANNEL_ID")
    if not settings.MP_ACCESS_TOKEN:
        missing.append("MP_ACCESS_TOKEN")
    if missing:
        raise RuntimeError(
            f"Variáveis de ambiente obrigatórias faltando: {', '.join(missing)}. "
            f"Confira o arquivo .env (veja .env.example)."
        )
