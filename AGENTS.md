# Repository Guidelines

## Project Structure & Module Organization
- `backend/` — FastAPI API and Dramatiq workers. Key dirs: `services/`, `agent/`, `agentpress/`, `youtube_mcp/`, `triggers/`. Tests: `backend/test_*.py`.
- `frontend/` — Next.js 15 + TypeScript. Source: `src/{app,components,lib,...}`.
- `docs/`, `sdk/`, `supabase/` — documentation, SDK assets, local Supabase configs.
- Root ops: `docker-compose.yaml`, `start_services.sh`, `setup.py`.

## Build, Test, and Development Commands
- Initial setup: `python setup.py` (creates env files, services).
- Full stack via Docker: `docker compose up --build` (API on `8000`, web on `3000`).
- Backend dev:
  - Redis only: `docker compose up redis`
  - API: `cd backend && uv run api.py`
  - Worker: `cd backend && uv run dramatiq --processes 4 --threads 4 run_agent_background`
- Frontend dev: `cd frontend && npm run dev`
- Backend tests: `cd backend && uv run pytest -q` (filter: `-k "youtube or instagram"`).

## Coding Style & Naming Conventions
- Python: PEP 8, 4‑space indent, add type hints where practical. Files/modules `snake_case`; classes `PascalCase`; functions/vars `snake_case`; constants `UPPER_CASE`.
- TypeScript/React: 2‑space indent. Use Prettier + ESLint. Components in `src/components/` named `PascalCase`.
- Lint/format: `cd frontend && npm run lint && npm run format`.

## Testing Guidelines
- Frameworks: `pytest`, `pytest-asyncio`. Name tests `backend/test_*.py`; prefer `async def test_*` for async code.
- Run all: `cd backend && uv run pytest -q`.
- External deps: tests touching Supabase/Redis require a valid `backend/.env`. For local API + Docker Redis set `REDIS_HOST=localhost` (Docker↔Docker use `redis`).

## Commit & Pull Request Guidelines
- Commits: use Conventional Commits, e.g. `feat(backend): add agent trigger API` or `fix(frontend): conditionally display event triggers`.
- PRs: include clear description, linked issues, test steps; screenshots for UI changes; note env or migration impacts. Keep changes focused and update docs when behavior or APIs change.

## Security & Configuration Tips
- Never commit secrets. Use `backend/.env` and `frontend/.env.local`; mirror new keys in `*.env.example`.
- When adding agents or triggers under `backend/{agent,agentpress,triggers}`, follow naming conventions above and keep modules small and testable.

