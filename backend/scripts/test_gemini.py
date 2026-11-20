"""Diagnostika spojení s Google Gemini.

Spouštěj ze složky backend (kvůli souboru .env):
    python scripts/test_gemini.py
    python scripts/test_gemini.py --model gemini-3.5-flash-lite   # vyzkoušet jiný model

Nastavení se čte stejně jako v aplikaci (app.config.Settings), takže skript testuje přesně to,
co používá backend. Hodnota API klíče se nikdy nevypisuje – v chybových hláškách se nahradí ***.
"""
import argparse
import os
import platform
import sys
import time
import traceback
from pathlib import Path

# aby šlo importovat balíček app, i když skript leží ve složce scripts
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# Windows konzole někdy neumí češtinu
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

KEY = ""


def hide(text) -> str:
    """Pro jistotu odstraní klíč z čehokoli, co se vypisuje."""
    text = str(text)
    if KEY:
        text = text.replace(KEY, "***")
    return text


def section(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def print_error(err: Exception) -> None:
    print(f"  CHYBA typ:     {type(err).__module__}.{type(err).__name__}")
    for attr in ("code", "status", "message"):
        if hasattr(err, attr):
            print(f"  CHYBA {attr + ':':<8} {hide(getattr(err, attr))}")
    details = getattr(err, "details", None)
    if details:
        print(f"  CHYBA detail:  {hide(details)[:1500]}")
    print("  --- traceback (posledních 6 řádků) ---")
    lines = traceback.format_exception(type(err), err, err.__traceback__)
    for line in "".join(lines).strip().splitlines()[-6:]:
        print("  " + hide(line))


def print_response(response) -> None:
    """Vypíše, proč model skončil (STOP, SAFETY, MAX_TOKENS…) a jestli nebyl dotaz zablokován."""
    feedback = getattr(response, "prompt_feedback", None)
    if feedback:
        print(f"  prompt_feedback: {hide(feedback)}")
    for i, cand in enumerate(getattr(response, "candidates", None) or []):
        print(f"  kandidát {i}: finish_reason = {getattr(cand, 'finish_reason', None)}")
    if not getattr(response, "candidates", None):
        print("  (odpověď nemá žádné kandidáty – typicky blokace bezpečnostním filtrem)")
    usage = getattr(response, "usage_metadata", None)
    if usage:
        print(f"  tokeny: vstup={getattr(usage, 'prompt_token_count', None)}, "
              f"výstup={getattr(usage, 'candidates_token_count', None)}, "
              f"přemýšlení={getattr(usage, 'thoughts_token_count', None)}")
    text = response.text if getattr(response, "candidates", None) else None
    print(f"  text ({len(text or '')} znaků): {hide((text or '')[:400])!r}")


def run(name: str, fn) -> bool:
    print(f"\n>>> {name}")
    start = time.perf_counter()
    try:
        fn()
        print(f"  OK ({time.perf_counter() - start:.1f} s)")
        return True
    except Exception as err:  # chceme vidět úplně každou chybu
        print(f"  SELHALO po {time.perf_counter() - start:.1f} s")
        print_error(err)
        return False


def main() -> int:
    global KEY
    parser = argparse.ArgumentParser(description="Diagnostika Gemini")
    parser.add_argument("--model", help="použít jiný model než GEMINI_MODEL z .env")
    args = parser.parse_args()

    section("1) Prostředí")
    print(f"  Python:            {sys.version.split()[0]} ({platform.system()})")
    print(f"  Pracovní složka:   {os.getcwd()}")
    print(f"  Soubor .env:       {'nalezen' if Path('.env').is_file() else 'NENALEZEN v pracovní složce'}")
    try:
        from importlib.metadata import version
        print(f"  google-genai:      {version('google-genai')}")
        print(f"  pydantic:          {version('pydantic')}")
    except Exception as err:
        print(f"  google-genai:      NENÍ NAINSTALOVÁNO ({err})")
        return 1
    print(f"  GOOGLE_GENAI_API_VERSION: {os.environ.get('GOOGLE_GENAI_API_VERSION') or '(nenastaveno)'}")

    section("2) Nastavení aplikace (app.config.Settings)")
    try:
        from app.config import get_settings
        settings = get_settings()
    except Exception as err:
        print("  Nastavení se nepodařilo načíst:")
        print_error(err)
        return 1

    KEY = settings.gemini_api_key or ""
    model = args.model or settings.gemini_model
    print(f"  ENVIRONMENT:       {settings.environment}")
    print(f"  GEMINI_MODEL:      {settings.gemini_model!r}")
    print(f"  testovaný model:   {model!r}")
    print(f"  klíč nastaven:     {'ano' if KEY else 'NE'}")
    if KEY:
        # jen kontroly tvaru – hodnota se nevypisuje
        wrapped = KEY != KEY.strip(" \"'")
        print(f"  klíč má mezery/uvozovky na okraji: {'ANO (chyba!)' if wrapped else 'ne'}")
        print(f"  klíč začíná 'AIza': {'ano' if KEY.startswith('AIza') else 'ne'}")
    if os.environ.get("GEMINI_API_KEY") is not None:
        print("  pozn.: GEMINI_API_KEY je nastaven i v proměnných prostředí systému (má přednost před .env)")
    if not KEY:
        print("\n  Bez klíče nemá smysl pokračovat. Doplň GEMINI_API_KEY do backend/.env.")
        return 1

    from pydantic import BaseModel
    from google import genai
    from google.genai import types

    class Pokus(BaseModel):
        mesto: str
        pocet_obyvatel: int
        zajimavosti: list[str]

    client = genai.Client(api_key=KEY, http_options=types.HttpOptions(timeout=60_000))
    results = {}

    section("3) Testy")

    def model_info():
        info = client.models.get(model=model)
        print(f"  název: {info.name}, zobrazený: {getattr(info, 'display_name', None)}")
        print(f"  max. vstup tokenů: {getattr(info, 'input_token_limit', None)}, "
              f"max. výstup: {getattr(info, 'output_token_limit', None)}")

    results["A model existuje"] = run("A) Existuje model a mám k němu přístup? (models.get)", model_info)

    def simple_text():
        r = client.models.generate_content(model=model, contents="Odpověz jedním slovem: hlavní město Česka?")
        print_response(r)
        if not r.text:
            raise RuntimeError("prázdná odpověď")

    results["B text"] = run("B) Jednoduchý textový dotaz", simple_text)

    def json_like_app():
        # stejná konfigurace, jakou teď používá app/ai.py
        config = types.GenerateContentConfig(
            system_instruction="Odpovídáš pouze ve formátu JSON podle zadaného schématu.",
            response_mime_type="application/json",
            response_schema=Pokus,
            temperature=0.7,
        )
        if "flash" in model:
            config.thinking_config = types.ThinkingConfig(thinking_budget=0)
        r = client.models.generate_content(model=model, contents="Popiš město Opava.", config=config)
        print_response(r)
        print(f"  validace Pydantic: {Pokus.model_validate_json(r.text or '')}")

    results["C JSON jako aplikace"] = run(
        "C) JSON výstup PŘESNĚ jako aplikace (response_schema + temperature + thinking_budget=0)", json_like_app
    )

    def json_plain():
        # minimální varianta bez temperature a thinking – pro porovnání s testem C
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=Pokus.model_json_schema(),
        )
        r = client.models.generate_content(model=model, contents="Popiš město Opava.", config=config)
        print_response(r)
        print(f"  validace Pydantic: {Pokus.model_validate_json(r.text or '')}")

    results["D JSON minimální"] = run(
        "D) JSON výstup minimálně (response_json_schema, bez temperature a thinking)", json_plain
    )

    section("4) Souhrn")
    for name, ok in results.items():
        print(f"  {'OK     ' if ok else 'SELHALO'}  {name}")
    print("\nZkopíruj celý výstup od řádku '1) Prostředí' až sem.")
    return 0 if all(results.values()) else 2


if __name__ == "__main__":
    sys.exit(main())
