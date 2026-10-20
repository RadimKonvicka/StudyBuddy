from datetime import date, timedelta
from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Document, Question, Card
from extract import extract_text
from macros import MACROS, run_macro
from liascript import build_liascript

Base.metadata.create_all(bind=engine)

app = FastAPI(title="StudyBuddy API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4321", "http://127.0.0.1:4321"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Leitner: po kolika dnech se kartička v dané krabičce vrátí
INTERVALS = {1: 0, 2: 1, 3: 3, 4: 7, 5: 14}


class ReviewIn(BaseModel):
    correct: bool


@app.get("/api/macros")
def list_macros():
    return [{"key": k, "label": v["label"], "desc": v["desc"]} for k, v in MACROS.items()]


@app.post("/api/documents")
def upload(file: UploadFile = File(...), macro: str = Form("full"), db: Session = Depends(get_db)):
    if macro not in MACROS:
        raise HTTPException(400, "Neznámé makro.")
    try:
        text = extract_text(file.filename, file.file.read())
    except ValueError as e:
        raise HTTPException(400, str(e))
    if len(text) < 50:
        raise HTTPException(422, "V souboru jsem nenašel dost textu (možná je to sken).")

    try:
        res = run_macro(macro, text)
    except Exception as e:
        raise HTTPException(502, f"Chyba AI: {e}")

    doc = Document(title=file.filename.rsplit(".", 1)[0], text=res["text"], summary=res["summary"])
    doc.questions = [
        Question(question=q["question"], options=q["options"], correct=q["correct"],
                 explanation=q.get("explanation", ""))
        for q in res["questions"]
    ]
    doc.cards = [Card(front=c["front"], back=c["back"]) for c in res["cards"]]
    db.add(doc)
    db.commit()
    return {"id": doc.id, "agents": res["log"]}


@app.get("/api/documents")
def list_documents(db: Session = Depends(get_db)):
    docs = db.query(Document).order_by(Document.created_at.desc()).all()
    return [
        {"id": d.id, "title": d.title, "created_at": d.created_at.isoformat(),
         "questions": len(d.questions), "cards": len(d.cards)}
        for d in docs
    ]


@app.get("/api/documents/{doc_id}")
def get_document(doc_id: int, db: Session = Depends(get_db)):
    d = db.get(Document, doc_id)
    if not d:
        raise HTTPException(404, "Dokument nenalezen.")
    return {
        "id": d.id, "title": d.title, "summary": d.summary,
        "questions": [{"question": q.question, "options": q.options,
                       "correct": q.correct, "explanation": q.explanation} for q in d.questions],
        "cards": [{"id": c.id, "front": c.front, "back": c.back, "box": c.box,
                   "next_review": c.next_review.isoformat()} for c in d.cards],
    }


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db)):
    d = db.get(Document, doc_id)
    if not d:
        raise HTTPException(404, "Dokument nenalezen.")
    db.delete(d)
    db.commit()
    return {"ok": True}


@app.get("/api/documents/{doc_id}/liascript", response_class=PlainTextResponse)
def export_liascript(doc_id: int, db: Session = Depends(get_db)):
    d = db.get(Document, doc_id)
    if not d:
        raise HTTPException(404, "Dokument nenalezen.")
    return build_liascript(d)


@app.post("/api/cards/{card_id}/review")
def review_card(card_id: int, body: ReviewIn, db: Session = Depends(get_db)):
    c = db.get(Card, card_id)
    if not c:
        raise HTTPException(404, "Kartička nenalezena.")
    c.box = min(c.box + 1, 5) if body.correct else 1
    c.next_review = date.today() + timedelta(days=INTERVALS[c.box])
    db.commit()
    return {"box": c.box, "next_review": c.next_review.isoformat()}