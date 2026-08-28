# MMI2 Schedule System

Уеб система за импорт, обработка и персонален преглед на месечни работни графици от Excel файлове.

## Какво има в MVP

- импорт на `.xlsx` файлове;
- автоматично откриване на колони за работен номер и име;
- автоматично откриване на колоните за дните от месеца;
- запис на дневна, нощна, почивка, компенсация, отпуск и неизвестни кодове;
- повторният импорт обновява съществуващ график вместо да създава дубликати;
- вход на служител чрез работен номер;
- JWT access token след вход;
- персонален месечен календар;
- REST API, подходящ за бъдещо Android native приложение;
- защитен административен endpoint за Excel импорт;
- SQLite по подразбиране и готовност за PostgreSQL чрез `DATABASE_URL`;
- Dockerfile и Docker Compose.

## Архитектура

```text
Excel (.xlsx)
    |
    v
FastAPI import service
    |
    +--> employees
    +--> shift_entries
    |
    +--> Web UI
    |
    +--> REST API --> бъдещо Android приложение
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

Swagger/OpenAPI документацията е на `http://127.0.0.1:8000/docs`.

## Docker

```bash
cp .env.example .env
docker compose up --build
```

## Excel формат

Parser-ът не е заключен към точна позиция на колоните. Търси заглавия като:

- `Работен номер`, `Табелен номер`, `Work number`;
- `Име`, `Име на служителя`, `Employee`;
- колони за дни `1` до `31` или Excel date клетки.

Начално разпознаваеми кодове:

| Код | Тип |
| --- | --- |
| Д / ДН / ДНЕВНА | day |
| Н / НОЩ / НОЩНА | night |
| П / ПОЧ / ПОЧИВКА | rest |
| К / КОМП / КОМПЕНСАЦИЯ | compensation |
| О / ОТП / ОТПУСК | leave |

Всеки непознат код се съхранява като `raw_code` и тип `unknown`, така че реалните означения могат да бъдат добавени без загуба на данни.

## API

### Вход

`POST /api/v1/auth/login`

```json
{
  "work_number": "12345"
}
```

### Текущ служител

`GET /api/v1/me`

Header:

```text
Authorization: Bearer <token>
```

### Месечен график

`GET /api/v1/me/schedule/{year}/{month}`

Пример:

```text
GET /api/v1/me/schedule/2026/9
```

### Импорт на график

`POST /api/v1/admin/import`

Multipart fields:

- `year`
- `month`
- `file`

Header:

```text
X-Admin-Key: <ADMIN_IMPORT_KEY>
```

## Сигурност

В MVP служителят влиза само с работен номер, както е заложено в първоначалната идея. Това е удобно за вътрешен прототип, но не е достатъчно сигурно за публична production система, защото работен номер може да бъде познат от друг човек.

Препоръчителна следваща стъпка преди реално публикуване:

- работен номер + персонален PIN/парола; или
- еднократен код/първоначална активация; или
- корпоративна идентификация, ако има налична такава.

## Следващи етапи

1. Изпитване с реален Excel файл от графика.
2. Добавяне на всички реални кодове и специфични формати.
3. Административен преглед/редакция на служители и смени.
4. История и версии на импортираните графици.
5. PostgreSQL за production.
6. Role-based admin authentication.
7. Android native клиент върху `/api/v1`.
8. Push notifications при промяна на графика.
9. Отбелязване на празници, извънреден труд и други специфични състояния.

## Privacy

Репото е public. Не качвай реални Excel файлове с имена, работни номера или други лични данни в GitHub. За тестове използвай анонимизирани примерни данни.
