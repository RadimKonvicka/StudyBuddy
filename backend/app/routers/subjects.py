"""Témata a podtémata: vytvoření tématu (AI plán + vstupní test), výklad a procvičovací testy."""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import ai
from ..access import get_subject, get_subtopic, subtopic_out
from ..database import get_db
from ..deps import get_current_user
from ..models import Flashcard, Lesson, Question, Quiz, Subject, Subtopic, User
from ..schemas import (
    FlashcardOut,
    LessonOut,
    QuizBrief,
    QuizCreated,
    SubjectIn,
    SubjectListItem,
    SubjectOut,
)
from ..progress import mastery_level

router = APIRouter(tags=["Učení"])


def _ai_call(fn, *args):
    """Zavolá funkci z modulu ai a chybu AI převede na HTTP odpověď s českou hláškou."""
    try:
        return fn(*args)
    except ai.AIError as err:
        raise HTTPException(err.status, err.message)


def _summary(subject: Subject) -> dict:
    tested = [s.mastery for s in subject.subtopics if s.mastery is not None]
    entry = next((q for q in subject.quizzes if q.kind == "entry"), None)
    return dict(
        id=subject.id,
        title=subject.title,
        level=subject.level,
        created_at=subject.created_at,
        mastery=round(sum(tested) / len(tested)) if tested else None,
        entry_quiz_id=entry.id if entry else None,
        entry_done=bool(entry and entry.completed_at),
        subtopic_count=len(subject.subtopics),
    )


def _subject_out(subject: Subject) -> SubjectOut:
    return SubjectOut(
        **_summary(subject),
        subtopics=[subtopic_out(s) for s in subject.subtopics],
        quizzes=[
            QuizBrief(
                id=q.id,
                kind=q.kind,
                subtopic_name=q.subtopic.name if q.subtopic else None,
                completed=q.completed_at is not None,
                score=q.score,
                total=len(q.questions),
                created_at=q.created_at,
            )
            for q in reversed(subject.quizzes)  # nejnovější nahoře
        ],
    )


def _mistakes(db: Session, subtopic: Subtopic) -> list[str]:
    """Otázky z tohoto podtématu, na které uživatel odpověděl špatně – AI se na ně zaměří."""
    rows = db.scalars(
        select(Question).where(Question.subtopic_id == subtopic.id, Question.chosen.is_not(None))
    )
    return [f"{q.text} (správně: {q.options[q.correct]})" for q in rows if q.chosen != q.correct]


# --- Témata ---------------------------------------------------------------------------------

@router.get("/api/subjects", response_model=list[SubjectListItem])
def list_subjects(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    subjects = db.scalars(select(Subject).where(Subject.user_id == user.id).order_by(Subject.id.desc()))
    return [SubjectListItem(**_summary(s)) for s in subjects]


@router.post("/api/subjects", response_model=SubjectOut, status_code=201)
def create_subject(body: SubjectIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Uživatel zadá téma → AI ho rozdělí na podtémata a připraví vstupní test."""
    plan = _ai_call(ai.generate_plan, body.title, body.level)

    subject = Subject(user_id=user.id, title=body.title, level=body.level)
    subject.subtopics = [
        Subtopic(position=i, name=s.name, description=s.description) for i, s in enumerate(plan.subtopics)
    ]
    quiz = Quiz(kind="entry")
    quiz.questions = [
        Question(
            position=i,
            subtopic=subject.subtopics[q.subtopic],
            text=q.question,
            options=q.options,
            correct=q.correct,
            explanation=q.explanation,
        )
        for i, q in enumerate(plan.questions)
    ]
    subject.quizzes = [quiz]
    db.add(subject)
    db.commit()
    return _subject_out(subject)


@router.get("/api/subjects/{subject_id}", response_model=SubjectOut)
def subject_detail(subject_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _subject_out(get_subject(db, subject_id, user))


@router.delete("/api/subjects/{subject_id}", status_code=204)
def delete_subject(subject_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(get_subject(db, subject_id, user))
    db.commit()
    return Response(status_code=204)


# --- Podtémata: výklad a procvičování -------------------------------------------------------

def _lesson_out(subtopic: Subtopic) -> LessonOut:
    return LessonOut(
        subject_id=subtopic.subject.id,
        subject_title=subtopic.subject.title,
        subtopic=subtopic_out(subtopic),
        content=subtopic.lesson.content if subtopic.lesson else None,
        flashcards=[FlashcardOut(id=c.id, front=c.front, back=c.back, box=c.box) for c in subtopic.flashcards],
    )


@router.get("/api/subtopics/{subtopic_id}", response_model=LessonOut)
def subtopic_detail(subtopic_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _lesson_out(get_subtopic(db, subtopic_id, user))


@router.post("/api/subtopics/{subtopic_id}/lesson", response_model=LessonOut)
def create_lesson(subtopic_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Vytvoří (nebo podle aktuální úrovně znovu vytvoří) výklad a kartičky k podtématu."""
    subtopic = get_subtopic(db, subtopic_id, user)
    subject = subtopic.subject
    lesson = _ai_call(
        ai.generate_lesson,
        subject.title,
        subject.level,
        subtopic.name,
        subtopic.description,
        mastery_level(subtopic.mastery),
        _mistakes(db, subtopic),
    )
    # Nový výklad nahradí starý a kartičky se vytvoří nové (staré by se tématicky opakovaly).
    if subtopic.lesson:
        subtopic.lesson.content = lesson.content
    else:
        subtopic.lesson = Lesson(content=lesson.content)
    subtopic.flashcards = [Flashcard(front=c.front, back=c.back) for c in lesson.flashcards]
    db.commit()
    return _lesson_out(subtopic)


@router.post("/api/subtopics/{subtopic_id}/quiz", response_model=QuizCreated, status_code=201)
def create_practice_quiz(
    subtopic_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Procvičovací test k jednomu podtématu, obtížnost podle toho, jak ho uživatel zvládá."""
    subtopic = get_subtopic(db, subtopic_id, user)
    subject = subtopic.subject
    previous = list(db.scalars(select(Question.text).where(Question.subtopic_id == subtopic.id)))
    questions = _ai_call(
        ai.generate_quiz,
        subject.title,
        subject.level,
        subtopic.name,
        subtopic.description,
        mastery_level(subtopic.mastery),
        previous,
    )
    quiz = Quiz(subject=subject, subtopic=subtopic, kind="practice")
    quiz.questions = [
        Question(
            position=i,
            subtopic=subtopic,
            text=q.question,
            options=q.options,
            correct=q.correct,
            explanation=q.explanation,
        )
        for i, q in enumerate(questions)
    ]
    db.add(quiz)
    db.commit()
    return QuizCreated(quiz_id=quiz.id)
