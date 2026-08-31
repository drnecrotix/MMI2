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
- SQLite за development и PostgreSQL-ready `DATABASE_URL`;
- Dockerfile и Docker Compose;
- unit tests със синтетични данни;
- GitHub Actions CI за автоматично изпълнение на migrations и тестовете.

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

Приложението не създава или променя database schema автоматично при старт. След промени по схемата винаги изпълнявай Alembic migrations преди Uvicorn.

Отвори `http://127.0.0.1:8000`.

Admin: `http://127.0.0.1:8000/admin`.

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
