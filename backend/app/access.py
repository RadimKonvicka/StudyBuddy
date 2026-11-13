"""Načítání dat s kontrolou vlastníka.

Každá funkce vrátí záznam jen tehdy, když patří přihlášenému uživateli. Jinak vrátí 404 –
záměrně ne 403, aby cizí uživatel ani nepoznal, že záznam s tímto ID existuje.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from .models import Flashcard, Quiz, Subject, Subtopic, User
from .progress import mastery_level
from .schemas import SubtopicOut


def _not_found(what: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"{what} neexistuje.")


def get_subject(db: Session, subject_id: int, user: User) -> Subject:
    subject = db.get(Subject, subject_id)
    if subject is None or subject.user_id != user.id:
        raise _not_found("Téma")
    return subject


def get_subtopic(db: Session, subtopic_id: int, user: User) -> Subtopic:
    subtopic = db.get(Subtopic, subtopic_id)
    if subtopic is None or subtopic.subject.user_id != user.id:
        raise _not_found("Podtéma")
    return subtopic


def get_quiz(db: Session, quiz_id: int, user: User) -> Quiz:
    quiz = db.get(Quiz, quiz_id)
    if quiz is None or quiz.subject.user_id != user.id:
        raise _not_found("Test")
    return quiz


def get_flashcard(db: Session, card_id: int, user: User) -> Flashcard:
    card = db.get(Flashcard, card_id)
    if card is None or card.subtopic.subject.user_id != user.id:
        raise _not_found("Kartička")
    return card


def subtopic_out(subtopic: Subtopic) -> SubtopicOut:
    return SubtopicOut(
        id=subtopic.id,
        name=subtopic.name,
        description=subtopic.description,
        mastery=subtopic.mastery,
        level=mastery_level(subtopic.mastery),
        has_lesson=subtopic.lesson is not None,
        cards=len(subtopic.flashcards),
    )
