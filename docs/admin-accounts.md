# Admin accounts and roles

MMI2 stores administrator accounts in the database. Passwords are never stored as plain text; they are hashed with `scrypt` and a random salt.

## First owner

When `admin_users` is empty, the first successful login using the bootstrap credentials creates the single `owner` account.

Preferred bootstrap settings:

```env
ADMIN_EMAIL=owner@example.com
ADMIN_PASSWORD=use-a-strong-password
```

`ADMIN_USERNAME` remains only as a compatibility fallback for installations upgrading from older versions.

After the first owner exists, normal admin login is validated only against the database account and its password hash.

## Roles

### owner

There is exactly one owner account in the supported UI/API flow.

The owner can:

- use all schedule administration features
- edit employee metadata
- view audit/import history
- create `admin` and `moderator` accounts
- activate/deactivate non-owner accounts
- change non-owner roles
- reset account passwords

The owner cannot be demoted or deactivated from the account management API.

### admin

An admin can:

- preview and import Excel schedules
- search employees and view their schedules
- edit employee metadata
- manually edit daily schedule entries
- view import and manual-edit audit history

An admin cannot manage administrator accounts.

### moderator

A moderator is schedule-only:

- preview Excel schedules
- import Excel schedules
- search employees so a schedule can be selected
- view a selected employee month
- manually edit daily schedule entries

A moderator cannot:

- edit employee name or permanent team
- view audit/import history
- create or manage administrator accounts

These restrictions are enforced by the backend API, not only by hiding controls in the web interface.
