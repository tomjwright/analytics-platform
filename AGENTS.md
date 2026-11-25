# AGENTS.md

Guidance for coding agents working in this repo. Humans: start with [README.md](README.md).

## Standards

The workflow rules shared by all of Tom's repos (branches, PR size and descriptions, testing, secrets) live in his home repo, `tomjwright/home`.

## Agent skills

### Issue tracker

Issues and specs live as GitHub issues in this repo; use the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical labels, applied as-is: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` at the root and `docs/adr/` (created lazily by `/domain-modeling`). See `docs/agents/domain.md`.

## Checks

Run these before committing and before opening a PR. CI runs the same commands in `.github/workflows/pr.yml`.

```bash
uv run python -m analytics_platform.naming "$(git branch --show-current)" "<type>: <summary>"
uv run ruff check .
uv run ruff format --check .
uv run sqlfluff lint dbt
uv run mypy
uv run pytest --cov
uv run mutmut run && uv run mutmut export-cicd-stats && uv run python scripts/check_mutation_score.py 85
uv export --format requirements-txt --no-emit-project > requirements.txt && uv run pip-audit -r requirements.txt --disable-pip
uv run pip-licenses --partial-match --ignore-packages analytics-platform text-unidecode --allow-only="MIT;BSD;Apache;ISC;PSF;Python Software Foundation;MPL;Unlicense"
uvx semgrep@1.187.0 scan --config p/python --config p/github-actions --error --metrics off
uv run actionlint
uv run zizmor .github/workflows
```

gitleaks and CodeQL run in CI only.
