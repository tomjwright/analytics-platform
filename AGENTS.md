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
