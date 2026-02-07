# EasyInterview

Multi-scenario interview system with question-bank-driven workflows and evaluation.

## Language
- Chinese: [README](./README.md)
- English: [README_EN](./README_EN.md)

## Project Structure
App: src/app/; Deploy scripts: src/deploy/; Docs: docs/

## Quick Start
cd app && pip install -r requirements.txt && uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

## Source Directory
- Unified source entry: [src](./src)

## Development Status
- This repository is maintained for open-source collaboration.
- Progress is tracked via commits and issues.

## Migration Note
- Core folders have been moved to `src/app` and `src/deploy`.
- Root `app` / `deploy` are compatibility symlinks so existing commands keep working.
