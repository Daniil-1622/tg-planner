"""
Inline- и reply-клавиатуры для бота.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from database import Goal, Task


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню — без ввода команд."""
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📝 Задачи"), KeyboardButton("➕ Задачи сегодня")],
            [KeyboardButton("🎯 Цели"), KeyboardButton("➕ Новая цель")],
            [KeyboardButton("📚 Расписание завтра"), KeyboardButton("ℹ️ Помощь")],
        ],
        resize_keyboard=True,
    )


def cancel_only_keyboard() -> ReplyKeyboardMarkup:
    """Во время ввода списка задач или диалога цели."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton("❌ Отмена")]],
        resize_keyboard=True,
    )


def weekly_pending_keyboard() -> ReplyKeyboardMarkup:
    """Пока ждём ответ на еженедельный чекап по целям."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton("⏭ Пропустить чекап")]],
        resize_keyboard=True,
    )


def pair_selection_keyboard() -> InlineKeyboardMarkup:
    """Кнопки выбора номера пары (и «нет пар»)."""
    rows = [
        [
            InlineKeyboardButton("1-я", callback_data="pair:1"),
            InlineKeyboardButton("2-я", callback_data="pair:2"),
        ],
        [
            InlineKeyboardButton("3-я", callback_data="pair:3"),
            InlineKeyboardButton("4-я", callback_data="pair:4"),
        ],
        [InlineKeyboardButton("Нет пар", callback_data="pair:none")],
    ]
    return InlineKeyboardMarkup(rows)


def tasks_keyboard(tasks: list[Task]) -> InlineKeyboardMarkup:
    """Кнопка «Отметить выполненной» напротив каждой задачи (повторное нажатие снимает отметку)."""
    rows = []
    for t in tasks:
        mark = "✅" if t.done else "⬜"
        label = f"{mark} {t.text[:40]}{'…' if len(t.text) > 40 else ''}"
        rows.append([InlineKeyboardButton(label, callback_data=f"task:toggle:{t.id}")])
    return InlineKeyboardMarkup(rows)


def goals_keyboard(goals: list[Goal]) -> InlineKeyboardMarkup:
    """Кнопки «Журнал», «Выполнено» и «Удалить» для каждой активной цели."""
    rows = []
    for g in goals:
        short = g.title[:28] + ("…" if len(g.title) > 28 else "")
        rows.append([InlineKeyboardButton(f"📖 {short}", callback_data=f"goal:log:{g.id}")])
        rows.append(
            [
                InlineKeyboardButton(f"✅ {short}", callback_data=f"goal:done:{g.id}"),
                InlineKeyboardButton(f"🗑 {short}", callback_data=f"goal:del:{g.id}"),
            ]
        )
    return InlineKeyboardMarkup(rows)
