# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

StudyBuddy is a Czech high-school graduation (maturita) project: a user enters a topic, Google Gemini splits it into subtopics plus an entry quiz, quiz results set per-subtopic mastery, and the AI then writes lessons, flashcards and practice quizzes tailored to that mastery. Two independent apps: `backend/` (FastAPI + SQLAlchemy 2.0) and `frontend/` (static Astro 7 + Tailwind 4). **All user-facing text, comments, docstrings and AI prompts are in Czech**, so keep new ones in Czech too.

## Commands

Backend (run from `backend/`):
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # set SECRET_KEY, GEMINI_API_KEY
uvicorn app.main:app --reload     # http://localhost:8000, docs at /docs
pytest                            # all tests (pytest.ini sets testpaths/pythonpath)
pytest tests/test_learning.py::test_name   # single test
```

Frontend (run from `frontend/`, Node >= 22):
```bash
npm install
cp .env.example .env              # PUBLIC_API_URL=http://localhost:8000
npm run dev                       # http://localhost:4321
npm run build
```

There is no linter or frontend test setup.

## Architecture

### Backend (`backend/app/`)
- `main.py` calls `Base.metadata.create_all` at startup. There are no migrations, so after a schema change in `models.py` you have to delete the local `studybuddy.db`. It also replaces `RequestValidationError` with a single Czech `detail` string (field labels in `_FIELD_NAMES`).
- Data model (`models.py` docstring has the tree; plus `Group ─< GroupMember >─ User` for classes): `User ─< Subject ─< Subtopic (mastery 0–100 or None, one Lesson, many Flashcards)` and `Subject ─< Quiz (kind "entry" | "practice") ─< Question`. Cascades are ORM-level (`delete-orphan`) and also DB-level `ON DELETE CASCADE`. `database.py` turns on SQLite foreign keys with a PRAGMA.
- **Ownership checks:** load records only through `access.py` (`get_subject`, `get_subtopic`, `get_quiz`, `get_flashcard`). They walk up to `subject.user_id` and return **404, not 403**, for records owned by someone else. Every protected route depends on `deps.get_current_user` (Bearer JWT).
- **Classes/teachers (`routers/groups.py`):** `Group` (6-char `join_code`) ─< `GroupMember` (`role` "teacher" | "student", unique per group+user). Roles belong to the membership, not the account: whoever creates a group is its teacher and can promote members. The last teacher can't be demoted or leave (409). Checks go through `access.get_membership(db, group_id, user, teacher=…)`, which returns **404 for non-members and 403 for a student attempting a teacher action**, and `access.get_member` for the target user. Teachers get **read-only** access to students' data only via `/api/groups/{id}/students/{uid}` (reusing `subjects.subject_out` and `quizzes.quiz_result`). The regular `/api/subjects…` routes remain owner-only. Deleting a group doesn't delete students' subjects.
- **AI layer (`ai.py`):** all Gemini prompts live here. Routers call only `generate_plan`, `generate_lesson` and `generate_quiz`, wrapped in `subjects._ai_call`, which converts `AIError(message, status)` to an `HTTPException`. Responses use structured JSON output (`response_schema` = Pydantic models `AIPlan`/`AIQuiz`/`AILesson`) and are then sanitized by `_clean_questions` (exactly 4 options, valid indices, shuffling). `_generate` tries `GEMINI_MODEL` then `GEMINI_FALLBACK_MODEL`; per model it retries 429/5xx/network errors with backoff (`AI_RETRIES`, `_sleep` is patchable) and retries an unusable answer once (invalid JSON, safety block, or failing the per-function `check` callback) before falling back. A bad API key (`AIError.fallback=False`) stops immediately. Gemini 3.x rejects `thinking_budget` (400), so `_config` sends `thinking_level=MINIMAL` except for `gemini-2*` models. Whole call is bounded by `AI_TOTAL_TIMEOUT` (frontend waits 120 s). With no `GEMINI_API_KEY`, calls raise a 503 that says so. `scripts/test_gemini.py` is a live diagnostic (never prints the key).
- **Uploaded materials:** `POST /api/subjects/upload` (multipart, sync `def` so it runs in the threadpool) takes up to 5 files, `documents.extract_text` turns PDF/DOCX/PPTX/TXT/MD into text (`DocumentError` = Czech 422 message), `fit_materials` trims them to `MAX_TEXT_CHARS`, and only the text is stored in the `materials` table (a new table, so `create_all` adds it to existing DBs). `Subject.material_text` is passed as `material=` to every `ai.generate_*` call; when non-empty the prompts switch to `MATERIAL_RULES` (use only the material) and ask for a `source` quote that `_clean_questions` appends to the explanation.
- **Learning flow across routers:** `POST /api/subjects` (or `/upload`) → `generate_plan` creates the subtopics and the entry quiz. With `skip_entry=true` ("starting from zero"), `generate_plan(entry_quiz=False)` returns subtopics only and no entry quiz is saved. That is the only marker (`entry_skipped` = subject has no entry quiz, no DB column), and `subjects._level` then treats untested subtopics as `"weak"` for lessons and practice quizzes. `POST /api/quizzes/{id}/submit` (`quizzes.py`, 409 if already submitted) scores the quiz, updates each subtopic's mastery from its own questions and awards XP. `POST /api/subtopics/{id}/lesson` (`subjects.py`) passes the student's past wrong answers (`_mistakes`) into `generate_lesson`. Regenerating a lesson overwrites the old text and **replaces all of that subtopic's flashcards**. `POST /api/subtopics/{id}/quiz` passes earlier question texts so the AI doesn't repeat them. `routers/review.py` serves due flashcards and records Leitner answers.
- **Learning logic (`progress.py`):** pure functions with no DB or AI. `mastery_level` thresholds are weak <50, mid <80, strong ≥80. `update_mastery` takes the first score as-is and blends later ones 0.4·old + 0.6·new. XP/streak is handled by `award_xp`. Flashcards use a Leitner system with boxes 1–5 and intervals of 1/2/4/8/16 days; a wrong answer goes back to box 1, due today. The mastery level controls how deep the lesson prompt goes (`ai.LEVEL_TEXT`).
- Login rate limit: an in-memory dict `routers/auth._FAILED` (8 failures per 10 min per IP).
- `config.py`: pydantic-settings reads `.env`. It rewrites `postgres://` URLs to `postgresql+psycopg://`. With `ENVIRONMENT=production` it refuses to start if `SECRET_KEY` is the default value or shorter than 32 characters.

### Tests (`backend/tests/`)
`conftest.py` sets env vars **before** importing the app (in-memory SQLite, empty Gemini key). It also gives each test a fresh `StaticPool` engine, monkeypatches `database.SessionLocal`, overrides `get_db` and clears `_FAILED`. Tests never call Gemini: the `fake_ai` fixture in `test_learning.py` monkeypatches the `ai.generate_*` functions, and `test_ai.py` replaces `ai.genai.Client` with a scripted `FakeClient` to test retries/fallback. Use `register(client)` / `auth_headers` for authenticated requests.

### Frontend (`frontend/src/`)
- Static output only. Pages are thin Astro shells, and all data loading and rendering happens in client-side `<script>` blocks that build HTML strings. Detail pages take their ID from the query string (`/lesson?id=12`, read by `learning.idFromUrl`), not from dynamic routes.
- `lib/api.js` is the only way to reach the backend. It adds the Bearer token, applies a timeout (pass `AI_TIMEOUT` = 120 s for AI-backed calls), turns any 401 into a logout plus redirect, and surfaces the backend's Czech `detail` as `ApiError`.
- Auth: the JWT is kept in `localStorage` (`sb_token`, `sb_user`), deliberately not in cookies because frontend and backend are separate origins in production. `Layout.astro` has an inline script that sets the theme (`sb_theme`) and redirects to `/login?next=…` when no token is present (`auth={false}` makes a page public).
- XSS: escape plain text with `dom.esc` and render AI Markdown only through `dom.md` (marked + DOMPurify).
- Tailwind class names must be written as complete literal strings so Tailwind can detect them (see `LEVELS` in `lib/learning.js`). Theme colors (`bg-weak`, `text-muted`, `bg-surface-2`, …) are defined in `styles/global.css`.

## Status
Deployment: `render.yaml` (Render Blueprint) defines the free backend web service `studybuddy-maturita-api` and the static site `studybuddy-maturita` (their URLs are hard-coded in each other's `CORS_ORIGINS`/`PUBLIC_API_URL`). PostgreSQL is on Neon (`DATABASE_URL` is set in the Render dashboard). The free backend sleeps after 15 min, so `lib/api.js` waits up to 90 s and shows a "Probouzím server…" notice after 4 s. Step-by-step guide in README "Nasazení online".
