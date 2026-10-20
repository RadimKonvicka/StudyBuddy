from agents import ResearchAgent, SummaryAgent, QuizAgent, FlashcardAgent

MACROS = {
    "full": {
        "label": "Kompletní balíček",
        "desc": "Shrnutí + test (10 otázek) + kartičky (15). Krátké texty se doplní z webu.",
        "summary": True, "quiz": 10, "cards": 15, "research_below": 3000,
    },
    "quick": {
        "label": "Rychlé opakování",
        "desc": "Shrnutí + 10 kartiček. Nejrychlejší.",
        "summary": True, "quiz": 0, "cards": 10, "research_below": 0,
    },
    "exam": {
        "label": "Zkouška (jen test)",
        "desc": "20 testových otázek, nic dalšího.",
        "summary": False, "quiz": 20, "cards": 0, "research_below": 0,
    },
}


def run_macro(key: str, text: str) -> dict:
    cfg = MACROS[key]
    log = []
    work_text = text

    # 1) Výzkumník: jen když je text krátký
    if len(text) < cfg["research_below"]:
        agent = ResearchAgent()
        extra = agent.run(text)
        work_text = text + "\n\n--- DOPLNĚNO Z WEBU ---\n" + extra
        log.append(agent.name)

    result = {"summary": "", "questions": [], "cards": [], "log": log, "text": work_text}

    if cfg["summary"]:
        a = SummaryAgent()
        result["summary"] = a.run(work_text)
        log.append(a.name)
    if cfg["quiz"]:
        a = QuizAgent()
        result["questions"] = a.run(work_text, cfg["quiz"])
        log.append(a.name)
    if cfg["cards"]:
        a = FlashcardAgent()
        result["cards"] = a.run(work_text, cfg["cards"])
        log.append(a.name)
    return result