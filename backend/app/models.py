"""Databázové tabulky (SQLAlchemy ORM).

Každá data patří konkrétnímu uživateli – přímo (user_id) nebo přes předmět (subject.user_id).

Struktura učení:
    User ─< Subject (téma, např. „Fotosyntéza“)
              ├─< Subtopic (podtéma; mastery = jak dobře ho uživatel zvládá, 0–100)
              │     ├── Lesson (výklad od AI, nejvýš jeden)
              │     └─< Flashcard (kartičky pro opakování, Leitnerův systém)
              └─< Quiz (vstupní test „entry“ nebo procvičovací „practice“)
                    └─< Question (otázka ABCD + odpověď uživatele)
"""
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Gamifikace
    xp: Mapped[int] = mapped_column(Integer, default=0)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_active_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class Subject(Base):
    """Téma, které se chce uživatel naučit."""

    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    level: Mapped[str] = mapped_column(String(300), default="")  # volitelná poznámka: ročník, co už umí…
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # cascade="all, delete-orphan" = smazáním tématu se smaže i vše, co k němu patří
    subtopics: Mapped[list["Subtopic"]] = relationship(
        back_populates="subject", cascade="all, delete-orphan", order_by="Subtopic.position"
    )
    quizzes: Mapped[list["Quiz"]] = relationship(
        back_populates="subject", cascade="all, delete-orphan", order_by="Quiz.id"
    )


class Subtopic(Base):
    """Část tématu. Podle `mastery` se řídí, jak podrobný výklad AI napíše."""

    __tablename__ = "subtopics"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text, default="")
    mastery: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = ještě netestováno

    subject: Mapped[Subject] = relationship(back_populates="subtopics")
    lesson: Mapped["Lesson | None"] = relationship(
        back_populates="subtopic", cascade="all, delete-orphan", uselist=False
    )
    flashcards: Mapped[list["Flashcard"]] = relationship(
        back_populates="subtopic", cascade="all, delete-orphan", order_by="Flashcard.id"
    )


class Quiz(Base):
    __tablename__ = "quizzes"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    # u procvičovacího testu podtéma, ke kterému patří; vstupní test pokrývá všechna (None)
    subtopic_id: Mapped[int | None] = mapped_column(
        ForeignKey("subtopics.id", ondelete="CASCADE"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(20))  # "entry" | "practice"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)  # počet správných odpovědí

    subject: Mapped[Subject] = relationship(back_populates="quizzes")
    subtopic: Mapped[Subtopic | None] = relationship()
    questions: Mapped[list["Question"]] = relationship(
        back_populates="quiz", cascade="all, delete-orphan", order_by="Question.position"
    )


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("quizzes.id", ondelete="CASCADE"), index=True)
    subtopic_id: Mapped[int] = mapped_column(ForeignKey("subtopics.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text)
    options: Mapped[list[str]] = mapped_column(JSON)  # vždy 4 možnosti (A–D)
    correct: Mapped[int] = mapped_column(Integer)  # index správné možnosti 0–3
    explanation: Mapped[str] = mapped_column(Text, default="")
    chosen: Mapped[int | None] = mapped_column(Integer, nullable=True)  # odpověď uživatele

    quiz: Mapped[Quiz] = relationship(back_populates="questions")
    subtopic: Mapped[Subtopic] = relationship()


class Lesson(Base):
    """Výklad podtématu v Markdownu, napsaný AI na míru úrovni uživatele."""

    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(primary_key=True)
    subtopic_id: Mapped[int] = mapped_column(
        ForeignKey("subtopics.id", ondelete="CASCADE"), unique=True
    )
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    subtopic: Mapped[Subtopic] = relationship(back_populates="lesson")


class Flashcard(Base):
    """Kartička. `box` 1–5 = Leitnerova krabička, `due_date` = kdy ji znovu ukázat."""

    __tablename__ = "flashcards"

    id: Mapped[int] = mapped_column(primary_key=True)
    subtopic_id: Mapped[int] = mapped_column(ForeignKey("subtopics.id", ondelete="CASCADE"), index=True)
    front: Mapped[str] = mapped_column(Text)
    back: Mapped[str] = mapped_column(Text)
    box: Mapped[int] = mapped_column(Integer, default=1)
    due_date: Mapped[date] = mapped_column(Date, default=date.today)

    subtopic: Mapped[Subtopic] = relationship(back_populates="flashcards")
