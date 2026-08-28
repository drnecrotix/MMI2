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
- `.xlsx` импорт чрез OpenPyXL;
- разпознаване на реалния MMI2 формат с няколко блока в един лист;
- извличане на работен номер, име и смяна А/Б/В/Г;
- месечни записи за всички календарни дни;
- повторен импорт обновява съществуващите записи;
- засичане на повторни служители и конфликтни дни;
- вход чрез работен номер;
- JWT access token;
- responsive персонален календар;
- навигация между месеци;
- месечна статистика за дневни, нощни, отпуск, болничен и почивни дни;
- REST API за бъдещо Android native приложение;
- защитен административен endpoint за Excel импорт;
- SQLite за development и PostgreSQL-ready `DATABASE_URL`;
- Dockerfile и Docker Compose;
- unit tests със синтетични данни.

## Архитектура

```text
Excel (.xlsx)
    |
    v
MMI2 import service
    |
    +--> Employee
    |      - work_number
    |      - full_name
    |      - team (А/Б/В/Г)
    |
    +--> ShiftEntry
           - date
           - type
           - raw_code
    |
    +--> Web calendar
    |
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
uvicorn app.main:app --reload
```

Linux/macOS:

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Отвори `http://127.0.0.1:8000`.

Swagger/OpenAPI: `http://127.0.0.1:8000/docs`.

## Docker

```bash
cp .env.example .env
docker compose up --build
```

## API

### Вход на служител

`POST /api/v1/auth/login`

```json
{
  "work_number": "12345"
}
```

Примерен отговор:

```json
{
  "access_token": "...",
  "token_type": "bearer",
  "employee_name": "Иван Иванов",
  "work_number": "12345",
  "team": "В"
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

Примерен елемент:

```json
{
  "work_date": "2026-07-01",
  "shift_type": "day",
  "raw_code": "1"
}
```

### Импорт

`POST /api/v1/admin/import`

Multipart fields:

- `year`
- `month`
- `file`

Header:

```text
X-Admin-Key: <ADMIN_IMPORT_KEY>
```

## Web интерфейс

Основният екран е за служителя:

1. въвежда работния си номер;
2. системата намира служителя;
3. показва име, работен номер и смяна;
4. показва календара за текущия месец;
5. със стрелките може да се разглеждат други импортирани месеци.

Административният Excel импорт е отделен в свиваема секция.

## Сигурност

Текущото изискване е вход само чрез работен номер. Това е подходящо за прототип или ограничена вътрешна среда, но работният номер сам по себе си не е силен authentication фактор.

Преди публично production използване е препоръчително да се добави поне едно от следните:

- персонален PIN;
- парола;
- първоначална активация с еднократен код;
- корпоративна идентификация.

## Следващи етапи

1. Preview на Excel файла преди окончателен импорт.
2. История и версии на импортираните графици.
3. Административен списък със служители и ръчна корекция на график.
4. PostgreSQL за production.
5. Отделна admin authentication система.
6. Android native приложение върху `/api/v1`.
7. Push известия при промяна на графика.

## Privacy

Репото е public. Реални Excel файлове с имена и работни номера не трябва да се commit-ват в GitHub. За автоматични тестове се използват синтетични данни.
