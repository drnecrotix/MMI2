# MMI2 Schedule System

Уеб система за импорт на месечни работни графици от Excel и персонален календар за всеки служител.

## Основна логика

От Excel файла за всеки служител се извличат:

- работен номер;
- имена;
- постоянна смяна `А`, `Б`, `В` или `Г`;
- график за всеки ден от месеца.

Служителят въвежда своя работен номер и вижда само своя месечен график.

## Потвърдена легенда

| Excel | Значение | API тип |
| --- | --- | --- |
| `1` | Дневна смяна | `day` |
| `2` | Нощна смяна | `night` |
| `О` или `0` | Отпуск | `leave` |
| `Б` | Болничен | `sick_leave` |
| празна клетка | Почивка по график | `rest` |

Всички други стойности се съхраняват като `unknown`, като оригиналният код остава в `raw_code`.

## Какво има в текущия MVP

- FastAPI backend;
- SQLAlchemy база данни;
- Alembic versioned database migrations;
- first-run web installer в `/install`;
- SQLite или PostgreSQL конфигурация през installer-а;
- DB-backed admin accounts с роли `owner`, `admin`, `moderator`;
- точно един owner и owner-only управление на акаунти;
- scrypt password hashing;
- `.xlsx` импорт чрез OpenPyXL;
- разпознаване на реалния MMI2 формат с няколко блока в един лист;
- извличане на работен номер, име и смяна А/Б/В/Г;
- месечни записи за всички календарни дни;
- повторен импорт обновява съществуващите записи;
- atomic import на графика и `ImportHistory` в една DB транзакция;
- засичане на повторни служители и конфликтни дни;
- вход чрез работен номер;
- JWT access token;
- responsive персонален календар;
- автоматичен ориентировъчен 2-на-2 fallback при липсващ официален график;
- навигация между месеци;
- месечна статистика за дневни, нощни, отпуск, болничен и почивни дни;
- отделен `/admin` интерфейс с admin authentication;
- preview на Excel файла преди запис в базата;
- автоматично разпознаване на месец и година, когато Excel съдържа достатъчно надежден сигнал;
- ръчен fallback за месец и година, ако автоматичното разпознаване не е сигурно;
- история на успешните импорти;
- SHA-256 отпечатък на всеки импортиран файл без съхраняване на самия Excel;
- REST API за бъдещо Android native приложение;
- Dockerfile и Docker Compose;
- unit tests със синтетични данни;
- GitHub Actions CI за автоматично изпълнение на migrations и тестовете.

## Роли в административния панел

### owner

- единствен owner профил;
- пълен оперативен достъп;
- единствен може да създава и управлява admin/moderator акаунти;
- owner профилът не може да бъде понижен или деактивиран през поддържания UI/API flow.

### admin

- preview/import на Excel графици;
- ръчни корекции;
- редакция на employee metadata;
- import history и audit history;
- няма управление на административни акаунти.

### moderator

- preview/import на Excel графици;
- търсене на служители и зареждане на месец;
- редактиране на дневните записи на графика;
- не може да редактира име или постоянна смяна на служителя;
- няма account management, import history или audit history.

## First-run web installer

След качване на проекта и стартиране на Python/ASGI приложението, ако няма завършена инсталация, първото отваряне на сайта автоматично пренасочва към:

```text
/install
```

Wizard-ът изпълнява:

1. проверка на Python/Alembic и права за запис;
2. избор между SQLite и PostgreSQL;
3. тест на database връзката;
4. `alembic upgrade head` към избраната база;
5. създаване на единствения owner чрез имейл и парола;
6. генериране на случаен JWT secret;
7. запис на `.env`;
8. изключване на bootstrap admin login-а;
9. създаване на `install/install.lock`;
10. изискване за restart/reload на Python приложението.

Owner паролата не се записва в `.env`. В базата остава само нейният scrypt hash.

След успешна инсталация installer-ът е заключен и повторна web инсталация не е разрешена.

### Важно за FTP hosting

FTP само качва файловете. MMI2 не е PHP приложение - hosting средата трябва да може да стартира Python ASGI приложение чрез например:

- Python App / Passenger в hosting control panel;
- VPS + systemd;
- Docker;
- друг ASGI-compatible deployment.

При PostgreSQL самата database трябва предварително да съществува. Installer-ът създава таблиците и индексите чрез Alembic.

Повече информация: `install/README.md`.

## Архитектура

```text
Excel (.xlsx)
    |
    +--> period detector
    |
    +--> preview (без запис)
    |
    +--> confirm import
            |
            +--> Employee
            |      - work_number
            |      - full_name
            |      - team (А/Б/В/Г)
            |
            +--> ShiftEntry
            |      - date
            |      - type
            |      - raw_code
            |
            +--> ImportHistory
                   - filename
                   - year/month
                   - employee/shift counts
                   - conflicts/duplicates
                   - SHA-256

Employee data
    +--> Web calendar
    +--> REST API --> Android app
```

Backend: FastAPI + SQLAlchemy + OpenPyXL.

## Стартиране локално

За стандартен manual setup:

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m alembic upgrade head
uvicorn app.main:app --reload
```

Linux/macOS:

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m alembic upgrade head
uvicorn app.main:app --reload
```

Алтернативно, за чиста инсталация можеш да стартираш приложението без предварително създаден owner и да използваш `/install` wizard-а.

Приложението не създава или променя database schema автоматично при нормален runtime. Schema промени се изпълняват чрез Alembic; единственото изключение е изрично стартираният first-run installer, който при потвърждение извиква Alembic към избраната база.

Отвори `http://127.0.0.1:8000`.

Admin: `http://127.0.0.1:8000/admin`.

Admin accounts: `http://127.0.0.1:8000/admin/accounts`.

Swagger/OpenAPI: `http://127.0.0.1:8000/docs`.

## Docker

```bash
cp .env.example .env
docker compose up --build
```

Docker изпълнява `alembic upgrade head` автоматично преди стартиране на Uvicorn.

## API

### Вход на служител

`POST /api/v1/auth/login`

```json
{
  "work_number": "12345"
}
```

### Текущ служител

`GET /api/v1/me`

```text
Authorization: Bearer <token>
```

### Месечен график

`GET /api/v1/me/schedule/{year}/{month}`

Пример:

```text
GET /api/v1/me/schedule/2026/7
```

### Preview преди импорт

`POST /api/v1/admin/preview`

Multipart fields:

- `file` - задължително;
- `year` - по избор;
- `month` - по избор.

Ако `year` и `month` са пропуснати, системата се опитва да ги разпознае от Excel файла, името на листа, Excel date клетки, текстови заглавия или името на файла.

Ако разпознаването не е достатъчно сигурно, API връща грешка и изисква ръчно задаване на периода.

### Потвърден импорт

`POST /api/v1/admin/import`

Използва същите полета като preview endpoint-а. При успешен импорт се създава запис в `ImportHistory` в същата DB транзакция като самия график.

### История на импортите

`GET /api/v1/admin/imports`
