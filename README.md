# 🎓 StudyBuddy: Inteligentní asistent pro přípravu na zkoušky

> **Závěrečný maturitní projekt** | **Autor:** Radim Konvička | **Instituce:** SŠPU Opava

---

## 🎯 Konkrétní záměr projektu

Hlavním záměrem projektu je **vytvořit funkční webovou aplikaci**, která automatizuje proces přípravy na testy a zkoušky. Aplikace řeší problém časově náročného ručního zpracovávání studijních materiálů.

**Cíle aplikace:**
1. **Transformace dokumentů:** Převést pasivní studijní podklady (PDF, DOCX, PPTX, TXT) na interaktivní výukové pomůcky.
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
| Možnost „Začínám od nuly“ – bez vstupního testu, rovnou výklad od základů a testy až potom | ✅ Hotovo |
| Vyhodnocení testu a zvládnutí podtémat (slabé / částečně / zvládnuté) | ✅ Hotovo |
| Výklad a kartičky na míru podle úrovně a chyb v testech (Gemini) | ✅ Hotovo |
| Procvičovací testy k podtématům | ✅ Hotovo |
| Opakování kartiček (Leitnerův systém, *Spaced Repetition*) | ✅ Hotovo |
| Gamifikace (XP, série dní) | ✅ Hotovo |
| Třídy: učitel založí třídu, žáci se připojí kódem, učitel vidí jejich témata, zvládnutí a odpovědi v testech (víc učitelů v jedné třídě) | ✅ Hotovo |
| Automatické testy backendu (pytest, AI v testech nahrazená) | ✅ Hotovo |
| Nahrávání vlastních podkladů (PDF/DOCX/PPTX/TXT) – podtémata, výklad, kartičky i testy 1:1 podle nich | ✅ Hotovo |
| Nasazení online (Render + databáze Neon) – konfigurace v `render.yaml` | ✅ Připraveno |

> Pro generování obsahu je potřeba klíč Google Gemini v `backend/.env` (`GEMINI_API_KEY`), získáš ho na https://aistudio.google.com/apikey.

---

## 🔄 Kroky k dosažení cíle (Metodický postup)

Projekt je realizován v logických návazných krocích, které vedou od zpracování dat až po finální uživatelské rozhraní:

1. **Vstup a extrakce dat:**
   Uživatel nahraje až 5 souborů (PDF/DOCX/PPTX/TXT, max. 10 MB). Backend je přijme a pomocí knihoven `pypdf`, `python-docx` a `python-pptx` z nich extrahuje čistý text (včetně tabulek a poznámek řečníka v prezentaci). Ukládá se jen text, ne celý soubor. AI pak smí používat výhradně informace z podkladů a ke každé otázce uvede citát z podkladů, ze kterého správná odpověď plyne.
2. **Sémantické zpracování a AI Prompting:**
   Extrahovaný text je odeslán přes API do jazykového modelu Google Gemini 3.5 Flash-Lite (při výpadku se automaticky použije záložní model Gemini 3.6 Flash). Pomocí přesně definovaných výzev (*promptů*) AI vygeneruje odpověď ve formátu JSON (otázky, možnosti, správné odpovědi, klíčové body).
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
  * **Python 3.11+** & `pip` (backendová logika)
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
| **Backend** | **Python (FastAPI + SQLAlchemy 2.0)** | **Python** poskytuje nativní ekosystém pro práci s AI SDK, manipulaci s dokumenty (`pypdf`, `python-docx`, `python-pptx`) a tvorbu REST API endpointů. |
| **Zabezpečení** | **Argon2 + JWT** | Hesla se ukládají pouze jako hash Argon2id, přihlášení drží podepsaný JWT token posílaný v hlavičce `Authorization`. |
| **AI API** | **Google Gemini 3.5 Flash-Lite** + záložní **Gemini 3.6 Flash** (`google-genai`) | Bezplatný vývojářský tier, obrovské kontextové okno (zpracování dlouhých PDF) a dobrá čeština. Modely jdou přepnout v `.env` (`GEMINI_MODEL`, `GEMINI_FALLBACK_MODEL`), volání se při přetížení opakuje. |
| **Databáze** | **PostgreSQL (Neon)** | Relační databáze pro strukturované ukládání uživatelů, předmětů, extraktů z dokumentů a kvízů. |
| **Deployment** | **Render.com** (frontend i backend) + **Neon** (PostgreSQL) | Bezplatný hosting s automatickým nasazením po každém pushi na GitHub. Neon má databázi zdarma bez časového omezení. |

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

---

## 🌐 Nasazení online

Aplikace běží zdarma na **Render.com** (backend i frontend) s databází na **Neon.tech**. Vše je popsané v souboru `render.yaml`, takže stačí jednou propojit účty a každý další `git push` se nasadí sám.

| Služba | Adresa |
| :--- | :--- |
| Aplikace (frontend) | https://studybuddy-maturita.onrender.com |
| API (backend) | https://studybuddy-maturita-api.onrender.com/docs |

### Jednorázové nastavení

1. **Databáze (Neon):** na https://neon.tech se přihlas přes GitHub → *Create project* (region **AWS Europe Central 1 / Frankfurt**, Postgres verze výchozí) → tlačítko **Connect** → zkopíruj *connection string* (začíná `postgresql://…`).
2. **Klíč Gemini:** stejný jako v `backend/.env` (nebo nový z https://aistudio.google.com/apikey).
3. **Render:** na https://render.com se přihlas přes GitHub → **New → Blueprint** → vyber repozitář `StudyBuddy` → Render načte `render.yaml` a zeptá se na:
   - `DATABASE_URL` = connection string z Neonu,
   - `GEMINI_API_KEY` = klíč Gemini.

   Potvrď **Deploy Blueprint**. První sestavení trvá pár minut.
4. Otevři https://studybuddy-maturita.onrender.com, zaregistruj se a hotovo. Na mobilu si stránku přidej na plochu (Safari: *Sdílet → Přidat na plochu*, Chrome: *⋮ → Přidat na plochu*).

### Co je dobré vědět

- **Backend zdarma usíná** po 15 minutách bez návštěvy. První načtení potom trvá asi minutu (aplikace ukáže „Probouzím server…“), pak už běží normálně.
- Online databáze je **nová a prázdná** – účty a témata z lokální `studybuddy.db` se nepřenášejí.
- Když by adresy služeb byly obsazené a Render dal jiné, uprav v nastavení služeb na Renderu `CORS_ORIGINS` (backend) a `PUBLIC_API_URL` (frontend) a nasaď znovu.
- Registrace je otevřená komukoli, kdo zná adresu – všichni sdílí tvůj limit Gemini zdarma.
