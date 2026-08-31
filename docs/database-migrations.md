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

## Revisions

### `20260831_0001` - baseline

Covers the initial Alembic-managed schema:

- `employees`
- `shift_entries`
- `import_history`
- `manual_edit_history`

### `20260831_0002` - admin audit actor

Adds nullable `manual_edit_history.changed_by` so new manual corrections record the authenticated admin account. Existing audit rows remain valid with a null actor.

### `20260831_0003` - database admin accounts

- adds `admin_users`
- uses unique email login
- stores only scrypt password hashes
- supports roles `owner`, `admin` and `moderator`
- widens `manual_edit_history.changed_by` to 255 characters so complete admin emails can be stored
- remains adoption-safe when the current metadata schema already exists
