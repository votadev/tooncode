---
name: test
description: Generate tests (auto-detect what needs testing)
---

Test target: {{input}}

## If a file was specified:
Write tests for that specific file.

## If nothing specified (auto-detect):
1. Find source files that have NO corresponding test files
2. Check `git diff` for recently changed files without tests
3. Prioritize: most critical/complex files first
4. Generate tests for the top 3 untested files

## For each test file:
1. Detect language -> choose framework (pytest, jest, vitest, go test)
2. Read the source code first
3. Write tests covering:
   - Happy path
   - Edge cases (empty, null, max values)
   - Error handling
   - Boundary conditions
4. Run the tests
5. Fix any failures
