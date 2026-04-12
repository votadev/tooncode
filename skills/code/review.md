---
name: review
description: Review code for bugs and security (auto-detect scope)
---

Review target: {{input}}

## If a file/folder was specified:
Read and review that specific target.

## If nothing specified (auto-detect):
1. Run `git diff` or `git diff --staged` to find recent changes
2. If no changes, review the main source files in the project
3. Focus on the most critical files first

## Review checklist:
- Security vulnerabilities (injection, XSS, auth bypass)
- Logic errors and edge cases
- Performance bottlenecks
- Error handling gaps
- Race conditions / concurrency issues

Output a report with severity: Critical / High / Medium / Low
For each: file:line, problem, fix suggestion.
