---
name: deps
description: Analyze and manage dependencies
---

Analyze dependencies in this project:

1. List all dependencies and their versions
2. Check for:
   - Outdated packages (major/minor/patch)
   - Known vulnerabilities (npm audit / pip-audit / cargo audit)
   - Unused dependencies
   - Missing dependencies
3. Suggest updates with risk assessment
4. If {{input}} = "update": apply safe updates (patch/minor only)
