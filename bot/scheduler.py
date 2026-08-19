"""
Tarefas agendadas (rodam sozinhas, sem intervenção manual):

1. check_subscriptions   -> roda 1x/dia: remove do canal quem expirou e avisa quem está perto de vencer
2. send_daily_test_message -> roda 1x/dia: envia "Hello world" no canal (mensagem de teste pedida no projeto)
"""
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot
from telegram.error import TelegramError

from bot import database as db
from bot.config import settings

logger = logging.getLogger("scheduler")


async def check_subscriptions(bot: Bot):
    now = datetime.now()
    users = db.get_all_active_users()
    logger.info(f"Checando {len(users)} assinatura(s) ativa(s)...")

    for user in users:
        telegram_id = user["telegram_id"]
        end = datetime.fromisoformat(user["subscription_end"])

        if end < now:
            # Assinatura expirou -> remove do canal.
            # ban + unban (em vez de apenas ban) evita banimento permanente,
            # permitindo que o usuário volte a entrar após pagar novamente.
            try:
                await bot.ban_chat_member(chat_id=settings.CHANNEL_ID, user_id=telegram_id)
                await bot.unban_chat_member(chat_id=settings.CHANNEL_ID, user_id=telegram_id)
                db.set_user_status(telegram_id, "expired")
                await bot.send_message(
                    telegram_id,
                    "❌ Sua assinatura expirou e você foi removido do canal.\n"
                    "Use /assinar para renovar e voltar a ter acesso.",
                )
                logger.info(f"Usuário {telegram_id} removido por expiração.")
            except TelegramError as e:
                logger.error(f"Erro ao remover {telegram_id} do canal: {e}")

        elif (end - now) <= timedelta(days=settings.WARNING_DAYS_BEFORE) and not user["warned"]:
            # Ainda ativo, mas perto de vencer -> avisa uma única vez.
            try:
                dias_restantes = max((end - now).days, 0)
                await bot.send_message(
                    telegram_id,
                    f"⚠️ Sua assinatura vence em {dias_restantes} dia(s) "
                    f"({end.strftime('%d/%m/%Y')}).\n"
                    "Use /assinar para renovar e não perder o acesso ao canal.",
                )
                db.mark_user_warned(telegram_id)
                logger.info(f"Aviso de expiração enviado para {telegram_id}.")
            except TelegramError as e:
                logger.error(f"Erro ao avisar {telegram_id}: {e}")


async def send_daily_test_message(bot: Bot):
    """Mensagem diária de teste no canal, conforme solicitado no projeto ('Hello world')."""
    try:
        await bot.send_message(chat_id=settings.CHANNEL_ID, text="Hello world")
        logger.info("Mensagem diária de teste enviada ao canal.")
    except TelegramError as e:
        logger.error(f"Erro ao enviar mensagem diária de teste: {e}")


def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.TIMEZONE)

    scheduler.add_job(
        check_subscriptions,
        trigger="cron",
        hour=settings.CHECK_HOUR,
        minute=0,
        args=[bot],
        id="check_subscriptions",
        replace_existing=True,
    )

    scheduler.add_job(
        send_daily_test_message,
        trigger="cron",
        hour=settings.DAILY_MESSAGE_HOUR,
        minute=0,
        args=[bot],
        id="daily_test_message",
        replace_existing=True,
    )

    scheduler.start()
    return scheduler
