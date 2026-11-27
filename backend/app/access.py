"""Načítání dat s kontrolou vlastníka.

Každá funkce vrátí záznam jen tehdy, když patří přihlášenému uživateli. Jinak vrátí 404 –
záměrně ne 403, aby cizí uživatel ani nepoznal, že záznam s tímto ID existuje.

U tříd: kdo není členem, dostane 404; člen bez potřebných práv (žák u učitelské akce) 403.
"""
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Flashcard, Group, GroupMember, Quiz, Subject, Subtopic, User
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


# --- Třídy ----------------------------------------------------------------------------------

def get_membership(db: Session, group_id: int, user: User, teacher: bool = False) -> GroupMember:
    """Členství přihlášeného uživatele ve třídě. `teacher=True` = akce jen pro učitele (jinak 403)."""
    member = db.scalar(
        select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == user.id)
    )
    if member is None:
        raise _not_found("Třída")
    if teacher and member.role != "teacher":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Tohle může jen učitel třídy.")
    return member


def get_member(db: Session, group: Group, user_id: int, role: str | None = None) -> GroupMember:
    """Jiný člen téže třídy (např. žák, jehož výsledky si učitel prohlíží)."""
    member = db.scalar(
        select(GroupMember).where(GroupMember.group_id == group.id, GroupMember.user_id == user_id)
    )
    if member is None or (role and member.role != role):
        raise _not_found("Žák" if role == "student" else "Člen třídy")
    return member
