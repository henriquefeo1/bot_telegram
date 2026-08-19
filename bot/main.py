"""
Ponto de entrada do serviço. Sobe, no mesmo processo e loop asyncio:

  1. O bot do Telegram (polling)
  2. O servidor webhook (FastAPI/uvicorn) que recebe confirmações de pagamento
  3. O agendador (APScheduler) com as tarefas diárias

Rodar com: python -m bot.main
"""
import asyncio
import logging

import uvicorn
from telegram.ext import Application, CommandHandler

from bot.config import settings, validate_settings
from bot import database as db
from bot import handlers
from bot.scheduler import start_scheduler
from bot.webhook import app as webhook_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("main")


async def main():
    validate_settings()
    db.init_db()

    application = Application.builder().token(settings.BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("assinar", handlers.assinar))
    application.add_handler(CommandHandler("status", handlers.status))
    application.add_handler(CommandHandler("listar", handlers.listar))
    application.add_handler(CommandHandler("add_dias", handlers.add_dias))
    application.add_handler(CommandHandler("remover", handlers.remover))

    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    logger.info("Bot do Telegram iniciado (polling).")

    scheduler = start_scheduler(application.bot)
    logger.info(
        f"Agendador iniciado (checagem às {settings.CHECK_HOUR}h, "
        f"mensagem diária às {settings.DAILY_MESSAGE_HOUR}h, fuso {settings.TIMEZONE})."
    )

    config = uvicorn.Config(
        webhook_app,
        host=settings.WEBHOOK_HOST,
        port=settings.WEBHOOK_PORT,
        log_level="info",
    )
    server = uvicorn.Server(config)
    webhook_task = asyncio.create_task(server.serve())
    logger.info(f"Servidor de webhook escutando em {settings.WEBHOOK_HOST}:{settings.WEBHOOK_PORT}.")

    try:
        await webhook_task
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        logger.info("Encerrando serviço...")
        scheduler.shutdown()
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
