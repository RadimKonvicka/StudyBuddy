"""Testy učení: téma → vstupní test → zvládnutí podtémat → výklad a kartičky → opakování.

Skutečné AI se nevolá – funkce z modulu `ai` nahradíme falešnými, které vrací pevná data.
"""
from datetime import date, timedelta

import pytest

from app import ai, progress
from app.models import User
from tests.conftest import register


def _q(subtopic: int, n: int) -> ai.AIQuestion:
    # správná odpověď je vždy možnost „správně“ (index 0) – po zamíchání ji test najde podle textu
    return ai.AIQuestion(
        subtopic=subtopic,
        question=f"Otázka {subtopic}-{n}",
        options=["správně", "špatně A", "špatně B", "špatně C"],
        correct=0,
        explanation="Protože.",
    )


@pytest.fixture
def fake_ai(monkeypatch):
    calls = {}

    def plan(title, level):
        calls["plan"] = (title, level)
        return ai.AIPlan(
            subtopics=[ai.AISubtopic(name=f"Podtéma {i}", description="popis") for i in range(3)],
            questions=ai._clean_questions([_q(i, n) for i in range(3) for n in range(2)], 3),
        )

    def lesson(title, level_note, subtopic, description, level, mistakes):
        calls["lesson"] = {"level": level, "mistakes": mistakes}
        return ai.AILesson(
            content="## Výklad\n" + "Text výkladu. " * 30,
            flashcards=[ai.AIFlashcard(front=f"Pojem {i}", back=f"Vysvětlení {i}") for i in range(3)],
        )

    def quiz(title, level_note, subtopic, description, level, previous):
        calls["quiz"] = {"level": level, "previous": previous}
        return ai._clean_questions([_q(0, n) for n in range(5)], 1)

    monkeypatch.setattr(ai, "generate_plan", plan)
    monkeypatch.setattr(ai, "generate_lesson", lesson)
    monkeypatch.setattr(ai, "generate_quiz", quiz)
    return calls


def _answers(quiz: dict, good: set[str]) -> dict:
    """Odpovědi na test: u otázek z podtémat v `good` správně, jinak špatně."""
    answers = {}
    for q in quiz["questions"]:
        right = q["options"].index("správně")
        answers[q["id"]] = right if q["subtopic_name"] in good else (right + 1) % 4
    return answers


def _create(client, headers, title="Fotosyntéza"):
    r = client.post("/api/subjects", json={"title": title, "level": "2. ročník"}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


# --- Čistá logika (progress.py) ------------------------------------------------------------

def test_mastery_levels():
    assert progress.mastery_level(None) is None
    assert progress.mastery_level(49) == "weak"
    assert progress.mastery_level(50) == "mid"
    assert progress.mastery_level(80) == "strong"
    assert progress.update_mastery(None, 1, 2) == 50
    assert progress.update_mastery(50, 2, 2) == 80  # 0,4·50 + 0,6·100


def test_streak():
    user = User(xp=0, streak=0, longest_streak=0, last_active_date=None)
    day = date(2026, 11, 10)
    progress.award_xp(user, 5, day)
    progress.award_xp(user, 5, day)  # stejný den série neroste
    assert (user.xp, user.streak) == (10, 1)
    progress.award_xp(user, 1, day + timedelta(days=1))
    assert user.streak == 2
    progress.award_xp(user, 1, day + timedelta(days=5))  # vynechané dny = série od začátku
    assert (user.streak, user.longest_streak) == (1, 2)


def test_leitner():
    today = date(2026, 11, 10)
    assert progress.next_review(1, True, today) == (2, today + timedelta(days=2))
    assert progress.next_review(5, True, today) == (5, today + timedelta(days=16))
    assert progress.next_review(4, False, today) == (1, today)


def test_clean_questions_drops_bad_and_shuffles():
    bad = ai.AIQuestion(subtopic=0, question="?", options=["a", "b", "c"], correct=0, explanation="")
    out_of_range = ai.AIQuestion(subtopic=5, question="?", options=list("abcd"), correct=0, explanation="")
    good = _q(0, 0)
    clean = ai._clean_questions([bad, out_of_range, good], 1)
    assert len(clean) == 1
    assert clean[0].options[clean[0].correct] == "správně"


# --- API ------------------------------------------------------------------------------------

def test_create_subject_makes_entry_test(client, auth_headers, fake_ai):
    subject = _create(client, auth_headers)
    assert fake_ai["plan"] == ("Fotosyntéza", "2. ročník")
    assert len(subject["subtopics"]) == 3
    assert subject["entry_quiz_id"] and not subject["entry_done"]

    quiz = client.get(f"/api/quizzes/{subject['entry_quiz_id']}", headers=auth_headers).json()
    assert len(quiz["questions"]) == 6
    assert quiz["result"] is None
    assert "correct" not in quiz["questions"][0]  # správná odpověď se před odevzdáním neposílá


def test_submit_entry_test_sets_mastery_and_xp(client, auth_headers, fake_ai):
    subject = _create(client, auth_headers)
    quiz_id = subject["entry_quiz_id"]
    quiz = client.get(f"/api/quizzes/{quiz_id}", headers=auth_headers).json()

    r = client.post(
        f"/api/quizzes/{quiz_id}/submit", json={"answers": _answers(quiz, {"Podtéma 0"})}, headers=auth_headers
    )
    assert r.status_code == 200, r.text
    result = r.json()
    assert (result["score"], result["total"], result["xp_gained"]) == (2, 6, 20)
    by_name = {s["name"]: s for s in result["subtopics"]}
    assert by_name["Podtéma 0"]["mastery"] == 100 and by_name["Podtéma 0"]["level"] == "strong"
    assert by_name["Podtéma 1"]["mastery"] == 0 and by_name["Podtéma 1"]["level"] == "weak"
    assert result["user"]["xp"] == 20 and result["user"]["streak"] == 1

    again = client.post(f"/api/quizzes/{quiz_id}/submit", json={"answers": {}}, headers=auth_headers)
    assert again.status_code == 409

    detail = client.get(f"/api/subjects/{subject['id']}", headers=auth_headers).json()
    assert detail["entry_done"] and detail["mastery"] == 33


def test_lesson_adapts_to_level_and_creates_flashcards(client, auth_headers, fake_ai):
    subject = _create(client, auth_headers)
    quiz_id = subject["entry_quiz_id"]
    quiz = client.get(f"/api/quizzes/{quiz_id}", headers=auth_headers).json()
    client.post(f"/api/quizzes/{quiz_id}/submit", json={"answers": _answers(quiz, set())}, headers=auth_headers)

    weak_id = subject["subtopics"][1]["id"]
    assert client.get(f"/api/subtopics/{weak_id}", headers=auth_headers).json()["content"] is None

    r = client.post(f"/api/subtopics/{weak_id}/lesson", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["content"].startswith("## Výklad")
    assert len(r.json()["flashcards"]) == 3
    assert fake_ai["lesson"]["level"] == "weak"
    assert len(fake_ai["lesson"]["mistakes"]) == 2  # AI dostane otázky, které uživatel pokazil

    # nový výklad nahradí starý, kartičky se nezdvojí
    r = client.post(f"/api/subtopics/{weak_id}/lesson", headers=auth_headers)
    assert len(r.json()["flashcards"]) == 3


def test_practice_quiz_updates_mastery(client, auth_headers, fake_ai):
    subject = _create(client, auth_headers)
    subtopic_id = subject["subtopics"][0]["id"]

    r = client.post(f"/api/subtopics/{subtopic_id}/quiz", headers=auth_headers)
    assert r.status_code == 201
    quiz_id = r.json()["quiz_id"]
    assert len(fake_ai["quiz"]["previous"]) == 2  # AI ví, na co už se ptala ve vstupním testu

    quiz = client.get(f"/api/quizzes/{quiz_id}", headers=auth_headers).json()
    assert quiz["kind"] == "practice" and quiz["subtopic_name"] == "Podtéma 0"
    result = client.post(
        f"/api/quizzes/{quiz_id}/submit", json={"answers": _answers(quiz, {"Podtéma 0"})}, headers=auth_headers
    ).json()
    assert result["score"] == 5 and result["subtopics"][0]["mastery"] == 100


def test_review_flashcards(client, auth_headers, fake_ai):
    subject = _create(client, auth_headers)
    client.post(f"/api/subtopics/{subject['subtopics'][0]['id']}/lesson", headers=auth_headers)

    due = client.get("/api/review", headers=auth_headers).json()
    assert due["due_total"] == 3
    card = due["cards"][0]
    assert card["subject_title"] == "Fotosyntéza"

    r = client.post(f"/api/flashcards/{card['id']}/review", json={"known": True}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["box"] == 2 and r.json()["xp_gained"] == 2
    assert client.get("/api/review", headers=auth_headers).json()["due_total"] == 2

    r = client.post(f"/api/flashcards/{due['cards'][1]['id']}/review", json={"known": False}, headers=auth_headers)
    assert r.json()["box"] == 1
    assert client.get("/api/review", headers=auth_headers).json()["due_total"] == 2  # neznámá zůstává na dnes


def test_other_user_cannot_access(client, auth_headers, fake_ai):
    subject = _create(client, auth_headers)
    client.post(f"/api/subtopics/{subject['subtopics'][0]['id']}/lesson", headers=auth_headers)
    card_id = client.get("/api/review", headers=auth_headers).json()["cards"][0]["id"]

    other = register(client, email="bob@example.com", name="Bob")
    assert client.get("/api/subjects", headers=other).json() == []
    assert client.get(f"/api/subjects/{subject['id']}", headers=other).status_code == 404
    assert client.get(f"/api/quizzes/{subject['entry_quiz_id']}", headers=other).status_code == 404
    assert client.post(f"/api/subtopics/{subject['subtopics'][0]['id']}/lesson", headers=other).status_code == 404
    assert client.post(f"/api/flashcards/{card_id}/review", json={"known": True}, headers=other).status_code == 404
    assert client.delete(f"/api/subjects/{subject['id']}", headers=other).status_code == 404
    assert client.get("/api/review", headers=other).json()["due_total"] == 0


def test_delete_subject_removes_everything(client, auth_headers, fake_ai):
    subject = _create(client, auth_headers)
    client.post(f"/api/subtopics/{subject['subtopics'][0]['id']}/lesson", headers=auth_headers)
    assert client.delete(f"/api/subjects/{subject['id']}", headers=auth_headers).status_code == 204
    assert client.get("/api/subjects", headers=auth_headers).json() == []
    assert client.get("/api/review", headers=auth_headers).json()["due_total"] == 0
    assert client.get(f"/api/quizzes/{subject['entry_quiz_id']}", headers=auth_headers).status_code == 404


def test_requires_login(client):
    assert client.get("/api/subjects").status_code == 401
    assert client.post("/api/subjects", json={"title": "Cokoli"}).status_code == 401


def test_validation_and_missing_api_key(client, auth_headers):
    r = client.post("/api/subjects", json={"title": "  a "}, headers=auth_headers)
    assert r.status_code == 422 and "Téma" in r.json()["detail"]
    # conftest nastavuje prázdný GEMINI_API_KEY → srozumitelná chyba místo pádu serveru
    r = client.post("/api/subjects", json={"title": "Fotosyntéza"}, headers=auth_headers)
    assert r.status_code == 503 and "GEMINI_API_KEY" in r.json()["detail"]
