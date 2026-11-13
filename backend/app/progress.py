"""Logika učení: úroveň zvládnutí podtématu, XP a série dní, Leitnerův systém kartiček.

Je to čistý Python bez databáze a bez AI – proto se dá snadno otestovat i vysvětlit.
"""
from datetime import date, timedelta

from .models import User

# --- Zvládnutí podtématu (mastery 0–100) ---------------------------------------------------

WEAK_BELOW = 50  # pod 50 % = slabé
STRONG_FROM = 80  # od 80 % = zvládnuté


def mastery_level(mastery: int | None) -> str | None:
    """Převede procenta na slovní úroveň, podle které frontend barví a AI volí hloubku výkladu."""
    if mastery is None:
        return None
    if mastery < WEAK_BELOW:
        return "weak"
    if mastery < STRONG_FROM:
        return "mid"
    return "strong"


def update_mastery(old: int | None, correct: int, total: int) -> int:
    """Nové zvládnutí po testu.

    Poprvé = rovnou výsledek testu. Potom vážený průměr (60 % nový test, 40 % dosavadní stav),
    aby jeden šťastný nebo nepovedený test nezměnil úroveň skokem.
    """
    score = round(correct / total * 100) if total else 0
    if old is None:
        return score
    return round(0.4 * old + 0.6 * score)


# --- XP a série dní -----------------------------------------------------------------------

XP_CORRECT_ANSWER = 10
XP_CARD_KNOWN = 2
XP_CARD_UNKNOWN = 1


def award_xp(user: User, xp: int, today: date | None = None) -> None:
    """Připíše XP a aktualizuje sérii dní (streak) – učil ses včera i dnes = série roste."""
    today = today or date.today()
    last = user.last_active_date
    if last != today:
        user.streak = (user.streak or 0) + 1 if last == today - timedelta(days=1) else 1
        user.longest_streak = max(user.longest_streak or 0, user.streak)
        user.last_active_date = today
    user.xp = (user.xp or 0) + xp


# --- Leitnerův systém ---------------------------------------------------------------------
# Kartičky jsou v krabičkách 1–5. Když ji umíš, posune se o krabičku výš a ukáže se až za delší
# dobu. Když ji neumíš, vrátí se do krabičky 1 a opakuje se ještě dnes.

INTERVAL_DAYS = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16}
MAX_BOX = 5


def next_review(box: int, known: bool, today: date | None = None) -> tuple[int, date]:
    """Vrátí (nová krabička, datum dalšího opakování)."""
    today = today or date.today()
    if not known:
        return 1, today
    new_box = min(box + 1, MAX_BOX)
    return new_box, today + timedelta(days=INTERVAL_DAYS[new_box])
