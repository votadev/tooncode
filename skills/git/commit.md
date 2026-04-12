---
name: commit
description: Smart git commit with auto-generated message
---

1. Run `git diff --staged` and `git diff` to see all changes
2. If nothing staged, run `git add -A`
3. Write a clear commit message:
   - First line: type(scope): summary (under 72 chars)
   - Types: feat, fix, refactor, docs, test, chore
   - Body: what changed and why
4. Commit with the message
