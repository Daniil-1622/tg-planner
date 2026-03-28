"""
Модели SQLAlchemy и инициализация SQLite (data.db).
"""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from config import DB_PATH


class Base(DeclarativeBase):
    pass


class Task(Base):
    """Задача на конкретную дату (день в календаре пользователя, МСК)."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    task_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    text: Mapped[str] = mapped_column(String(500), nullable=False)
    done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class Goal(Base):
    """Долгосрочная цель."""

    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    deadline: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    motivation: Mapped[str] = mapped_column(Text, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    journal_entries: Mapped[list["GoalJournalEntry"]] = relationship(
        back_populates="goal", cascade="all, delete-orphan"
    )


class GoalJournalEntry(Base):
    """Дневниковая запись по цели (в т.ч. еженедельный чекап)."""

    __tablename__ = "goal_journal_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    goal: Mapped["Goal"] = relationship(back_populates="journal_entries")


class ScheduleChoice(Base):
    """Выбранная пара на конкретный учебный день (дата = «завтра» на момент опроса в 22:00)."""

    __tablename__ = "schedule_choices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    target_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    pair_key: Mapped[str] = mapped_column(String(10), nullable=False)


engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_db() -> None:
    """Создаёт таблицы, если их ещё нет."""
    Base.metadata.create_all(bind=engine)
