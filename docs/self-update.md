# Safe self-update

MMI2 може да проверява GitHub за нови merge-нати PR-и и да прилага съвместими updates през SSH/Terminal.

Self-update-ът е проектиран основно за N0C/PlanetHoster и cPanel/Passenger, където приложението вече има Python virtualenv и writable application directory.

## Защо update-ът не се стартира през HTTP

Python web worker не трябва да презаписва собствените си source файлове по време на активна HTTP заявка. Затова admin панелът открива update-а, а самото прилагане се прави през terminal/SSH:

```bash
python update_mmi2.py check --force
```

Преди update:

```bash
python update_mmi2.py preflight 19
```

Ако `automatic_apply` е `true`:

```bash
python update_mmi2.py apply 19 --yes
```

Замени `19` с PR номера, показан в admin панела.

## Какво проверява preflight

- PR-ът е merge-нат;
- base branch е `main`;
- PR номерът е по-нов от текущия build;
- GitHub предоставя валиден merge commit SHA;
- `requirements.txt` е същият като в текущия Python environment;
- има права за запис в project directory;
- database backup може да бъде направен безопасно.

## Dependencies

Ако target PR променя `requirements.txt`, automatic apply се блокира.

Причината е, че downgrade/rollback на Python virtualenv не може да бъде гарантиран безопасно на shared hosting.

В такъв случай:

1. отвори PR-а и провери dependency промените;
2. активирай правилния N0C/cPanel virtualenv;
3. обнови packages ръчно;
4. използвай normal deployment или следваща версия на updater-а, която поддържа конкретната dependency промяна.

## Backup

Преди file replacement updater-ът създава:

```text
.update/backups/<backup-id>/
```

Backup-ът съдържа:

- snapshot на управляваните project файлове;
- manifest с current/target version;
- database backup.

Не се презаписват:

- `.env`;
- `install/install.lock`;
- installer runtime markers;
- uploads/user runtime data.

### SQLite

Използва се SQLite backup API, а не обикновено копиране на активен database файл.

### PostgreSQL

Automatic update се разрешава само ако са налични едновременно:

```text
pg_dump
pg_restore
```

Ако някой от двата инструмента липсва, preflight спира update-а.

## Update sequence

1. GitHub PR metadata validation.
2. Изтегляне на точния merge commit от GitHub.
3. Safe ZIP extraction със защита от path traversal и symlinks.
4. Проверка на `app/version.py`.
5. Проверка, че dependencies не са променени.
6. Python compile check на staging кода.
7. File + database backup.
8. File replacement със запазване на runtime secrets/lock.
9. `alembic upgrade head` в отделен Python process.
10. Fresh-process `import app.main` smoke test.
11. При грешка - автоматично връщане на файловете и database backup-а.
12. При успех - restart marker и Passenger `tmp/restart.txt` request.

## Restart

На N0C/cPanel updater-ът създава:

```text
tmp/restart.txt
```

за Passenger restart request.

Ако control panel не рестартира приложението автоматично, използвай:

- N0C: **Restart Python App / Restart**;
- cPanel: **Restart / Reload application**.

След стартиране на новия build `app/__init__.py` валидира target PR и премества restart marker-а в `.update/history/`.

## Interrupted update

Ако process/server спре след създаване на `update.in_progress`, следващият application startup спира умишлено вместо да обслужва потенциално полуобновена система.

Използвай offline rollback:

```bash
python rollback_update.py --yes
```

или конкретен backup:

```bash
python rollback_update.py 20260831T220000Z-pr18-to-pr19 --yes
```

След rollback рестартирай Python приложението.

## Status

```bash
python update_mmi2.py status
```

## Важно

Self-update не заменя външен backup. Преди production update е препоръчително да имаш отделен hosting/database backup извън `.update/` директорията.
