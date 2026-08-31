# System Diagnostics

MMI2 има production diagnostics страница за `owner` и `admin`:

```text
/admin/system
```

API:

```text
GET /api/v1/admin/system/diagnostics
```

`moderator` няма достъп.

## Какво проверява

- версия на MMI2 и текущ build PR;
- hosting runtime: N0C, cPanel/Passenger или generic ASGI;
- Python версия;
- database connectivity;
- текущ Alembic revision и migration head;
- брой служители и admin акаунти;
- последен успешен Excel import;
- свободно дисково място;
- write permissions за project и `.update`;
- готовност за SQLite/PostgreSQL backup;
- наличие на `install/install.lock`;
- self-update state и евентуален restart/rollback проблем.

## Статуси

- `healthy` - няма установени проблеми;
- `warning` - приложението може да работи, но има operational риск, например липсва backup tool;
- `error` - има проблем, който трябва да се коригира, например database connection failure или Alembic schema mismatch.

## Privacy / secrets

Diagnostics API умишлено **не връща**:

- `DATABASE_URL`;
- database host/user/password;
- `JWT_SECRET`;
- admin password hashes;
- `.env` съдържание;
- filesystem paths към database credentials/configuration.

Показва само database driver (`sqlite`, `postgresql` и т.н.) и безопасни operational metadata.

## Production use

След първоначална инсталация в N0C/cPanel отвори `/admin/system` и провери най-малко:

1. Database connection = OK
2. Alembic current = Alembic head
3. Backup ready = Да
4. Self-update state = ready
5. Project/update directories = writable
6. достатъчно свободно disk space

При `error` не прилагай self-update, преди причината да бъде отстранена.
