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

## 📌 Aktuální stav

| Oblast | Stav |
| :--- | :--- |
| Registrace, přihlášení, odhlášení (Argon2 + JWT) | ✅ Hotovo |
| Ochrana proti hádání hesel (max. 8 neúspěšných pokusů za 10 min z jedné IP) | ✅ Hotovo |
| Přehled (XP, série dní, kartičky k opakování, seznam témat), světlý/tmavý režim | ✅ Hotovo |
| Zadání tématu → AI vytvoří podtémata a vstupní test | ✅ Hotovo |
| Vyhodnocení testu a zvládnutí podtémat (slabé / částečně / zvládnuté) | ✅ Hotovo |
| Výklad a kartičky na míru podle úrovně a chyb v testech (Gemini) | ✅ Hotovo |
| Procvičovací testy k podtématům | ✅ Hotovo |
| Opakování kartiček (Leitnerův systém, *Spaced Repetition*) | ✅ Hotovo |
| Gamifikace (XP, série dní) | ✅ Hotovo |
| Automatické testy backendu (pytest, AI v testech nahrazená) | ✅ Hotovo |
| Nahrávání vlastních dokumentů (PDF/DOCX/TXT) | 🔜 Plánováno |
| Nasazení (Vercel + Render) | 🔜 Plánováno |

> Pro generování obsahu je potřeba klíč Google Gemini v `backend/.env` (`GEMINI_API_KEY`), získáš ho na https://aistudio.google.com/apikey.

---

## 🔄 Kroky k dosažení cíle (Metodický postup)

Projekt je realizován v logických návazných krocích, které vedou od zpracování dat až po finální uživatelské rozhraní:

1. **Vstup a extrakce dat:**
   Uživatel nahraje soubor (PDF/DOCX/TXT). Backend aplikace soubor přijme a pomocí knihoven `pypdf` a `python-docx` z něj extrahuje čistý text bez balastu.
2. **Sémantické zpracování a AI Prompting:**
   Extrahovaný text je odeslán přes API do jazykového modelu Google Gemini 2.5 Flash. Pomocí přesně definovaných výzev (*promptů*) AI vygeneruje odpověď ve formátu JSON (otázky, možnosti, správné odpovědi, klíčové body).
3. **Uložení a správa dat:**
   Vygenerovaná data a metadata o dokumentech se uloží do relační databáze (PostgreSQL v produkci, SQLite při lokálním vývoji). Každý záznam patří konkrétnímu přihlášenému uživateli.
4. **Předání dat frontendu:**
   Backend poskytuje data přes REST API (JSON). Textový obsah od AI (např. shrnutí) je ve formátu Markdown.
5. **Renderování na frontendu:**
   Astro frontend data načte v prohlížeči, Markdown převede na HTML (knihovna `marked`, vždy vyčištěné přes `DOMPurify`) a zobrazí je jako interaktivní kvíz s vyhodnocením v reálném čase nebo jako otáčecí studijní kartičky.

---

## 💻 Využitý software a vývojové nástroje

Pro vývoj, správu kódu a spuštění projektu jsou použity následující nástroje:

* **Vývojové prostředí (IDE):** Visual Studio Code (s rozšířeními pro Python, Astro a Git)
* **Verzovací systém:** Git & GitHub (správa zdrojového kódu a verzování)
* **Runtime & Balíčkovací správci:**
  * **Python 3.10+** & `pip` (backendová logika)
  * **Node.js 22+** & `npm` (buildování frontendu a správce balíčků)
* **Databáze:** PostgreSQL (Render / Supabase), SQLite pro lokální vývoj
* **Testování:** `pytest` (automatické testy backendu)
* **Grafika a Návrh UI:** Figma (návrh drátěných modelů a rozvržení stránek)
* **API klienti:** Postman / Bruno (testování REST API endpointů), případně vestavěná dokumentace FastAPI na `/docs`

---

## 🛠 Technologický stack

| Část aplikace | Technologie | Zdůvodnění volby |
| :--- | :--- | :--- |
| **Frontend** | **Astro + Tailwind CSS 4** | **Astro** ve statickém režimu zajišťuje bleskovou rychlost a minimální JS bundle. **marked + DOMPurify** bezpečně převádí Markdown od AI na HTML. **Tailwind CSS** garantuje čisté UI se světlým i tmavým režimem. |
| **Backend** | **Python (FastAPI + SQLAlchemy 2.0)** | **Python** poskytuje nativní ekosystém pro práci s AI SDK, manipulaci s dokumenty (`pypdf`, `python-docx`) a tvorbu REST API endpointů. |
| **Zabezpečení** | **Argon2 + JWT** | Hesla se ukládají pouze jako hash Argon2id, přihlášení drží podepsaný JWT token posílaný v hlavičce `Authorization`. |
| **AI API** | **Google Gemini 2.5 Flash** (`google-genai`) | Bezplatný vývojářský tier, obrovské kontextové okno (zpracování dlouhých PDF) a výborná čeština. |
| **Databáze** | **PostgreSQL (Render)** | Relační databáze pro strukturované ukládání uživatelů, předmětů, extraktů z dokumentů a kvízů. |
| **Deployment** | **Vercel** (Frontend) + **Render.com** (Backend) | Bezplatné hostingové platformy s automatickým CI/CD přímo z GitHub repozitáře. |

---

## 🚀 Spuštění lokálně

### Backend (složka `backend/`)

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # doplň SECRET_KEY a GEMINI_API_KEY
uvicorn app.main:app --reload
```

API běží na `http://localhost:8000`, dokumentace na `http://localhost:8000/docs`.

Testy: `pytest`

### Frontend (složka `frontend/`)

```bash
npm install
cp .env.example .env             # PUBLIC_API_URL=http://localhost:8000
npm run dev
```

Aplikace běží na `http://localhost:4321`.

### Proměnné prostředí

Všechny tajné údaje (API klíč, heslo k databázi, `SECRET_KEY`) patří do souboru `.env`, který se nikdy necommituje. Popis všech proměnných je v `backend/.env.example` a `frontend/.env.example`. V produkci (`ENVIRONMENT=production`) backend odmítne nastartovat s výchozím nebo krátkým `SECRET_KEY`.
