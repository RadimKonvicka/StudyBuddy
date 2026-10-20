# 🎓 StudyBuddy: Inteligentní asistent pro přípravu na zkoušky

> **Závěrečný maturitní projekt** | **Autor:** Radim Konvička | **Instituce:** SŠPU Opava

---

## 🎯 Konkrétní záměr projektu

Hlavním záměrem projektu je **vytvořit funkční webovou aplikaci**, která automatizuje proces přípravy na testy a zkoušky. Aplikace řeší problém časově náročného ručního zpracovávání studijních materiálů.

**Cíle aplikace:**
1. **Transformace dokumentů:** Převést pasivní studijní podklady (PDF, DOCX, TXT) na interaktivní výukové pomůcky.
2. **Generování obsahu pomocí AI:** Automaticky vytvářet strukturovaná shrnutí, cvičné testy (ABC/D) a oboustranné kartičky (*flashcards*).
3. **Předcházení nedostatku podkladů:** Doplňovat chybějící informace vyhledáváním relevantních studijních zdrojů na webu.
4. **Efektivní učení:** Poskytnout studentovi přehledné rozhraní podporující metodu aktivního vybavování (*Active Recall*) a intervalového opakování (*Spaced Repetition*).

---

## 🔄 Kroky k dosažení cíle (Metodický postup)

Projekt je realizován v logických návazných krocích, které vedou od zpracování dat až po finální uživatelské rozhraní:

1. **Vstup a extrakce dat:**
   Uživatel nahraje soubor (PDF/DOCX/TXT). Backend aplikace soubor přijme a pomocí specializovaných knihoven z něj extrahuje čistý text bez balastu.
2. **Sémantické zpracování a AI Prompting:**
   Extrahovaný text je strukturován a odeslán přes API do jazykového modelu Google Gemini 1.5 Flash. Pomocí přesně definovaných výzev (*promptů*) AI vygeneruje odpověď v čistém datovém formátu JSON (otázky, možnosti, správné odpovědi, klíčové body).
3. **Uložení a správa dat:**
   Vygenerovaná data a metdata o dokumentech se uloží do relační databáze PostgreSQL pro rychlé načítání a dlouhodobou správu.
4. **Transformace do interaktivní podoby (LiaScript):**
   Backend připraví strukturovaná data ve formátu Markdown/LiaScript a předá je na frontend.
5. **Renderování na frontendu:**
   Astro frontend přijme data a zobrazení uživateli převede na interaktivní kvíz s vyhodnocením v reálném čase nebo na otáčecí studijní kartičky.

---

## 💻 Využitý software a vývojové nástroje

Pro vývoj, správy kódu a spuštění projektu jsou použity následující nástroje:

* **Vývojové prostředí (IDE):** Visual Studio Code (s rozšířeními pro Python, Astro a Git)
* **Verzovací systém:** Git & GitHub (správa zdrojového kódu a verzování)
* **Runtime & Balíčkovací správci:**
  * **Python 3.10+** & `pip` (backendová logika)
  * **Node.js** & `npm` (buildování frontendu a správce balíčků)
* **Databázový nástroj:** Supabase / PostgreSQL (případně SQLite pro lokální vývoj)
* **Grafika a Návrh UI:** Figma (návrh drátěných modelů a rozvržení stránek)
* **API klienti:** Postman / Bruno (testování REST API endpointů)

---

## 🛠 Technologický stack

| Část aplikace | Technologie | Zdůvodnění volby |
| :--- | :--- | :--- |
| **Frontend** | **Astro.build + Tailwind CSS** | **Astro** zajišťuje bleskovou rychlost a minimální JS bundle. **LiaScript** umožňuje transformaci Markdownu na interaktivní kurzy. **Tailwind CSS** garantuje čisté UI. |
| **Backend** | **Python (FastAPI)** | **Python** poskytuje nativní ekosystém pro práci s AI SDK, manipulaci s dokumenty (`pypdf`, `python-docx`) a tvorbu REST API endpoints. |
| **AI API** | **Google Gemini 1.5 Flash API** | Bezplatný vývojářský tier (až 15 požadavků/min), obrovské kontextové okno (zpracování dlouhých PDF) a výborná čeština. |
| **Databáze** | **PostgreSQL (Render)** | Relační databáze pro strukturované ukládání uživatelů, předmětů, extraktů z dokumentů a kvízů. |
| **Deployment** | **Vercel** (Frontend) + **Render.com** (Backend) | Bezplatné hostingové platformy s automatickým CI/CD přímo z GitHub repozitáře. |

---
