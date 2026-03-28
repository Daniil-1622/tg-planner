"""
Обработчики команд, callback-кнопок и текстовых ответов (диалоги).
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session
from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import CHAT_IDS, DAY_SUMMARY_ALL_DONE, DAY_SUMMARY_INCOMPLETE, MOTIVATION_ALL_DONE, PAR_SCHEDULE
from database import Goal, GoalJournalEntry, ScheduleChoice, SessionLocal, Task
from keyboards import (
    cancel_only_keyboard,
    goals_keyboard,
    main_menu_keyboard,
    pair_selection_keyboard,
    tasks_keyboard,
    weekly_pending_keyboard,
)

logger = logging.getLogger(__name__)

MOSCOW = ZoneInfo("Europe/Moscow")

# Ключи user_data
KEY_AWAIT_TASKS_DATE = "awaiting_tasks_date"  # date — на какой день пишем задачи
KEY_MANUAL_ADD = "manual_add_tasks"

# Ключ bot_data: set[int] чатов, ожидающих ответ на еженедельный чекап
BOT_DATA_PENDING_WEEKLY = "pending_weekly_reflection_chats"

# Диалог /addgoal
(GOAL_NAME, GOAL_DEADLINE, GOAL_MOTIVATION) = range(3)

# Тексты кнопок главного меню (reply keyboard)
BTN_TASKS = "📝 Задачи"
BTN_ADD_TASKS = "➕ Задачи сегодня"
BTN_GOALS = "🎯 Цели"
BTN_NEW_GOAL = "➕ Новая цель"
BTN_SCHEDULE = "📚 Расписание завтра"
BTN_HELP = "ℹ️ Помощь"
BTN_CANCEL = "❌ Отмена"
WEEKLY_SKIP_BTN = "⏭ Пропустить чекап"

# «➕ Новая цель» не входит сюда — её обрабатывает ConversationHandler (entry_points).
_MENU_FILTER_LABELS = (BTN_TASKS, BTN_ADD_TASKS, BTN_GOALS, BTN_SCHEDULE, BTN_HELP)
MENU_FILTER = filters.Regex("^(" + "|".join(re.escape(s) for s in _MENU_FILTER_LABELS) + ")$")


def moscow_today() -> date:
    return datetime.now(MOSCOW).date()


def moscow_tomorrow() -> date:
    return moscow_today() + timedelta(days=1)


def reply_keyboard_for_chat(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Главное меню или клавиатура чекапа, если ждём еженедельный ответ."""
    pending = context.application.bot_data.setdefault(BOT_DATA_PENDING_WEEKLY, set())
    if chat_id in pending:
        return weekly_pending_keyboard()
    return main_menu_keyboard()


def format_schedule_card(pair_key: str) -> str:
    """Текст карточки по ключу пары из config.PAR_SCHEDULE (без parse_mode — безопасно для Telegram)."""
    data = PAR_SCHEDULE.get(pair_key, PAR_SCHEDULE["none"])
    return (
        f"📋 {data['label']}\n\n"
        f"⏰ Вставать: {data['wake_up']}\n"
        f"🎒 Начать собираться: {data['get_ready']}\n"
        f"🚎 Троллейбус: {data['trolleybus']}\n"
        f"📖 Пара начинается: {data['class_start']}"
    )


def parse_deadline(text: str) -> tuple[Optional[date], bool]:
    """
    Парсит дедлайн. Возвращает (дата | None для «без дедлайна»), ok.
    ok=False — не распознали, нужно переспросить.
    """
    t = text.strip().lower()
    if t in ("без дедлайна", "без дедлайна.", "-", "нет", "no"):
        return None, True
    raw = text.strip()
    for fmt in ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date(), True
        except ValueError:
            continue
    return None, False


def save_schedule_choice(db: Session, chat_id: int, target_date: date, pair_key: str) -> None:
    row = db.execute(
        select(ScheduleChoice).where(
            ScheduleChoice.chat_id == chat_id,
            ScheduleChoice.target_date == target_date,
        )
    ).scalar_one_or_none()
    if row:
        row.pair_key = pair_key
    else:
        db.add(ScheduleChoice(chat_id=chat_id, target_date=target_date, pair_key=pair_key))
    db.commit()


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    chat_id = update.effective_chat.id
    text = (
        "Привет! Я бот для расписания пар, задач на день и долгосрочных целей.\n\n"
        "Действия — кнопками меню внизу; команды вводить не нужно.\n"
        "Вечером в 22:00 спрошу пару на завтра (МСК), в 23:30 — краткий итог дня."
    )
    await update.message.reply_text(text, reply_markup=reply_keyboard_for_chat(context, chat_id))


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    chat_id = update.effective_chat.id
    text = (
        "Кнопки меню дублируют основные действия.\n"
        "Команды на всякий случай: /tasks /add /goals /addgoal /schedule /goallog название /cancel"
    )
    await update.message.reply_text(text, reply_markup=reply_keyboard_for_chat(context, chat_id))


async def cmd_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    chat_id = update.effective_chat.id
    today = moscow_today()
    with SessionLocal() as db:
        tasks = list(
            db.execute(
                select(Task).where(Task.chat_id == chat_id, Task.task_date == today).order_by(Task.id)
            ).scalars().all()
        )
    if not tasks:
        await update.message.reply_text(
            "На сегодня задач нет. Добавь кнопкой «➕ Задачи сегодня» или ответом на вечерний опрос.",
            reply_markup=reply_keyboard_for_chat(context, chat_id),
        )
        return
    lines = [f"{'✅' if t.done else '⬜'} {t.text}" for t in tasks]
    body = "📝 Задачи на сегодня:\n\n" + "\n".join(lines)
    await update.message.reply_text(
        body,
        reply_markup=tasks_keyboard(tasks),
    )
    if all(t.done for t in tasks):
        await update.message.reply_text(
            MOTIVATION_ALL_DONE,
            reply_markup=reply_keyboard_for_chat(context, chat_id),
        )


async def cmd_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Тот же список, что /tasks — с кнопками для отметки."""
    await cmd_tasks(update, context)


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    context.user_data[KEY_MANUAL_ADD] = True
    await update.message.reply_text(
        "Отправь задачи на сегодня списком — каждая с новой строки. «❌ Отмена» — выход.",
        reply_markup=cancel_only_keyboard(),
    )


async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    chat_id = update.effective_chat.id
    tmr = moscow_tomorrow()
    with SessionLocal() as db:
        row = db.execute(
            select(ScheduleChoice).where(
                ScheduleChoice.chat_id == chat_id,
                ScheduleChoice.target_date == tmr,
            )
        ).scalar_one_or_none()
    if not row:
        await update.message.reply_text(
            "На завтра ещё не выбрана пара. Ответь на вечернее сообщение в 22:00 или дождись напоминания.",
            reply_markup=reply_keyboard_for_chat(context, chat_id),
        )
        return
    card = format_schedule_card(row.pair_key)
    await update.message.reply_text(
        f"📚 Расписание на {tmr.strftime('%d.%m.%Y')} (завтра):\n\n{card}",
        reply_markup=reply_keyboard_for_chat(context, chat_id),
    )


async def cmd_goals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    chat_id = update.effective_chat.id
    today = moscow_today()
    with SessionLocal() as db:
        goals = list(
            db.execute(
                select(Goal)
                .where(Goal.chat_id == chat_id, Goal.completed.is_(False))
                .order_by(Goal.id)
            ).scalars().all()
        )
    if not goals:
        await update.message.reply_text(
            "Активных целей нет. Добавь кнопкой «➕ Новая цель».",
            reply_markup=reply_keyboard_for_chat(context, chat_id),
        )
        return
    parts = []
    for g in goals:
        if g.deadline:
            left = (g.deadline - today).days
            if left >= 0:
                dl = f"до дедлайна: {left} дн."
            else:
                dl = f"дедлайн был {g.deadline.strftime('%d.%m.%Y')} (просрочено)"
        else:
            dl = "без дедлайна"
        parts.append(
            f"🎯 {g.title}\n"
            f"📅 {dl}\n"
            f"💡 Зачем: {g.motivation}\n"
        )
    text = "Твои цели:\n\n" + "\n".join(parts)
    await update.message.reply_text(
        text,
        reply_markup=goals_keyboard(goals),
    )


def _format_goal_journal_lines(goal_title: str, entries: list[GoalJournalEntry]) -> str:
    lines = [
        f"• {e.created_at.strftime('%d.%m.%Y %H:%M')}: {e.content[:200]}{'…' if len(e.content) > 200 else ''}"
        for e in entries[:30]
    ]
    return f"📖 {goal_title} — последние записи:\n\n" + "\n".join(lines)


async def cmd_goallog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    chat_id = update.effective_chat.id
    kb = reply_keyboard_for_chat(context, chat_id)
    if not context.args:
        await update.message.reply_text(
            "Открой «🎯 Цели» и нажми «📖» у нужной цели — или: /goallog точное название",
            reply_markup=kb,
        )
        return
    title_query = " ".join(context.args).strip()
    with SessionLocal() as db:
        goal = db.execute(
            select(Goal).where(Goal.chat_id == chat_id, Goal.title == title_query)
        ).scalar_one_or_none()
        if not goal:
            await update.message.reply_text("Цель с таким точным названием не найдена.", reply_markup=kb)
            return
        goal_title = goal.title
        entries = list(
            db.execute(
                select(GoalJournalEntry)
                .where(GoalJournalEntry.goal_id == goal.id)
                .order_by(GoalJournalEntry.created_at.desc())
            ).scalars().all()
        )
    if not entries:
        await update.message.reply_text(f"По цели «{goal_title}» пока нет записей.", reply_markup=kb)
        return
    await update.message.reply_text(_format_goal_journal_lines(goal_title, entries), reply_markup=kb)


# --- /addgoal: диалог ---


async def addgoal_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message:
        return ConversationHandler.END
    await update.message.reply_text(
        "Как назовём цель? (одним сообщением)\n«❌ Отмена» — выход.",
        reply_markup=cancel_only_keyboard(),
    )
    return GOAL_NAME


async def addgoal_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        return GOAL_NAME
    context.user_data["new_goal_title"] = update.message.text.strip()
    await update.message.reply_text(
        "Дедлайн? Формат ДД.ММ.ГГГГ или ГГГГ-ММ-ДД, либо напиши «без дедлайна».",
        reply_markup=cancel_only_keyboard(),
    )
    return GOAL_DEADLINE


async def addgoal_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        return GOAL_DEADLINE
    d, ok = parse_deadline(update.message.text)
    if not ok:
        await update.message.reply_text(
            "Не понял дату. Повтори в формате ДД.ММ.ГГГГ или напиши «без дедлайна».",
            reply_markup=cancel_only_keyboard(),
        )
        return GOAL_DEADLINE
    context.user_data["new_goal_deadline"] = d
    await update.message.reply_text(
        "Зачем тебе эта цель? (смысл / мотивация — одним сообщением ниже)",
        reply_markup=cancel_only_keyboard(),
    )
    return GOAL_MOTIVATION


async def addgoal_motivation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        return GOAL_MOTIVATION
    title = context.user_data.get("new_goal_title")
    deadline = context.user_data.get("new_goal_deadline")
    motivation = update.message.text.strip()
    chat_id = update.effective_chat.id
    if not title:
        await update.message.reply_text(
            "Сессия сброшена. Начни снова кнопкой «➕ Новая цель».",
            reply_markup=reply_keyboard_for_chat(context, chat_id),
        )
        return ConversationHandler.END
    with SessionLocal() as db:
        db.add(
            Goal(
                chat_id=chat_id,
                title=title,
                deadline=deadline,
                motivation=motivation,
                completed=False,
            )
        )
        db.commit()
    context.user_data.pop("new_goal_title", None)
    context.user_data.pop("new_goal_deadline", None)
    await update.message.reply_text(
        f"Цель «{title}» сохранена.",
        reply_markup=reply_keyboard_for_chat(context, chat_id),
    )
    return ConversationHandler.END


async def addgoal_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    context.user_data.pop("new_goal_title", None)
    context.user_data.pop("new_goal_deadline", None)
    await context.bot.send_message(
        chat_id=chat_id,
        text="Ок, отменено.",
        reply_markup=reply_keyboard_for_chat(context, chat_id),
    )
    return ConversationHandler.END


# --- Callback: пара ---


async def on_pair_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q or not q.data:
        return
    await q.answer()
    if not q.data.startswith("pair:"):
        return
    pair_key = q.data.split(":", 1)[1]
    chat_id = q.message.chat_id if q.message else update.effective_chat.id
    tmr = moscow_tomorrow()
    with SessionLocal() as db:
        save_schedule_choice(db, chat_id, tmr, pair_key)
    card = format_schedule_card(pair_key)
    if q.message:
        await q.message.reply_text(card)
    context.user_data[KEY_AWAIT_TASKS_DATE] = tmr
    if q.message:
        await q.message.reply_text(
            "📝 Какие планы на завтра? Отправь задачи списком (каждая с новой строки). «❌ Отмена» — выход.",
            reply_markup=cancel_only_keyboard(),
        )


# --- Callback: задачи ---


async def on_task_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q or not q.data or not q.data.startswith("task:toggle:"):
        return
    try:
        task_id = int(q.data.split(":")[2])
    except (IndexError, ValueError):
        await q.answer()
        return
    chat_id = q.message.chat_id if q.message else update.effective_chat.id
    today = moscow_today()
    with SessionLocal() as db:
        task = db.get(Task, task_id)
        if not task or task.chat_id != chat_id:
            await q.answer("Задача не найдена", show_alert=True)
            return
        task.done = not task.done
        db.commit()
        tasks = list(
            db.execute(
                select(Task).where(Task.chat_id == chat_id, Task.task_date == today).order_by(Task.id)
            ).scalars().all()
        )
        all_done = tasks and all(t.done for t in tasks)
    await q.answer()
    lines = [f"{'✅' if t.done else '⬜'} {t.text}" for t in tasks]
    body = "📝 Задачи на сегодня:\n\n" + "\n".join(lines)
    try:
        await q.edit_message_text(
            body,
            reply_markup=tasks_keyboard(tasks),
        )
    except Exception as e:
        logger.warning("edit_message_text: %s", e)
    if all_done:
        if q.message:
            await q.message.reply_text(
                MOTIVATION_ALL_DONE,
                reply_markup=reply_keyboard_for_chat(context, chat_id),
            )


# --- Callback: цели ---


async def on_goal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q or not q.data:
        return
    parts = q.data.split(":")
    if len(parts) != 3 or parts[0] != "goal":
        return
    action, sid = parts[1], parts[2]
    try:
        gid = int(sid)
    except ValueError:
        await q.answer()
        return
    chat_id = q.message.chat_id if q.message else update.effective_chat.id

    if action == "log":
        with SessionLocal() as db:
            goal = db.get(Goal, gid)
            if not goal or goal.chat_id != chat_id:
                await q.answer("Цель не найдена", show_alert=True)
                return
            goal_title = goal.title
            entries = list(
                db.execute(
                    select(GoalJournalEntry)
                    .where(GoalJournalEntry.goal_id == goal.id)
                    .order_by(GoalJournalEntry.created_at.desc())
                ).scalars().all()
            )
        await q.answer()
        kb = reply_keyboard_for_chat(context, chat_id)
        if q.message:
            if not entries:
                await q.message.reply_text(f"По цели «{goal_title}» пока нет записей.", reply_markup=kb)
            else:
                await q.message.reply_text(_format_goal_journal_lines(goal_title, entries), reply_markup=kb)
        return

    with SessionLocal() as db:
        goal = db.get(Goal, gid)
        if not goal or goal.chat_id != chat_id:
            await q.answer("Цель не найдена", show_alert=True)
            return
        if action == "done":
            goal.completed = True
            tip = "Отмечено выполненной"
        elif action == "del":
            db.delete(goal)
            tip = "Удалено"
        else:
            await q.answer()
            return
        db.commit()
        goals = list(
            db.execute(
                select(Goal)
                .where(Goal.chat_id == chat_id, Goal.completed.is_(False))
                .order_by(Goal.id)
            ).scalars().all()
        )
    await q.answer(tip)
    if not goals:
        if q.message:
            try:
                await q.edit_message_text(
                    "Активных целей больше нет.",
                    reply_markup=None,
                )
            except Exception:
                pass
            try:
                await q.message.reply_text(
                    "Ок.",
                    reply_markup=reply_keyboard_for_chat(context, chat_id),
                )
            except Exception as e:
                logger.warning("goal callback reply menu: %s", e)
        return
    today = moscow_today()
    parts_lines = []
    for g in goals:
        if g.deadline:
            left = (g.deadline - today).days
            dl = f"до дедлайна: {left} дн." if left >= 0 else f"дедлайн {g.deadline.strftime('%d.%m.%Y')}"
        else:
            dl = "без дедлайна"
        parts_lines.append(f"🎯 {g.title}\n📅 {dl}\n💡 Зачем: {g.motivation}\n")
    text = "Твои цели:\n\n" + "\n".join(parts_lines)
    try:
        await q.edit_message_text(
            text,
            reply_markup=goals_keyboard(goals),
        )
    except Exception as e:
        logger.warning("goal callback edit: %s", e)


# --- Текстовые ответы (задачи на завтра, ручной /add, пятничный чекап) ---


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    text = update.message.text
    chat_id = update.effective_chat.id

    # Еженедельный отчёт (после пятничного сообщения)
    pending = context.application.bot_data.setdefault(BOT_DATA_PENDING_WEEKLY, set())
    if chat_id in pending:
        if text.strip() == WEEKLY_SKIP_BTN:
            pending.discard(chat_id)
            await update.message.reply_text(
                "Ок, чекап пропущен.",
                reply_markup=main_menu_keyboard(),
            )
            return
        if text.strip() == BTN_CANCEL:
            pending.discard(chat_id)
            await update.message.reply_text(
                "Ок, чекап отменён.",
                reply_markup=main_menu_keyboard(),
            )
            return
        pending.discard(chat_id)
        with SessionLocal() as db:
            goals = list(
                db.execute(
                    select(Goal).where(Goal.chat_id == chat_id, Goal.completed.is_(False))
                ).scalars().all()
            )
            if not goals:
                await update.message.reply_text(
                    "Активных целей нет — отчёт некуда сохранить.",
                    reply_markup=main_menu_keyboard(),
                )
                return
            for g in goals:
                db.add(GoalJournalEntry(goal_id=g.id, content=text.strip()))
            db.commit()
        await update.message.reply_text(
            "Записал отчёт ко всем активным целям.",
            reply_markup=main_menu_keyboard(),
        )
        return

    if text.strip() == BTN_CANCEL:
        if context.user_data.get(KEY_MANUAL_ADD):
            context.user_data[KEY_MANUAL_ADD] = False
            await update.message.reply_text(
                "Ок.",
                reply_markup=reply_keyboard_for_chat(context, chat_id),
            )
            return
        if KEY_AWAIT_TASKS_DATE in context.user_data:
            context.user_data.pop(KEY_AWAIT_TASKS_DATE, None)
            await update.message.reply_text(
                "Ок, ввод задач на завтра отменён.",
                reply_markup=reply_keyboard_for_chat(context, chat_id),
            )
            return

    # Задачи на завтра после выбора пары
    dkey = context.user_data.get(KEY_AWAIT_TASKS_DATE)
    if dkey is not None:
        context.user_data.pop(KEY_AWAIT_TASKS_DATE, None)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            await update.message.reply_text(
                "Список пуст — напиши хотя бы одну задачу.",
                reply_markup=cancel_only_keyboard(),
            )
            context.user_data[KEY_AWAIT_TASKS_DATE] = dkey
            return
        with SessionLocal() as db:
            for ln in lines[:50]:
                db.add(Task(chat_id=chat_id, task_date=dkey, text=ln[:500], done=False))
            db.commit()
        await update.message.reply_text(
            f"Сохранено задач на {dkey.strftime('%d.%m.%Y')}: {len(lines)}.",
            reply_markup=reply_keyboard_for_chat(context, chat_id),
        )
        return

    # Кнопка «➕ Задачи сегодня» — задачи на сегодня
    if context.user_data.get(KEY_MANUAL_ADD):
        context.user_data[KEY_MANUAL_ADD] = False
        today = moscow_today()
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            await update.message.reply_text(
                "Пусто. Нажми «➕ Задачи сегодня» снова и пришли список.",
                reply_markup=reply_keyboard_for_chat(context, chat_id),
            )
            return
        with SessionLocal() as db:
            for ln in lines[:50]:
                db.add(Task(chat_id=chat_id, task_date=today, text=ln[:500], done=False))
            db.commit()
        await update.message.reply_text(
            f"Добавлено задач на сегодня: {len(lines)}.",
            reply_markup=reply_keyboard_for_chat(context, chat_id),
        )
        return


async def on_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Те же действия, что команды — по нажатию кнопок reply keyboard."""
    if not update.message:
        return
    chat_id = update.effective_chat.id
    pending = context.application.bot_data.setdefault(BOT_DATA_PENDING_WEEKLY, set())
    if chat_id in pending:
        await update.message.reply_text(
            "Сначала еженедельный чекап: ответь одним сообщением или нажми «⏭ Пропустить чекап».",
            reply_markup=weekly_pending_keyboard(),
        )
        return
    label = update.message.text.strip()
    if label == BTN_TASKS:
        await cmd_tasks(update, context)
    elif label == BTN_ADD_TASKS:
        await cmd_add(update, context)
    elif label == BTN_GOALS:
        await cmd_goals(update, context)
    elif label == BTN_SCHEDULE:
        await cmd_schedule(update, context)
    elif label == BTN_HELP:
        await cmd_help(update, context)


def build_conversation_addgoal() -> ConversationHandler:
    cancel_filter = filters.Regex(f"^{re.escape(BTN_CANCEL)}$")
    return ConversationHandler(
        entry_points=[
            CommandHandler("addgoal", addgoal_start),
            MessageHandler(filters.Regex(f"^{re.escape(BTN_NEW_GOAL)}$"), addgoal_start),
        ],
        states={
            GOAL_NAME: [
                MessageHandler(cancel_filter, addgoal_cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, addgoal_name),
            ],
            GOAL_DEADLINE: [
                MessageHandler(cancel_filter, addgoal_cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, addgoal_deadline),
            ],
            GOAL_MOTIVATION: [
                MessageHandler(cancel_filter, addgoal_cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, addgoal_motivation),
            ],
        },
        fallbacks=[CommandHandler("cancel", addgoal_cancel)],
        name="addgoal",
        persistent=False,
    )


def register_handlers(application) -> None:
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("tasks", cmd_tasks))
    application.add_handler(CommandHandler("done", cmd_done))
    application.add_handler(CommandHandler("add", cmd_add))
    application.add_handler(CommandHandler("goals", cmd_goals))
    application.add_handler(CommandHandler("schedule", cmd_schedule))
    application.add_handler(CommandHandler("goallog", cmd_goallog))
    application.add_handler(build_conversation_addgoal())
    application.add_handler(CallbackQueryHandler(on_pair_callback, pattern=r"^pair:"))
    application.add_handler(CallbackQueryHandler(on_task_toggle, pattern=r"^task:toggle:"))
    application.add_handler(CallbackQueryHandler(on_goal_callback, pattern=r"^goal:(done|del|log):"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & MENU_FILTER, on_main_menu))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))


# --- Функции для планировщика (вызываются из scheduler.py) ---


async def job_send_pair_question(bot) -> None:
    """22:00 МСК — вопрос о паре (каждому чату из CHAT_IDS)."""
    if not CHAT_IDS:
        logger.warning("CHAT_ID / CHAT_IDS не заданы — пропуск вечернего опроса")
        return
    for chat_id in CHAT_IDS:
        await bot.send_message(
            chat_id=chat_id,
            text="📚 К какой паре завтра?",
            reply_markup=pair_selection_keyboard(),
        )


async def job_day_summary(bot) -> None:
    """23:30 МСК — итог дня по задачам (отдельно для каждого chat_id)."""
    if not CHAT_IDS:
        return
    today = moscow_today()
    for chat_id in CHAT_IDS:
        with SessionLocal() as db:
            tasks = list(
                db.execute(
                    select(Task).where(Task.chat_id == chat_id, Task.task_date == today)
                ).scalars().all()
            )
        if not tasks:
            continue
        undone = [t for t in tasks if not t.done]
        if not undone:
            await bot.send_message(
                chat_id=chat_id,
                text=DAY_SUMMARY_ALL_DONE,
                reply_markup=main_menu_keyboard(),
            )
            continue
        lines = "\n".join(f"⬜ {t.text}" for t in undone)
        await bot.send_message(
            chat_id=chat_id,
            text=f"{DAY_SUMMARY_INCOMPLETE}\n\nНевыполнено:\n{lines}",
            reply_markup=main_menu_keyboard(),
        )


async def job_weekly_goals_checkup(bot, application) -> None:
    """Пятница 20:00 МСК — чекап целей по каждому чату."""
    if not CHAT_IDS:
        return
    pending = application.bot_data.setdefault(BOT_DATA_PENDING_WEEKLY, set()) if application else None

    for chat_id in CHAT_IDS:
        with SessionLocal() as db:
            goals = list(
                db.execute(
                    select(Goal)
                    .where(Goal.chat_id == chat_id, Goal.completed.is_(False))
                    .order_by(Goal.id)
                ).scalars().all()
            )
        if not goals:
            await bot.send_message(
                chat_id=chat_id,
                text="📊 Еженедельный чекап: активных целей нет.",
                reply_markup=main_menu_keyboard(),
            )
            continue
        parts = []
        for g in goals:
            parts.append(f"• {g.title}")
        text = (
            "📊 Еженедельный чекап целей\n\n"
            + "\n".join(parts)
            + "\n\nЧто сделал на этой неделе для достижения своих целей? Напиши ответ одним сообщением."
        )
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=weekly_pending_keyboard(),
        )
        if pending is not None:
            pending.add(chat_id)
