from agents import ResearchAgent, SummaryAgent, QuizAgent, FlashcardAgent

MACROS = {
    "full": {
        "label": "Kompletní studijní set",
        "desc": "Stručný přehled + testová část (10 otázek) + oboustranné kartičky (15 ks). Krátké podklady systém automaticky dopočítá z webu.",
        "summary": True, "quiz": 10, "cards": 15, "research_below": 3000,
    },
    "quick": {
        "label": "Rychlý přehled látky",
        "desc": "Souhrnná výpska + 10 kartiček k procvičení. Vhodné pro expresní zopakování.",
        "summary": True, "quiz": 0, "cards": 10, "research_below": 0,
    },
    "exam": {
        "label": "Simulovaný test",
        "desc": "Generování sady 20 testových otázek bez doplňujících materiálů.",
        "summary": False, "quiz": 20, "cards": 0, "research_below": 0,
    },
}


def run_macro(key: str, text: str) -> dict:
    """Spustí zvolené makro a postupné zpracování přes agentické rozhraní."""
    cfg = MACROS[key]
    log = []
    work_text = text

    # Kroky agentu: hledani doplnovacich podkladu u txt
    if len(text) < cfg["research_below"]:
        agent = ResearchAgent()
        extra = agent.run(text)
        work_text = text + "\n\n--- DOPLNĚNO Z WEBU ---\n" + extra
        log.append(agent.name)

    result = {"summary": "", "questions": [], "cards": [], "log": log, "text": work_text}

    # generovani jednotlivych casti - konfigurace
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
