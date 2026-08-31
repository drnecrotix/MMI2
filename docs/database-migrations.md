# Database migrations

MMI2 uses Alembic as the only supported mechanism for versioning and applying database schema changes.

## Important runtime rule

The FastAPI application does **not** call `Base.metadata.create_all()` at startup.

Starting Uvicorn against a database that has not been migrated is considered a deployment/setup error. This is intentional: missing migrations must fail visibly instead of being silently masked by runtime table creation.

## Local development

After installing dependencies and whenever you pull changes that include a migration, run:

```bash
python -m alembic upgrade head
```

Then start the application normally:

```bash
uvicorn app.main:app --reload
```

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

Do not add `Base.metadata.create_all()` back to application startup as a migration shortcut.

## Current baseline

Revision: `20260831_0001`

It covers:

- `employees`
- `shift_entries`
- `import_history`
- `manual_edit_history`
