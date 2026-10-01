# Contributing to Kepa

Thanks for your interest in contributing!

## Development setup

```bash
git clone https://github.com/AkashNaickar/Kepa.git
cd Kepa
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements-dev.txt
```

## Before opening a PR

```bash
ruff check capture tests
pytest -q
```

Both must pass. CI runs the same checks on every push and PR.

## Guidelines

- Keep the pipeline logic in `capture/pipeline.py` pure and dependency-free;
  external services are injected via the client protocols there.
- AWS/CockroachDB specifics belong in `capture/aws_clients.py` (lazy imports).
- Add tests for any new behavior. No feature without a test.
- Never commit secrets. Use `.env.example` as the template for required vars.
- Small, imperative commit messages (e.g. "Add fail-closed signature check").
