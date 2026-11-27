"""Témata a podtémata: vytvoření tématu (AI plán + vstupní test), výklad a procvičovací testy.

Téma jde vytvořit dvěma způsoby: jen z názvu (AI použije své znalosti), nebo z nahraných podkladů
(zápisky, prezentace) – pak vše vychází 1:1 z textu podkladů.
"""
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import ai
from ..config import get_settings
from ..documents import MIN_CHARS, TRUNCATED_MARK, DocumentError, extract_text, fit_materials, format_materials
from ..access import get_subject, get_subtopic, subtopic_out
from ..database import get_db
from ..deps import get_current_user
from ..models import Flashcard, Lesson, Material, Question, Quiz, Subject, Subtopic, User
from ..schemas import (
    FlashcardOut,
    LessonOut,
    MaterialOut,
    QuizBrief,
    QuizCreated,
    SubjectIn,
    SubjectListItem,
    SubjectOut,
)
from ..progress import mastery_level

router = APIRouter(tags=["Učení"])


MAX_FILES = 5


def _ai_call(fn, *args, **kwargs):
    """Zavolá funkci z modulu ai a chybu AI převede na HTTP odpověď s českou hláškou."""
    try:
        return fn(*args, **kwargs)
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
        entry_skipped=entry is None,
        subtopic_count=len(subject.subtopics),
        from_materials=bool(subject.materials),
    )


def subject_out(subject: Subject) -> SubjectOut:
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
        materials=[MaterialOut(id=m.id, filename=m.filename, chars=len(m.text)) for m in subject.materials],
        materials_truncated=any(m.text.endswith(TRUNCATED_MARK) for m in subject.materials),
    )


def _mistakes(db: Session, subtopic: Subtopic) -> list[str]:
    """Otázky z tohoto podtématu, na které uživatel odpověděl špatně – AI se na ně zaměří."""
    rows = db.scalars(
        select(Question).where(Question.subtopic_id == subtopic.id, Question.chosen.is_not(None))
    )
    return [f"{q.text} (správně: {q.options[q.correct]})" for q in rows if q.chosen != q.correct]


def _level(subtopic: Subtopic) -> str | None:
    """Úroveň studenta v podtématu pro AI.

    Když student vstupní test přeskočil (začíná od nuly) a podtéma ještě netestoval, bereme ho jako
    slabé – výklad i procvičování půjdou od úplných základů.
    """
    level = mastery_level(subtopic.mastery)
    if level is None and not any(q.kind == "entry" for q in subtopic.subject.quizzes):
        return "weak"
    return level


# --- Témata ---------------------------------------------------------------------------------

@router.get("/api/subjects", response_model=list[SubjectListItem])
def list_subjects(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    subjects = db.scalars(select(Subject).where(Subject.user_id == user.id).order_by(Subject.id.desc()))
    return [SubjectListItem(**_summary(s)) for s in subjects]


def _save_subject(db: Session, user: User, title: str, level: str, plan: ai.AIPlan, materials=()) -> Subject:
    """Uloží téma podle plánu od AI: podtémata, vstupní test (pokud ho plán má) a případně podklady."""
    subject = Subject(user_id=user.id, title=title, level=level)
    subject.materials = [Material(filename=name, text=text) for name, text in materials]
    subject.subtopics = [
        Subtopic(position=i, name=s.name, description=s.description) for i, s in enumerate(plan.subtopics)
    ]
    if not plan.questions:  # student začíná od nuly – vstupní test přeskočil
        db.add(subject)
        db.commit()
        return subject
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
    return subject


@router.post("/api/subjects", response_model=SubjectOut, status_code=201)
def create_subject(body: SubjectIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Uživatel zadá téma → AI ho rozdělí na podtémata a připraví vstupní test (pokud ho nepřeskočil)."""
    plan = _ai_call(ai.generate_plan, body.title, body.level, entry_quiz=not body.skip_entry)
    return subject_out(_save_subject(db, user, body.title, body.level, plan))


@router.post("/api/subjects/upload", response_model=SubjectOut, status_code=201)
def create_subject_from_files(
    files: list[UploadFile] = File(...),
    title: str = Form(""),
    level: str = Form(""),
    skip_entry: bool = Form(False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Uživatel nahraje své podklady → AI z nich (a jen z nich) připraví podtémata a vstupní test.

    Funkce je záměrně obyčejná (ne async): čtení PDF a čekání na AI zabere čas a FastAPI takovou
    funkci spustí v samostatném vlákně, takže server mezitím obsluhuje ostatní požadavky.
    """
    settings = get_settings()
    if not files or len(files) > MAX_FILES:
        raise HTTPException(422, f"Nahraj 1 až {MAX_FILES} souborů.")
    title, level = title.strip()[:120], level.strip()[:300]

    max_bytes = settings.max_upload_mb * 1024 * 1024
    materials = []
    for f in files:
        name = Path(f.filename or "soubor").name[:255]
        data = f.file.read(max_bytes + 1)  # nečteme víc, než je limit
        if len(data) > max_bytes:
            raise HTTPException(413, f"„{name}“ je větší než {settings.max_upload_mb} MB.")
        try:
            text = extract_text(name, data)
        except DocumentError as err:
            raise HTTPException(422, err.message)
        materials.append((name, text))

    if sum(len(t) for _, t in materials) < MIN_CHARS:
        raise HTTPException(422, "V podkladech je moc málo textu. Nahraj obsáhlejší zápisky.")
    materials, _ = fit_materials(materials, settings.max_text_chars)
    if len(title) < 2:
        title = Path(materials[0][0]).stem.replace("_", " ").strip()[:120] or "Moje podklady"

    plan = _ai_call(
        ai.generate_plan, title, level, material=format_materials(materials), entry_quiz=not skip_entry
    )
    return subject_out(_save_subject(db, user, title, level, plan, materials))


@router.get("/api/subjects/{subject_id}", response_model=SubjectOut)
def subject_detail(subject_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return subject_out(get_subject(db, subject_id, user))


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
        from_materials=bool(subtopic.subject.materials),
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
        _level(subtopic),
        _mistakes(db, subtopic),
        material=subject.material_text,
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
        _level(subtopic),
        previous,
        material=subject.material_text,
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
