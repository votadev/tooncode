---
name: pr
description: Create a pull request with summary
---

1. Check current branch and commits ahead of main
2. Run `git diff main...HEAD` to see all changes
3. Write a PR description:
   ## Summary
   - Bullet points of what changed
   
   ## Changes
   - File-by-file breakdown
   
   ## Testing
   - How to test these changes
4. Create PR using `gh pr create` if gh CLI is available
