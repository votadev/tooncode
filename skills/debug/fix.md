---
name: fix
description: Find and fix bugs (auto-detect or specify)
---

Bug to fix: {{input}}

## If a specific bug was described:
1. Search codebase for related code
2. Identify root cause
3. Fix it
4. Verify the fix

## If no bug was specified (auto-detect):
1. Run `git diff` to see recent changes that might have caused issues
2. Run tests: `pytest` / `npm test` / `go test ./...` (detect which)
3. Check for common issues:
   - Import errors
   - Syntax errors
   - Runtime errors in recent changes
4. Read error logs if available
5. Fix all found issues
6. Re-run tests to confirm
