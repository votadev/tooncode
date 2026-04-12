---
name: sql
description: Write and optimize SQL queries
---

SQL task: {{input}}

1. Understand the schema (read models or migration files)
2. Write the query with:
   - Proper JOINs (avoid N+1)
   - Indexes consideration
   - Pagination if needed
3. Optimize: EXPLAIN ANALYZE if database is available
4. Add as a named query, repository method, or ORM equivalent
