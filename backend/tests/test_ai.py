"""Testy spolehlivosti volání AI (app/ai.py).

Skutečné Gemini se nevolá: `genai.Client` nahradíme falešným klientem, kterému předem řekneme,
co má vracet (odpověď, nevalidní JSON, chybu 429…). Čekání mezi pokusy se v testech přeskočí.
"""
import pytest
from google.genai import errors as genai_errors
from google.genai import types

from app import ai
from app.config import get_settings

PRIMARY = "hlavni-model"
FALLBACK = "zalozni-model"


def ok_response(text: str, finish=types.FinishReason.STOP) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=[types.Part(text=text)]),
                finish_reason=finish,
            )
        ]
    )


def api_error(code: int, message: str = "chyba") -> genai_errors.APIError:
    cls = genai_errors.ServerError if code >= 500 else genai_errors.ClientError
    return cls(code, {"error": {"code": code, "message": message, "status": "X"}})


VALID_QUIZ = (
    '{"questions": ['
    + ",".join(
        f'{{"subtopic": 0, "question": "Otázka {i}", "options": ["a{i}", "b{i}", "c{i}", "d{i}"],'
        f' "correct": 1, "explanation": "Protože."}}'
        for i in range(5)
    )
    + "]}"
)


class FakeClient:
    """Falešný genai.Client. `script` = seznam výsledků, které postupně vrací (nebo vyhazuje)."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []  # (model, config) každého volání
        self.models = self

    def generate_content(self, model, contents, config):
        self.calls.append((model, config))
        outcome = self.script.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def fake_gemini(monkeypatch):
    """Vrátí funkci, která nastaví, co bude falešné Gemini odpovídat."""
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", "testovaci-klic")
    monkeypatch.setattr(settings, "gemini_model", PRIMARY)
    monkeypatch.setattr(settings, "gemini_fallback_model", FALLBACK)
    monkeypatch.setattr(settings, "ai_retries", 3)
    waits = []
    monkeypatch.setattr(ai, "_sleep", waits.append)

    def setup(*script):
        client = FakeClient(script)
        client.waits = waits
        monkeypatch.setattr(ai.genai, "Client", lambda **kwargs: client)
        return client

    return setup


def ask():
    return ai.generate_quiz("Fyzika", "", "Pohyb", "rychlost a zrychlení", None, [])


def test_validni_json(fake_gemini):
    client = fake_gemini(ok_response(VALID_QUIZ))
    questions = ask()
    assert len(questions) == 5
    assert all(len(q.options) == 4 for q in questions)
    # správná odpověď zůstane správná i po zamíchání možností
    assert all(q.options[q.correct].startswith("b") for q in questions)
    assert [m for m, _ in client.calls] == [PRIMARY]


def test_nevalidni_json_se_jednou_zopakuje(fake_gemini):
    client = fake_gemini(ok_response('{"questions": [ {"useknuty'), ok_response(VALID_QUIZ))
    assert len(ask()) == 5
    assert [m for m, _ in client.calls] == [PRIMARY, PRIMARY]


def test_dvakrat_nevalidni_json_prepne_na_zalozni_model(fake_gemini):
    client = fake_gemini(ok_response("nesmysl"), ok_response("{}"), ok_response(VALID_QUIZ))
    assert len(ask()) == 5
    assert [m for m, _ in client.calls] == [PRIMARY, PRIMARY, FALLBACK]


def test_chyba_429_pocka_a_zkusi_znovu(fake_gemini):
    client = fake_gemini(api_error(429), api_error(503), ok_response(VALID_QUIZ))
    assert len(ask()) == 5
    assert [m for m, _ in client.calls] == [PRIMARY, PRIMARY, PRIMARY]
    assert len(client.waits) == 2
    assert client.waits[1] > client.waits[0]  # čekání se prodlužuje


def test_trvala_chyba_429_prepne_na_zalozni_model(fake_gemini):
    client = fake_gemini(api_error(429), api_error(429), api_error(429), ok_response(VALID_QUIZ))
    assert len(ask()) == 5
    assert [m for m, _ in client.calls] == [PRIMARY] * 3 + [FALLBACK]


def test_nedostupny_model_404_prepne_na_zalozni_bez_cekani(fake_gemini):
    client = fake_gemini(api_error(404, "no longer available"), ok_response(VALID_QUIZ))
    assert len(ask()) == 5
    assert [m for m, _ in client.calls] == [PRIMARY, FALLBACK]
    assert client.waits == []


def test_nepouzitelny_obsah_prepne_na_zalozni_model(fake_gemini):
    # validní JSON, ale bez otázek – to kontroluje funkce check v generate_quiz
    client = fake_gemini(ok_response('{"questions": []}'), ok_response('{"questions": []}'), ok_response(VALID_QUIZ))
    assert len(ask()) == 5
    assert [m for m, _ in client.calls] == [PRIMARY, PRIMARY, FALLBACK]


def test_spatny_klic_nezkousi_zalozni_model(fake_gemini):
    client = fake_gemini(api_error(403, "API key not valid"))
    with pytest.raises(ai.AIError) as exc:
        ask()
    assert "API klíč" in exc.value.message
    assert len(client.calls) == 1


def test_kdyz_selze_vse_vrati_ceskou_hlasku(fake_gemini):
    fake_gemini(*[api_error(503, "overloaded")] * 6)
    with pytest.raises(ai.AIError) as exc:
        ask()
    assert exc.value.status == 503
    assert "přetížená" in exc.value.message


def test_zablokovana_odpoved(fake_gemini):
    blocked = ok_response("", finish=types.FinishReason.SAFETY)
    fake_gemini(blocked, blocked, blocked, blocked)
    with pytest.raises(ai.AIError) as exc:
        ask()
    assert "bezpečnostní filtr" in exc.value.message


def test_bez_klice_srozumitelna_chyba(monkeypatch):
    monkeypatch.setattr(get_settings(), "gemini_api_key", "")
    with pytest.raises(ai.AIError) as exc:
        ask()
    assert exc.value.status == 503
    assert "GEMINI_API_KEY" in exc.value.message


def test_novy_model_dostane_thinking_level_stary_thinking_budget():
    new = ai._config("gemini-3.5-flash-lite", ai.AIQuiz, 30)
    old = ai._config("gemini-2.5-flash", ai.AIQuiz, 30)
    assert new.thinking_config.thinking_level == types.ThinkingLevel.MINIMAL
    assert new.thinking_config.thinking_budget is None
    assert old.thinking_config.thinking_budget == 0


def test_plan_bez_vstupniho_testu(fake_gemini):
    # AI otázky stejně poslala – zahodíme je; k platnému plánu stačí podtémata
    plan_json = (
        '{"subtopics": [{"name": "Základy", "description": "a"}, {"name": "Pokročilé", "description": "b"}],'
        + VALID_QUIZ[1:]
    )
    fake_gemini(ok_response(plan_json))
    plan = ai.generate_plan("Fotosyntéza", "", entry_quiz=False)
    assert [s.name for s in plan.subtopics] == ["Základy", "Pokročilé"] and plan.questions == []

    fake_gemini(ok_response('{"subtopics": [{"name": "Základy", "description": "a"}, {"name": "B", "description": "b"}]}'))
    assert len(ai.generate_plan("Fotosyntéza", "", entry_quiz=False).subtopics) == 2
