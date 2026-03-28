"""
Конфигурация бота: токен, chat_id и расписание пар.
Расписание — словарь pair_key → данные для карточки (строки для отображения).
"""
import os

from dotenv import load_dotenv

# .env лежит рядом с этим файлом (каталог bot/)
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID = int(os.getenv("CHAT_ID", "0") or 0)

# Путь к SQLite (относительно каталога bot/)
DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")

# Расписание пар: ключи "1", "2", "3", "4", "none" — как в inline-кнопках.
# Заполни под себя реальными временами.
PAR_SCHEDULE = {
    "1": {
        "label": "1-я пара",
        "wake_up": "07:00",  # заполни под себя
        "get_ready": "07:30",
        "trolleybus": "07:50",
        "class_start": "08:30",
    },
    "2": {
        "label": "2-я пара",
        "wake_up": "08:00",
        "get_ready": "08:30",
        "trolleybus": "08:50",
        "class_start": "09:30",
    },
    "3": {
        "label": "3-я пара",
        "wake_up": "09:00",
        "get_ready": "09:30",
        "trolleybus": "09:50",
        "class_start": "10:30",
    },
    "4": {
        "label": "4-я пара",
        "wake_up": "10:00",
        "get_ready": "10:30",
        "trolleybus": "10:50",
        "class_start": "11:30",
    },
    "none": {
        "label": "Нет пар",
        "wake_up": "—",
        "get_ready": "—",
        "trolleybus": "—",
        "class_start": "—",
    },
}

MOTIVATION_ALL_DONE = "🔥 Каждый день на 1% лучше. Так держать!"
DAY_SUMMARY_ALL_DONE = MOTIVATION_ALL_DONE
DAY_SUMMARY_INCOMPLETE = "👀 Остались невыполненные задачи за сегодня. Ещё не поздно!"
