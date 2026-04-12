---
name: ci
description: Generate CI/CD pipeline config
---

Create CI/CD pipeline for this project:

1. Detect language and framework
2. Generate config for {{input}} (default: GitHub Actions)
3. Include stages:
   - Install dependencies
   - Lint / format check
   - Run tests
   - Build
   - Deploy (if applicable)
4. Add caching for faster builds
