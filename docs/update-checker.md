# GitHub update checker

MMI2 има read-only update checker в административния панел.

## Какво се счита за update

За production update се приемат само pull request-и, които:

- са в `drnecrotix/MMI2`;
- са merge-нати;
- са merge-нати към `main`;
- имат PR номер по-голям от `CURRENT_PR` в `app/version.py`.

Open, draft или затворен без merge PR не се предлага като update.

## Admin UI

`owner` и `admin` виждат секция **Обновления** в `/admin`.

Тя показва:

- текуща версия;
- текущ build PR;
- дали има нов merge-нат PR;
- номера и заглавието на най-новия update;
- линк към PR-а в GitHub.

`moderator` няма достъп до update проверката.

## API

```text
GET /api/v1/admin/update/check
```

Принудително обновяване на cache-а:

```text
GET /api/v1/admin/update/check?force=true
```

Изисква валиден admin JWT и роля `owner` или `admin`.

## GitHub API и cache

Проверката използва публичния GitHub REST API и фиксира repository-то в кода, за да няма произволни outbound URL заявки.

Резултатът се кешира за 10 минути, за да не се изразходва ненужно unauthenticated GitHub API rate limit.

## Какво не прави тази версия

Update checker-ът не презаписва автоматично production файловете. Той само открива наличен merge-нат PR и дава линк към него.

Това е умишлено за първата версия на update системата: автоматичното self-update при N0C/cPanel трябва да има отделен backup, file replacement и rollback механизъм, преди да бъде разрешено безопасно.
