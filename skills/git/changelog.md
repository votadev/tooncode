---
name: changelog
description: Generate changelog from git history
---

Generate CHANGELOG.md:

1. Read git log: `git log --oneline --since="last month"` (or {{input}} range)
2. Categorize commits:
   - Features (feat:)
   - Bug Fixes (fix:)
   - Breaking Changes (breaking:)
   - Other (refactor, docs, chore)
3. Format as Keep a Changelog standard
4. Include date and version if tagged
5. Write/update CHANGELOG.md
