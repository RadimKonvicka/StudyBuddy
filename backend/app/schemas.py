"""Pydantic schémata – tvar dat, která API přijímá a vrací (a jejich validace)."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)

    @field_validator("display_name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Jméno nesmí být prázdné.")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str
    xp: int
    streak: int
    longest_streak: int


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- Učení: témata, testy, výklad, kartičky -------------------------------------------------

class SubjectIn(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    level: str = Field(default="", max_length=300)

    @field_validator("title", "level")
    @classmethod
    def _clean(cls, v: str) -> str:
        return v.strip()

    @field_validator("title")
    @classmethod
    def _title_not_empty(cls, v: str) -> str:
        if len(v) < 2:
            raise ValueError("Napiš téma alespoň dvěma znaky.")
        return v


class SubtopicOut(BaseModel):
    id: int
    name: str
    description: str
    mastery: int | None  # 0–100, None = ještě netestováno
    level: str | None  # "weak" | "mid" | "strong" | None
    has_lesson: bool
    cards: int


class QuizBrief(BaseModel):
    id: int
    kind: str  # "entry" | "practice"
    subtopic_name: str | None
    completed: bool
    score: int | None
    total: int
    created_at: datetime


class SubjectListItem(BaseModel):
    id: int
    title: str
    level: str
    created_at: datetime
    mastery: int | None  # průměr přes otestovaná podtémata
    entry_quiz_id: int | None
    entry_done: bool
    subtopic_count: int


class SubjectOut(SubjectListItem):
    subtopics: list[SubtopicOut]
    quizzes: list[QuizBrief]


class QuestionOut(BaseModel):
    id: int
    text: str
    options: list[str]
    subtopic_name: str


class QuestionResult(QuestionOut):
    chosen: int | None
    correct: int
    explanation: str
    is_correct: bool


class SubtopicScore(BaseModel):
    id: int
    name: str
    correct: int
    total: int
    before: int | None  # zvládnutí před testem (jen hned po odevzdání)
    mastery: int | None
    level: str | None


class QuizResultOut(BaseModel):
    score: int
    total: int
    xp_gained: int
    questions: list[QuestionResult]
    subtopics: list[SubtopicScore]
    user: UserOut | None = None


class QuizOut(BaseModel):
    id: int
    kind: str
    subject_id: int
    subject_title: str
    subtopic_id: int | None
    subtopic_name: str | None
    completed: bool
    questions: list[QuestionOut]  # bez správných odpovědí, dokud test není odevzdaný
    result: QuizResultOut | None


class SubmitIn(BaseModel):
    answers: dict[int, int]  # {id otázky: index zvolené možnosti 0–3}


class FlashcardOut(BaseModel):
    id: int
    front: str
    back: str
    box: int


class LessonOut(BaseModel):
    subject_id: int
    subject_title: str
    subtopic: SubtopicOut
    content: str | None  # None = výklad ještě nebyl vytvořen
    flashcards: list[FlashcardOut]


class ReviewCard(FlashcardOut):
    subject_title: str
    subtopic_name: str


class ReviewOut(BaseModel):
    cards: list[ReviewCard]
    due_total: int


class ReviewIn(BaseModel):
    known: bool


class ReviewResult(BaseModel):
    box: int
    due_date: date
    xp_gained: int
    user: UserOut


class QuizCreated(BaseModel):
    quiz_id: int
