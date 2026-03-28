"""
Точка входа: инициализация БД, регистрация хендлеров, планировщик, long polling.
Запуск из каталога bot/:  python main.py
"""
import logging
import sys

from telegram import Update
from telegram.ext import Application

from config import BOT_TOKEN
from database import init_db
from handlers import register_handlers
from scheduler import setup_scheduler, shutdown_scheduler

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(application: Application) -> None:
    """После старта приложения подключаем APScheduler."""
    setup_scheduler(application)


async def post_shutdown(application: Application) -> None:
    """Корректно гасим планировщик."""
    shutdown_scheduler(application)


def main() -> None:
    if not BOT_TOKEN or BOT_TOKEN == "your_token_here":
        logger.error("Задай BOT_TOKEN в файле .env (каталог bot/)")
        sys.exit(1)

    init_db()
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    register_handlers(application)
    logger.info("Бот запущен (polling)")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
