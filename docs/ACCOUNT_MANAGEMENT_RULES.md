# Account Management Rules

## Roles

- `admin`: can manage accounts and access finance.
- `dispatcher`: can use dispatch operations, but cannot manage accounts or access finance.
- `operations_manager`: can view vehicle, driver, maintenance, map, incidents, and operational reminders, but cannot manage accounts or access finance.
- `driver`: uses only the driver-side runtime and sees only their own work data.

## Account Lifecycle

- New accounts are created from the admin settings page.
- The initial password defaults to the last 6 digits of the phone number.
- Driver accounts must match an existing driver ledger phone number.
- Non-driver accounts create or bind an operator profile.
- Disabled accounts are not physically deleted. They are marked inactive and cannot log in.
- Password reset changes the password back to the phone-number last 6 digits.

## WeChat Binding

- Driver miniapp and dispatcher miniapp logins bind the first successful login WeChat identity.
- A mismatched WeChat identity is rejected.
- Admin can remove the WeChat binding from Settings so the user can bind again next time.
- Web admin console login does not require WeChat binding in this round.

## Audit

The following actions write to `audit_logs`:

- account creation
- account disable
- password reset
- WeChat unbind
- role update

## Finance Visibility

Finance APIs and the React sidebar finance entry are admin-only. Dispatchers and operations managers cannot access finance data.
