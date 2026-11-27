"""Testy tříd: založení, připojení kódem, role a hlavně kdo smí vidět čí výsledky."""
import pytest

from tests.conftest import register
from tests.test_learning import _answers, _create, fake_ai  # noqa: F401  (fixture)


@pytest.fixture
def people(client):
    """Učitelka, dva žáci a cizí člověk mimo třídu."""
    return dict(
        teacher=register(client, "ucitelka@example.com", name="Paní učitelka"),
        ana=register(client, "ana@example.com", name="Ana"),
        ben=register(client, "ben@example.com", name="Ben"),
        stranger=register(client, "cizi@example.com", name="Cizí"),
    )


def _group(client, people, name="4.A – biologie"):
    r = client.post("/api/groups", json={"name": name}, headers=people["teacher"])
    assert r.status_code == 201, r.text
    return r.json()


def _join(client, headers, code):
    return client.post("/api/groups/join", json={"code": code}, headers=headers)


def _uid(client, headers):
    return client.get("/api/auth/me", headers=headers).json()["id"]


def test_zalozeni_a_pripojeni_kodem(client, people):
    group = _group(client, people)
    assert group["role"] == "teacher" and len(group["join_code"]) == 6
    assert [t["display_name"] for t in group["teachers"]] == ["Paní učitelka"]

    # kód jde zadat malými písmeny a s pomlčkou
    code = group["join_code"]
    r = _join(client, people["ana"], f" {code[:3].lower()}-{code[3:]} ")
    assert r.status_code == 200, r.text
    joined = r.json()
    assert joined["role"] == "student"
    assert joined["join_code"] is None and joined["students"] == []  # žák nevidí kód ani spolužáky

    assert _join(client, people["ana"], code).status_code == 409  # podruhé ne
    assert _join(client, people["ben"], "XXXXXX").status_code == 404

    mine = client.get("/api/groups", headers=people["ana"]).json()
    assert [g["name"] for g in mine] == ["4.A – biologie"]
    assert client.get("/api/groups", headers=people["stranger"]).json() == []


def test_prazdny_nazev_ma_ceskou_hlasku(client, people):
    r = client.post("/api/groups", json={"name": "   "}, headers=people["teacher"])
    assert r.status_code == 422 and "Název třídy" in r.json()["detail"]


def test_ucitel_vidi_prehled_zaku(client, people, fake_ai):
    group = _group(client, people)
    _join(client, people["ana"], group["join_code"])

    subject = _create(client, people["ana"])
    quiz = client.get(f"/api/quizzes/{subject['entry_quiz_id']}", headers=people["ana"]).json()
    client.post(
        f"/api/quizzes/{quiz['id']}/submit", json={"answers": _answers(quiz, {"Podtéma 0"})}, headers=people["ana"]
    )

    detail = client.get(f"/api/groups/{group['id']}", headers=people["teacher"]).json()
    assert detail["student_count"] == 1
    row = detail["students"][0]
    assert row["display_name"] == "Ana" and row["subject_count"] == 1 and row["quizzes_done"] == 1
    assert row["mastery"] == 33 and row["xp"] == 20

    ana_id = row["user_id"]
    student = client.get(f"/api/groups/{group['id']}/students/{ana_id}", headers=people["teacher"]).json()
    assert student["subjects"][0]["title"] == "Fotosyntéza"
    assert [s["mastery"] for s in student["subjects"][0]["subtopics"]] == [100, 0, 0]

    # učitel vidí i konkrétní odpovědi žáka
    r = client.get(f"/api/groups/{group['id']}/students/{ana_id}/quizzes/{quiz['id']}", headers=people["teacher"])
    assert r.status_code == 200
    assert r.json()["score"] == 2 and sum(not q["is_correct"] for q in r.json()["questions"]) == 4

    # nedokončený test ještě ukázat nejde
    practice = client.post(f"/api/subtopics/{subject['subtopics'][1]['id']}/quiz", headers=people["ana"]).json()
    r = client.get(
        f"/api/groups/{group['id']}/students/{ana_id}/quizzes/{practice['quiz_id']}", headers=people["teacher"]
    )
    assert r.status_code == 409


def test_kdo_nesmi_videt_vysledky(client, people, fake_ai):
    group = _group(client, people)
    _join(client, people["ana"], group["join_code"])
    _join(client, people["ben"], group["join_code"])
    ana_id, ben_id = _uid(client, people["ana"]), _uid(client, people["ben"])
    subject = _create(client, people["ana"])
    gid = group["id"]

    # cizí člověk o třídě ani neví
    assert client.get(f"/api/groups/{gid}", headers=people["stranger"]).status_code == 404
    assert client.get(f"/api/groups/{gid}/students/{ana_id}", headers=people["stranger"]).status_code == 404

    # spolužák výsledky nevidí a správu dělat nesmí
    assert client.get(f"/api/groups/{gid}/students/{ana_id}", headers=people["ben"]).status_code == 403
    assert client.post(f"/api/groups/{gid}/code", headers=people["ben"]).status_code == 403
    assert client.delete(f"/api/groups/{gid}/members/{ana_id}", headers=people["ben"]).status_code == 403
    assert client.delete(f"/api/groups/{gid}", headers=people["ben"]).status_code == 403

    # učitel jiné třídy nevidí žáky této třídy
    other = register(client, "jiny@example.com", name="Jiný učitel")
    other_gid = client.post("/api/groups", json={"name": "Jiná"}, headers=other).json()["id"]
    assert client.get(f"/api/groups/{other_gid}/students/{ana_id}", headers=other).status_code == 404

    # učitel nevidí test, který žákovi nepatří, a pořád nemůže nic měnit přes běžné API
    r = client.get(
        f"/api/groups/{gid}/students/{ben_id}/quizzes/{subject['entry_quiz_id']}", headers=people["teacher"]
    )
    assert r.status_code == 404
    assert client.get(f"/api/subjects/{subject['id']}", headers=people["teacher"]).status_code == 404
    assert client.delete(f"/api/subjects/{subject['id']}", headers=people["teacher"]).status_code == 404


def test_vice_ucitelu_a_posledni_ucitel(client, people):
    group = _group(client, people)
    gid = group["id"]
    _join(client, people["ana"], group["join_code"])
    teacher_id, ana_id = _uid(client, people["teacher"]), _uid(client, people["ana"])

    # posledního učitele nejde sesadit ani nechat odejít
    r = client.patch(f"/api/groups/{gid}/members/{teacher_id}", json={"role": "student"}, headers=people["teacher"])
    assert r.status_code == 409
    assert client.delete(f"/api/groups/{gid}/members/{teacher_id}", headers=people["teacher"]).status_code == 409

    # povýšení žákyně na učitelku – teď vidí kód a přehled
    r = client.patch(f"/api/groups/{gid}/members/{ana_id}", json={"role": "teacher"}, headers=people["teacher"])
    assert r.status_code == 200 and len(r.json()["teachers"]) == 2
    as_ana = client.get(f"/api/groups/{gid}", headers=people["ana"]).json()
    assert as_ana["role"] == "teacher" and as_ana["join_code"]

    # neplatná role
    r = client.patch(f"/api/groups/{gid}/members/{ana_id}", json={"role": "admin"}, headers=people["teacher"])
    assert r.status_code == 422

    # původní učitelka teď může odejít
    assert client.delete(f"/api/groups/{gid}/members/{teacher_id}", headers=people["teacher"]).status_code == 204
    assert client.get(f"/api/groups/{gid}", headers=people["teacher"]).status_code == 404


def test_odchod_vyhozeni_novy_kod_smazani(client, people, fake_ai):
    group = _group(client, people)
    gid, code = group["id"], group["join_code"]
    _join(client, people["ana"], code)
    _join(client, people["ben"], code)
    ana_id, ben_id = _uid(client, people["ana"]), _uid(client, people["ben"])
    subject = _create(client, people["ana"])

    # žák sám odejde
    assert client.delete(f"/api/groups/{gid}/members/{ben_id}", headers=people["ben"]).status_code == 204
    assert client.get("/api/groups", headers=people["ben"]).json() == []

    # učitel vyhodí žákyni → už nevidí její výsledky
    assert client.delete(f"/api/groups/{gid}/members/{ana_id}", headers=people["teacher"]).status_code == 204
    assert client.get(f"/api/groups/{gid}/students/{ana_id}", headers=people["teacher"]).status_code == 404

    # nový kód – starý přestane platit
    new = client.post(f"/api/groups/{gid}/code", headers=people["teacher"]).json()["join_code"]
    assert new != code
    assert _join(client, people["ben"], code).status_code == 404
    assert _join(client, people["ben"], new).status_code == 200

    # smazání třídy nesmaže témata žáků
    assert client.delete(f"/api/groups/{gid}", headers=people["teacher"]).status_code == 204
    assert client.get("/api/groups", headers=people["ben"]).json() == []
    assert client.get(f"/api/subjects/{subject['id']}", headers=people["ana"]).status_code == 200
