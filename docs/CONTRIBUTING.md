# Contributing to vibecheck

Thanks for your interest in contributing!

## Ways to Contribute

### Report Issues

Found a bug or have a feature request? Open an issue on GitHub.

### Submit Tool Evaluations

The easiest way to contribute is to evaluate tools you use:

1. Sign in with GitHub at vibecheck.ito.com
2. Find a tool (or add it if missing)
3. Submit your evaluation

### Improve the Codebase

#### Setup

```bash
git clone https://github.com/joi/vibecheck.git
cd vibecheck
uv sync --all-extras
```

#### Development

```bash
# Run tests
uv run pytest

# Run linter
uv run ruff check src/

# Run type checker
uv run pyright src/

# Start dev server
uv run uvicorn vibecheck.api:app --reload
```

#### Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run tests and linting
5. Commit with a descriptive message
6. Push to your fork
7. Open a Pull Request

### Code Style

- Follow PEP 8
- Use type hints
- Write docstrings for public functions
- Keep functions focused and small

### Commit Messages

Use conventional commits:

```
feat: add Discord ingestion support
fix: handle empty chat exports gracefully
docs: update API documentation
refactor: simplify URL extraction logic
test: add tests for WhatsApp parser
```

## Issue Tracking

We use [beads](https://github.com/obra/beads) as the primary issue tracker. The `.beads/` directory contains the source of truth.

GitHub Issues are synced and welcome for external contributors.

## Questions?

Open a discussion on GitHub or reach out to [@joi](https://twitter.com/joi).
