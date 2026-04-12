---
name: audit
description: Security audit - OWASP top 10 scan
---

Security audit this project for OWASP Top 10:

1. **Injection** - SQL, NoSQL, OS command, LDAP
2. **Broken Auth** - weak passwords, session management
3. **Sensitive Data** - exposed secrets, unencrypted data
4. **XXE** - XML external entity
5. **Broken Access Control** - privilege escalation, IDOR
6. **Misconfig** - default credentials, verbose errors, open CORS
7. **XSS** - reflected, stored, DOM-based
8. **Insecure Deserialization** - pickle, yaml.load, JSON parse
9. **Known Vulnerabilities** - outdated dependencies
10. **Logging** - insufficient logging, log injection

Also check for:
- Hardcoded secrets (API keys, passwords, tokens)
- .env files in git
- Unsafe file operations

Output: severity, file:line, description, fix.
