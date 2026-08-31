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
8. изисква restart на Python приложението.

Owner паролата **не се записва в `.env`**. В `admin_users` се пази само scrypt hash.

## N0C / PlanetHoster

MMI2 поддържа N0C Python Applications. Проектът съдържа:

```text
run.py
```

за N0C startup file с entry point:

```text
app
```

В MG Panel създай Python приложение от **Languages > Python**, избери Python 3.11+, application directory и root URL `/`, когато е възможно. След създаването качи MMI2 в application directory, активирай virtualenv-а, изпълни:

```bash
pip install -r requirements.txt
```

и рестартирай приложението.

N0C използва Passenger за Python приложенията. `run.py` преобразува FastAPI ASGI приложението до WSGI чрез `a2wsgi`.

## cPanel / Passenger

За cPanel/CloudLinux проектът съдържа:

```text
passenger_wsgi.py
```

с callable:

```text
application
```

В **Setup Python App / Python Selector** използвай Python 3.11+, repository directory като Application root, `passenger_wsgi.py` като WSGI/startup entrypoint и `application` като callable. След това активирай virtualenv-а, инсталирай `requirements.txt` и рестартирай Passenger app-а.

## FTP / shared hosting

FTP/FTPS е подходящ за качване на файловете, но Python application environment трябва първо да бъде създаден от N0C/cPanel. Инсталирането на Python dependencies обикновено изисква SSH или package controls на hosting панела.

Препоръчва се MMI2 да работи на root-а на отделен домейн/поддомейн, например:

```text
schedule.example.com/
```

вместо под `/mmi2`, защото web интерфейсът използва root-relative URL-и като `/install` и `/admin`.

Подробните инструкции и troubleshooting са в:

```text
docs/hosting-deployment.md
```

След приключване на installer-а използвай функцията на N0C/cPanel за restart/reload на Python приложението.

## PostgreSQL

Избраната PostgreSQL база трябва предварително да съществува и потребителят трябва да има права за създаване/промяна на таблици и индекси. Installer-ът създава схемата чрез Alembic, но не създава самата PostgreSQL database.

## Повторна инсталация

Повторна web инсталация е блокирана след създаването на `install.lock`. Не премахвай lock файла на production система с цел reset. За миграции използвай Alembic и прави backup на базата предварително.
