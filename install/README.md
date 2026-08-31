# MMI2 web installer

Тази папка съдържа first-run installer-а на MMI2.

## Как работи

При инсталация без `install/install.lock` приложението пренасочва HTML заявките към `/install`.

Installer-ът:

1. проверява Python/Alembic и правата за запис;
2. конфигурира SQLite или PostgreSQL;
3. тества връзката с базата;
4. изпълнява `alembic upgrade head`;
5. създава единствения `owner` акаунт;
6. записва `.env` с нов JWT secret и `ADMIN_BOOTSTRAP_ENABLED=false`;
7. създава `install/install.lock`;
8. изисква restart на Python/ASGI приложението.

Owner паролата **не се записва в `.env`**. В `admin_users` се пази само scrypt hash.

## FTP / shared hosting

Качването през FTP е само начин за прехвърляне на файловете. Хостингът трябва да може да стартира Python ASGI приложение чрез например Passenger, собствен Python app manager, VPS/systemd или Docker.

След приключване на installer-а използвай функцията на hosting control panel за restart/reload на Python приложението.

## PostgreSQL

Избраната PostgreSQL база трябва предварително да съществува и потребителят трябва да има права за създаване/промяна на таблици и индекси. Installer-ът създава схемата чрез Alembic, но не създава самата PostgreSQL database.

## Повторна инсталация

Повторна web инсталация е блокирана след създаването на `install.lock`. Не премахвай lock файла на production система с цел reset. За миграции използвай Alembic и прави backup на базата предварително.
