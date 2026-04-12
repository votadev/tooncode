---
name: docker
description: Generate Dockerfile and docker-compose
---

Analyze the project and create:

1. **Dockerfile** - multi-stage build, minimal image, non-root user
2. **docker-compose.yml** - if multiple services needed
3. **.dockerignore** - exclude unnecessary files

Optimize for:
- Small image size
- Fast builds (layer caching)
- Security (non-root, no secrets in image)
