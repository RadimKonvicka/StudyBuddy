"""Testy: zobrazení otázek a odevzdání odpovědí (vyhodnocení, zvládnutí podtémat, XP)."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..access import get_quiz
from ..database import get_db
from ..deps import get_current_user
from ..models import Quiz, User
from ..progress import XP_CORRECT_ANSWER, award_xp, mastery_level, update_mastery
from ..schemas import (
    QuestionOut,
    QuestionResult,
    QuizOut,
    QuizResultOut,
    SubmitIn,
    SubtopicScore,
    UserOut,
)

router = APIRouter(prefix="/api/quizzes", tags=["Testy"])


def _result(quiz: Quiz, before: dict[int, int | None] | None = None, xp: int = 0) -> QuizResultOut:
    """Vyhodnocení odevzdaného testu: správné odpovědi, vysvětlení a výsledek po podtématech."""
    per_subtopic: dict[int, SubtopicScore] = {}
    for q in quiz.questions:
        s = per_subtopic.setdefault(
            q.subtopic_id,
            SubtopicScore(
                id=q.subtopic.id,
                name=q.subtopic.name,
                correct=0,
                total=0,
                before=(before or {}).get(q.subtopic_id),
                mastery=q.subtopic.mastery,
                level=mastery_level(q.subtopic.mastery),
            ),
        )
        s.total += 1
        s.correct += q.chosen == q.correct
    return QuizResultOut(
        score=quiz.score or 0,
        total=len(quiz.questions),
        xp_gained=xp,
        questions=[
            QuestionResult(
                id=q.id,
                text=q.text,
                options=q.options,
                subtopic_name=q.subtopic.name,
                chosen=q.chosen,
                correct=q.correct,
                explanation=q.explanation,
                is_correct=q.chosen == q.correct,
            )
            for q in quiz.questions
        ],
        subtopics=list(per_subtopic.values()),
    )


@router.get("/{quiz_id}", response_model=QuizOut)
def quiz_detail(quiz_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    quiz = get_quiz(db, quiz_id, user)
    completed = quiz.completed_at is not None
    return QuizOut(
        id=quiz.id,
        kind=quiz.kind,
        subject_id=quiz.subject_id,
        subject_title=quiz.subject.title,
        subtopic_id=quiz.subtopic_id,
        subtopic_name=quiz.subtopic.name if quiz.subtopic else None,
        completed=completed,
        # Správné odpovědi se posílají až po odevzdání – jinak by šly vyčíst z odpovědi serveru.
        questions=[
            QuestionOut(id=q.id, text=q.text, options=q.options, subtopic_name=q.subtopic.name)
            for q in quiz.questions
        ],
        result=_result(quiz) if completed else None,
    )


@router.post("/{quiz_id}/submit", response_model=QuizResultOut)
def submit_quiz(
    quiz_id: int, body: SubmitIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    quiz = get_quiz(db, quiz_id, user)
    if quiz.completed_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Tento test už je odevzdaný.")

    for q in quiz.questions:
        chosen = body.answers.get(q.id)
        q.chosen = chosen if chosen is not None and 0 <= chosen < len(q.options) else None
    quiz.score = sum(q.chosen == q.correct for q in quiz.questions)
    quiz.completed_at = datetime.now(timezone.utc)

    # Zvládnutí každého podtématu přepočítáme podle odpovědí v tomto testu.
    counts = {}  # podtéma -> [správně, celkem]
    for q in quiz.questions:
        c = counts.setdefault(q.subtopic, [0, 0])
        c[0] += q.chosen == q.correct
        c[1] += 1
    before = {}
    for subtopic, (correct, total) in counts.items():
        before[subtopic.id] = subtopic.mastery
        subtopic.mastery = update_mastery(subtopic.mastery, correct, total)

    xp = quiz.score * XP_CORRECT_ANSWER
    award_xp(user, xp)
    db.commit()

    result = _result(quiz, before, xp)
    result.user = UserOut.model_validate(user)
    return result
