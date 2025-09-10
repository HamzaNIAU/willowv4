# Repository Guidelines

## Project Structure & Modules
- `backend/` — FastAPI API and workers (Dramatiq). Key dirs: `services/`, `agent/`, `agentpress/`, `youtube_mcp/`, `triggers/`. Tests live as `backend/test_*.py`.
- `frontend/` — Next.js 15 + TypeScript. Code in `src/{app,components,lib,...}` with Prettier/ESLint configs.
- `docs/`, `sdk/`, `supabase/` — documentation, SDK assets, local Supabase configs.
- Root ops: `docker-compose.yaml` (redis, backend, worker, frontend), `start_services.sh`, `setup.py` (guided setup).

## Build, Test, and Dev Commands
- Initial setup (envs/services): `python setup.py` from repo root.
- Full stack via Docker: `docker compose up --build` (exposes `8000` API, `3000` web, Redis).
- Backend local dev:
  - Run Redis only: `docker compose up redis`
  - API: `cd backend && uv run api.py`
  - Worker: `cd backend && uv run dramatiq --processes 4 --threads 4 run_agent_background`
- Frontend dev: `cd frontend && npm run dev`
- Backend tests: `cd backend && uv run pytest -q`

## Coding Style & Naming
- Python (backend): PEP 8, 4‑space indent, type hints where practical. Files/modules `snake_case`, classes `PascalCase`, functions/vars `snake_case`, constants `UPPER_CASE`.
- TypeScript/React (frontend): 2‑space indent, Prettier + ESLint. Components `PascalCase` in `src/components/`, route files follow Next.js conventions. Run `npm run lint` and `npm run format`.

## Testing Guidelines
- Frameworks: `pytest`, `pytest-asyncio` (via `uv`). Name files `backend/test_*.py`; prefer `async def test_*` for async code.
- Run all: `cd backend && uv run pytest -q`; filter: `-k "youtube or instagram"`.
- External deps: tests that touch Supabase/Redis require a valid `backend/.env`. For local API+Docker Redis, set `REDIS_HOST=localhost`.

## Commit & Pull Request Guidelines
- Use Conventional Commits where possible: `feat:`, `fix:`, `chore:`, `refactor:` (e.g., `fix(frontend): conditionally display event triggers`). Keep subject ≤ 72 chars.
- PRs: clear description, linked issues, test steps; screenshots for UI changes; note env or migration impacts. Keep changes focused; update docs when behavior or APIs change.

## Security & Configuration
- Never commit secrets. Use `backend/.env` and `frontend/.env.local`; mirror new keys in `*.env.example`.
- Redis host: Docker↔Docker use `redis`; local API↔Docker Redis use `localhost`.
