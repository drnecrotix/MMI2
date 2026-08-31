# GitHub update checker

MMI2 има update checker в административния панел и отделен safe self-update CLI за N0C/cPanel deployment.

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

Самото прилагане на update не се изпълнява вътре в активна HTTP заявка. За production се използва SSH/Terminal командата `update_mmi2.py`, която има backup и rollback защити.

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

## Safe self-update

Проверка от terminal:

```bash
python update_mmi2.py check --force
```

Preflight на конкретен merge-нат PR:

```bash
python update_mmi2.py preflight 19
```

Прилагане след успешен preflight:

```bash
python update_mmi2.py apply 19 --yes
```

Подробната backup, migration и rollback логика е описана в:

```text
docs/self-update.md
```
