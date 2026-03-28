"""
Конфигурация бота: токен, chat_id и расписание пар.
Расписание — словарь pair_key → данные для карточки (строки для отображения).
"""
import os

from dotenv import load_dotenv

# .env лежит рядом с этим файлом (каталог bot/)
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

BOT_TOKEN = os.getenv("BOT_TOKEN", "")


def _parse_chat_ids() -> list[int]:
    """
    Все чаты для рассылок по расписанию (22:00 / 23:30 / пятница).
    Берётся из CHAT_ID, CHAT_ID_2 (или CHAT_ID2) и при необходимости CHAT_IDS
    (через запятую или точку с запятой). Пустые и дубликаты отбрасываются.
    """
    result: list[int] = []
    seen: set[int] = set()

    def add(cid: int) -> None:
        if cid and cid not in seen:
            seen.add(cid)
            result.append(cid)

    for key in ("CHAT_ID", "CHAT_ID_2", "CHAT_ID2"):
        raw = (os.getenv(key) or "").strip()
        if raw:
            try:
                add(int(raw))
            except ValueError:
                pass

    bulk = (os.getenv("CHAT_IDS") or "").strip()
    if bulk:
        for part in bulk.replace(";", ",").split(","):
            p = part.strip()
            if p:
                try:
                    add(int(p))
                except ValueError:
                    pass

    return result


CHAT_IDS: list[int] = _parse_chat_ids()
# Первый id (если есть) — для мест, где нужно одно значение по умолчанию
CHAT_ID: int = CHAT_IDS[0] if CHAT_IDS else 0

# Путь к SQLite (относительно каталога bot/)
DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")

# Расписание пар: ключи "1", "2", "3", "4", "none" — как в inline-кнопках.
# Заполни под себя реальными временами.
PAR_SCHEDULE = {
    "1": {
        "label": "1-я пара",
        "wake_up": "06:50",  # заполни под себя
        "get_ready": "07:30",
        "trolleybus": "07:40",
        "class_start": "08:30",
    },
    "2": {
        "label": "2-я пара",
        "wake_up": "07:50",
        "get_ready": "08:36",
        "trolleybus": "08:46",
        "class_start": "09:25",
    },
    "3": {
        "label": "3-я пара",
        "wake_up": "08:35",
        "get_ready": "09:24",
        "trolleybus": "09:34",
        "class_start": "10:25",
    },
    "4": {
        "label": "4-я пара",
        "wake_up": "09:30",
        "get_ready": "10:15",
        "trolleybus": "10:25",
        "class_start": "11:05",
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
