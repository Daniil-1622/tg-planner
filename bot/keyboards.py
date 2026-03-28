"""
Inline-клавиатуры для бота.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from database import Goal, Task


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
    """Кнопки «Выполнено» и «Удалить» для каждой активной цели."""
    rows = []
    for g in goals:
        short = g.title[:25] + ("…" if len(g.title) > 25 else "")
        rows.append(
            [
                InlineKeyboardButton(f"✅ {short}", callback_data=f"goal:done:{g.id}"),
                InlineKeyboardButton(f"🗑 {short}", callback_data=f"goal:del:{g.id}"),
            ]
        )
    return InlineKeyboardMarkup(rows)
