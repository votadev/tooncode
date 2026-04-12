---
name: migrate
description: Create database migration
---

Create database migration for: {{input}}

1. Read existing models/schema
2. Generate migration file with:
   - up() - apply changes
   - down() - rollback changes
3. Use the project's migration tool (alembic, knex, prisma, django)
4. Handle: new tables, column changes, indexes, foreign keys
5. Test both up and down migrations
