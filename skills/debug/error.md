---
name: error
description: Add error handling (auto-detect files or specify)
---

Target: {{input}}

## If a file/module was specified:
1. Read the specified file
2. Find all unhandled failure points
3. Add proper error handling

## If nothing specified (auto-detect):
1. Glob all source files in project
2. Search for risky patterns:
   - Bare `except:` or `catch(e)` with no handling
   - Missing null checks
   - Unvalidated user input
   - Network/file operations without try/catch
3. Fix the worst offenders first
4. Add logging where needed

For each fix:
- Use specific error types (not generic)
- Add meaningful error messages
- Add appropriate logging (error/warn/info)
- Add graceful degradation where possible
