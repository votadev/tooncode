---
name: secrets
description: Scan for hardcoded secrets and credentials
---

Scan entire project for hardcoded secrets:

1. Search for patterns: API keys, tokens, passwords, connection strings
2. Check: .env files, config files, source code, scripts
3. Check .gitignore covers sensitive files
4. Verify no secrets in git history: `git log -p | grep -i "password\|secret\|api.key\|token"`
5. Suggest: use environment variables or secret manager
6. Create/update .gitignore if needed
