# Database Migrations

This backend now has an Alembic baseline for the main database.

## Current Scope

- Alembic manages the main database schema.
- The current application data model uses one main database with `tenant_id` / `user_id` row-level tenant boundaries.
- The tenant database helpers in `app/core/database.py` are reserved for a future physical isolation migration and are not part of this baseline.

## Local Commands

Run commands from the `backend` directory.

```bash
alembic upgrade head
```

Create a new migration after ORM model changes:

```bash
alembic revision --autogenerate -m "describe change"
```

Review generated migrations before committing them. New schema changes should go through Alembic instead of adding more startup-time compatibility `ALTER TABLE` statements.

## Existing Databases

For an existing database that already matches the current ORM schema, verify the schema first and then stamp the baseline:

```bash
alembic stamp head
```

For a new empty database, run `alembic upgrade head`.

Production rollout should back up the database before migration and keep an application rollback plan ready.
