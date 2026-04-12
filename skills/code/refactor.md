---
name: refactor
description: Refactor code (auto-detect or specify target)
---

Refactor target: {{input}}

## If a file was specified:
Refactor that specific file.

## If nothing specified (auto-detect):
1. Find the largest/most complex files: `wc -l *.py` or equivalent
2. Check for code smells:
   - Functions longer than 50 lines
   - Files longer than 500 lines
   - Deep nesting (3+ levels)
   - Duplicated code blocks
3. Pick the worst offender and refactor it

## Refactor checklist:
- Improve naming clarity
- Extract long functions into smaller ones
- Remove duplication (DRY)
- Simplify complex conditionals
- Better structure and separation of concerns
Show diff of every change.
