# Database migrations

MMI2 uses Alembic to version database schema changes.

## Local development

After pulling changes that include a migration:

```bash
python -m alembic upgrade head
```

Then start the application normally.

## Docker

The Docker image runs `alembic upgrade head` automatically before Uvicorn starts.

## Existing SQLite databases

The first Alembic revision is an adoption-safe baseline. A database previously created by `Base.metadata.create_all()` can run:

```bash
python -m alembic upgrade head
```

without deleting the existing schedule data. The baseline creates only missing current tables/indexes and records the Alembic revision.

Always back up a production database before applying schema migrations.

## Creating future migrations

After changing SQLAlchemy models:

```bash
python -m alembic revision --autogenerate -m "describe change"
python -m alembic upgrade head
```

Review every generated revision before committing it, especially SQLite batch operations and destructive changes.

## Current baseline

Revision: `20260831_0001`

It covers:

- `employees`
- `shift_entries`
- `import_history`
- `manual_edit_history`
