"""
Планировщик APScheduler:
- 22:00 ежедневно — вопрос о паре;
- 23:30 ежедневно — итог дня;
- пятница 20:00 — чекап целей;
- воскресенье 20:00 — недельная статистика.
Часовой пояс — Europe/Moscow.
"""
import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

TZ = ZoneInfo("Europe/Moscow")
# Ключ для хранения экземпляра планировщика в application.bot_data
SCHEDULER_KEY = "apscheduler"


def setup_scheduler(application) -> AsyncIOScheduler:
    """Регистрирует и запускает cron-задачи."""
    from handlers import job_day_summary, job_send_pair_question, job_weekly_goals_checkup, send_weekly_stats

    scheduler = AsyncIOScheduler(timezone=TZ)

    async def evening_pair() -> None:
        await job_send_pair_question(application.bot)

    async def night_summary() -> None:
        await job_day_summary(application.bot)

    async def friday_weekly() -> None:
        await job_weekly_goals_checkup(application.bot, application)

    async def sunday_stats() -> None:
        await send_weekly_stats(application.bot)

    scheduler.add_job(evening_pair, "cron", hour=22, minute=0, id="evening_pair", replace_existing=True)
    scheduler.add_job(night_summary, "cron", hour=23, minute=30, id="night_summary", replace_existing=True)
    scheduler.add_job(
        friday_weekly,
        "cron",
        day_of_week="fri",
        hour=20,
        minute=0,
        id="friday_weekly",
        replace_existing=True,
    )
    scheduler.add_job(
        sunday_stats,
        "cron",
        day_of_week="sun",
        hour=20,
        minute=0,
        id="sunday_stats",
        replace_existing=True,
    )
    scheduler.start()
    application.bot_data[SCHEDULER_KEY] = scheduler
    logger.info(
        "APScheduler запущен (Europe/Moscow): 22:00 пары, 23:30 итог дня, пт 20:00 цели, вс 20:00 статистика"
    )
    return scheduler


def shutdown_scheduler(application) -> None:
    """Останавливает планировщик при выключении бота."""
    sched = application.bot_data.get(SCHEDULER_KEY)
    if sched:
        sched.shutdown(wait=False)
        logger.info("APScheduler остановлен")
