# Repository Guidelines

## Project Structure & Modules
- `app/`: main source (CLI in `cli.py`, orchestration in `main.py`, services, utils, models).
- `data/`: generated assets and templates; projects saved under `data/projects/<person>_<topic>_<timestamp>/`.
- `tests/`: automated tests (pytest).
- Root scripts: operational helpers (e.g., `add_text_to_image.py`, `cleanup_data.py`, `generate_from_script.py`).

## Build, Test, and Development
- Create venv: `python -m venv .venv && .venv\Scripts\activate`.
- Install deps: `pip install -r requirements.txt`.
- Run CLI: `python -m app.cli` (set `PYTHONUTF8=1` on Windows to avoid mojibake).
- Lint/format check: `ruff check .`.
- Type check: `mypy app`.
- Tests: `pytest` (add `-q` for quiet).

## Coding Style & Naming
- Language: Python 3.10+. Use 4-space indents, type hints, and f-strings.
- Names: modules_snake_case, functions/methods snake_case, classes PascalCase.
- Logging: prefer `app.utils.logger` helpers; keep user-facing prints concise and UTF-8 safe.
- Filenames: sanitize for filesystem; existing helper in `FileManager._sanitize_filename`.

## Testing Guidelines
- Framework: pytest; async tests supported via `pytest-asyncio`.
- Place tests in `tests/` mirroring module paths; name files `test_*.py` and functions `test_*`.
- When adding services, provide unit tests with mocked API calls (OpenAI/Anthropic/Gemini/KIEAI).
- Aim to cover failure paths (missing keys, network errors) and happy paths.

## Commit & PR Guidelines
- Commits: use clear, imperative summaries (e.g., `Add Gemini support for scripts`, `Fix CLI encoding prompt`).
- PRs should include: purpose/summary, notable changes, test evidence (`pytest`, `ruff`, `mypy`), and any screenshots/log excerpts for UX/CLI output.
- Link related issues/tasks when available; keep PR scope focused (one feature/fix).

## Security & Configuration
- Secrets live in `.env`; do not commit keys. Required keys per feature: `GEMINI_API_KEY`, optional `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`, `KIEAI_API_KEY` for images.
- Default LLM is `models/gemini-pro-latest`; override via `DEFAULT_LLM_MODEL` in `.env`.
- VOICEVOX must be reachable at `http://localhost:50021`; installer path is auto-detected.

## Agent Notes
- When scripting the CLI in automation, set `[Console]::InputEncoding/OutputEncoding = [Text.UTF8Encoding]::new($false)` on Windows to prevent mojibake in prompts and inputs.
- Large jobs (image/video) write under `data/projects`; avoid removing user data. Use existing helpers in `FileManager` for paths and metadata persistence.
