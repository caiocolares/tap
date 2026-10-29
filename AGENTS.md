# Repository Guidelines

## Project Structure & Module Organization

T.A.P. transcribes audio and assigns generic speaker labels. Source modules live at the root:

- `server.py`: FastAPI endpoints, synchronous requests, asynchronous jobs, and model caching.
- `transcribe.py`: CLI, ffmpeg conversion, Whisper transcription, diarization, and TXT/JSON output.
- `storage.py`: optional MinIO/S3 persistence.
- `tests/`: unit tests corresponding to the three modules; `img/`: documentation images.
- `Dockerfile.cpu`, `Dockerfile.gpu`, `docker-compose.yml`, and `knative-service.yaml`: container and deployment configuration.

See `README.md` for usage, `DOC.md` and `TODO.md` for architecture, and `CONTRIBUTING.md` for policy.

## Build, Test, and Development Commands

Use Python 3.13 and install ffmpeg for audio processing.

- `uv sync`: install locked dependencies, including the development group.
- `uv run uvicorn server:app --reload --port 8000`: start the local API.
- `uv run transcribe.py audio.mp3 --no-diarization`: transcribe through the CLI without a Hugging Face token.
- `uv run pytest`: run tests with terminal and HTML coverage reports.
- `uv run pytest tests/test_server.py -q`: run API tests only.
- `docker build -f Dockerfile.cpu -t audio-to-text:cpu .`: build the CPU image.
- `docker compose up --build`: start the API and MinIO; prepare `.env` first.

## Coding Style & Naming Conventions

Follow existing Python style: four-space indentation, `snake_case` functions and variables, `PascalCase` classes, and uppercase configuration constants. Add type hints. Keep HTTP, transcription, and storage responsibilities separate. Preserve existing Portuguese API names and messages. No formatter or linter is currently configured; Ruff commands in CI are commented examples.

## Testing Guidelines

Use pytest, pytest-cov, and pytest-mock. Name files `tests/test_<module>.py` and functions `test_<behavior>`. Stub ML models, ffmpeg, and storage calls with fixtures and monkeypatching; unit tests should run without model downloads or external services. Include regression tests for fixes. Coverage spans all source modules, generating `htmlcov/index.html`; no numeric minimum is configured. The CI test job currently fails at a configuration placeholder, so run tests locally.

## Commit & Pull Request Guidelines

History mixes `feat:`, `fix:`, and `docs:` commits with informal messages. Follow the documented Conventional Commits format and sign every commit with `git commit -s`. Branch from `main`, using prefixes such as `feat/` or `fix/`. Complete the PR template with the issue, rationale, validation commands, and relevant before/after output. Update affected documentation and justify new dependencies with their licenses.

## Security & Configuration

Copy `.env.example` to `.env`. Never commit tokens, credentials, audio containing institutional data, or sensitive fixtures. Keep `MINIO_ENDPOINT` empty to disable shared storage. Follow `SECURITY.md` for vulnerability reporting.
