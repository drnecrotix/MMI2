# Employee schedule API

MMI2 employee web portal and future mobile applications use the same REST API. The browser UI must not contain a second schedule calculation implementation that disagrees with the API.

## Authentication

Employee access currently uses the employee work number only.

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "work_number": "12345"
}
```

Successful response:

```json
{
  "access_token": "...",
  "token_type": "bearer",
  "employee_name": "Example Employee",
  "work_number": "12345",
  "team": "А"
}
```

The returned token is sent as:

```http
Authorization: Bearer <token>
```

The web portal stores it only in `sessionStorage`, so closing the tab/browser session removes the local copy.

> Work-number-only authentication is intentionally the current product requirement, but it is not strong identity verification. A future production hardening step can add a PIN, activation code, OTP or corporate SSO without changing the monthly schedule response contract.

## Employee profile

```http
GET /api/v1/me
```

Returns the authenticated employee's work number, full name and permanent team.

## Monthly schedule

```http
GET /api/v1/me/schedule/{year}/{month}
```

Example:

```http
GET /api/v1/me/schedule/2026/9
```

The response is designed to be consumed identically by the website and a future Android/iOS application.

Important fields:

- `employee_name`
- `work_number`
- `team`
- `year`
- `month`
- `days_in_month`
- `schedule_source`
- `schedule_status`
- `is_estimated`
- `is_partial`
- `missing_days`
- `warning`
- `summary`
- `shifts`
- fallback metadata when an automatic 2x2 schedule is used

### schedule_status

Possible values:

- `official` - full official/imported month
- `partial` - at least one official entry exists, but one or more calendar days have no official record
- `estimated` - no official entries exist for the month and the API returns the automatic 2x2 fallback

### Complete month contract

`shifts` represents every calendar day in the selected month.

If an official month is incomplete, missing dates are returned explicitly:

```json
{
  "work_date": "2026-09-02",
  "shift_type": "missing",
  "raw_code": "",
  "estimated": false
}
```

Clients must never interpret a missing day as a rest day.

### Shift types

Official values:

- `day`
- `night`
- `leave`
- `sick_leave`
- `rest`
- `unknown`
- `missing`

Automatic fallback values:

- `predicted_work`
- `predicted_rest`

A fallback work day deliberately does not invent whether the shift is day or night.

### summary

The API returns precomputed monthly totals:

```json
{
  "day": 10,
  "night": 8,
  "leave": 2,
  "sick_leave": 0,
  "rest": 10,
  "unknown": 0,
  "predicted_work": 0,
  "predicted_rest": 0,
  "missing": 0
}
```

Mobile clients should use this object instead of implementing a different counting algorithm.

## Web/mobile compatibility rule

The employee website is one client of this API, not the source of schedule truth. Any future Android/iOS client should render the same `schedule_status`, `summary`, `shifts` and warning fields instead of re-creating schedule rules locally. This keeps the website and mobile app consistent after future backend changes.

## Mobile application guidance

A future mobile app can reuse the API directly:

1. login with work number;
2. store the Bearer token using platform secure/session storage;
3. call `/api/v1/me` for profile data;
4. call `/api/v1/me/schedule/{year}/{month}` for calendar data;
5. render official, partial and estimated states using `schedule_status`;
6. never infer a rest day from missing data.

No employee Excel parsing should happen in the mobile application.
