"""Opakování kartiček (Leitnerův systém)."""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..access import get_flashcard
from ..database import get_db
from ..deps import get_current_user
from ..models import Flashcard, Subject, Subtopic, User
from ..progress import XP_CARD_KNOWN, XP_CARD_UNKNOWN, award_xp, next_review
from ..schemas import ReviewCard, ReviewIn, ReviewOut, ReviewResult, UserOut

router = APIRouter(tags=["Opakování"])

BATCH = 30  # kolik kartiček poslat najednou


@router.get("/api/review", response_model=ReviewOut)
def due_cards(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Kartičky, které je dnes potřeba zopakovat – nejdřív ty z nejnižších krabiček."""
    due = (
        select(Flashcard)
        .join(Subtopic, Flashcard.subtopic_id == Subtopic.id)
        .join(Subject, Subtopic.subject_id == Subject.id)
        .where(Subject.user_id == user.id, Flashcard.due_date <= date.today())
    )
    total = db.scalar(select(func.count()).select_from(due.subquery()))
    cards = db.scalars(due.order_by(Flashcard.box, Flashcard.due_date, Flashcard.id).limit(BATCH))
    return ReviewOut(
        due_total=total or 0,
        cards=[
            ReviewCard(
                id=c.id,
                front=c.front,
                back=c.back,
                box=c.box,
                subject_title=c.subtopic.subject.title,
                subtopic_name=c.subtopic.name,
            )
            for c in cards
        ],
    )


@router.post("/api/flashcards/{card_id}/review", response_model=ReviewResult)
def review_card(
    card_id: int, body: ReviewIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    card = get_flashcard(db, card_id, user)
    card.box, card.due_date = next_review(card.box, body.known)
    xp = XP_CARD_KNOWN if body.known else XP_CARD_UNKNOWN
    award_xp(user, xp)
    db.commit()
    return ReviewResult(box=card.box, due_date=card.due_date, xp_gained=xp, user=UserOut.model_validate(user))
