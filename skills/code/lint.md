---
name: lint
description: Lint and auto-fix code (auto-detect or specify)
---

Lint target: {{input}}

## If a file was specified:
Lint that specific file.

## If nothing specified (auto-detect):
1. Detect project language from files present
2. Find the linter config or use defaults
3. Lint entire project

## Actions:
- Python: run `ruff check --fix .` then `ruff format .` (or black/isort)
- JS/TS: run `eslint --fix .` then `prettier --write .`
- Go: run `gofmt -w .` then `go vet ./...`
- Rust: run `cargo clippy --fix`

If linter not installed, fix issues manually by reading files and applying style fixes.
Report: fixed count, remaining issues that need manual fix.
