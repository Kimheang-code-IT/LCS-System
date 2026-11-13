# LCS Finance — Mobile (Flutter)

A Finance & Accounting mobile client for the existing **LCS Freight Forwarding Management System**.
It is **not** a separate ERP: all data, business rules, permissions and document numbers come from
the existing FastAPI + PostgreSQL backend (`../backend`), enforced by Casbin exactly as for the web app.

- Framework: Flutter (stable), Dart 3 — Material 3, light professional theme
- State: Riverpod (flutter_riverpod 2.6), Navigation: go_router, HTTP: Dio (+ persistent cookie jar)
- Platforms: Android, iOS

## Prerequisites

- Flutter SDK (stable channel; verified with Flutter 3.44 / Dart 3.12)
- Android SDK + Java for the Android build; Xcode on macOS for iOS
- A reachable LCS backend (`../backend`) with at least one active user

## Setup

```powershell
cd mobile
flutter pub get
flutter gen-l10n        # only needed if arb files changed outside a build
```

## API configuration

The base URL is injected at build time — never committed:

```powershell
# Android emulator → host-local backend (uvicorn default port 8000)
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000

# Physical device → LAN address of the machine running the backend
flutter run --dart-define=API_BASE_URL=http://192.168.1.20:8000

# Production (HTTPS backend domain)
flutter build apk --release --dart-define=API_BASE_URL=https://lcs.example.com
```

Default if omitted: `http://10.0.2.2:8000` (Android emulator).

## Development commands

```powershell
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000
flutter analyze
flutter test
dart format .
flutter build apk --release --dart-define=API_BASE_URL=...
```

## Authentication flow

The app reuses the LCS login contract exactly like the web SPA:

1. `POST /api/v1/auth/login` (`email`/`username`, `password`, `remember_me`) — the backend sets
   HttpOnly `access_token` / `refresh_token` / `XSRF-TOKEN` cookies and (when `AUTH_RETURN_TOKENS=true`,
   the default) also returns `data.access_token`.
2. Cookies live in a persistent cookie jar backed by `flutter_secure_storage`; the access token is
   stored as a Bearer fallback. Bearer requests skip the backend's CSRF double-submit check; cookie-mode
   mutations automatically carry `X-CSRF-Token` from the jar.
3. `GET /api/v1/auth/me` restores the identity and the page-permission list on cold start.
4. On 401, the client calls `POST /api/v1/auth/refresh` once and replays the original request.
5. `POST /api/v1/auth/logout` clears the backend session; local cookies, tokens and cached data are wiped.

Passwords/tokens are never logged and never leave secure storage.

## Feature → API mapping

| Mobile screen | Backend endpoint | Notes |
|---|---|---|
| Login / logout / session | `/api/v1/auth/login`, `/auth/logout`, `/auth/me`, `/auth/refresh` | Existing web contract |
| Dashboard (4 cards + cash/bank) | `GET /api/v1/reports/dashboard` | `summary.receivables/payables/totalReceived/totalPaid/cashBankBalance`; `totalReceived`/`totalPaid` are a small additive backend extension (see below) |
| Accounts Receivable | `GET /api/v1/reports/receivables` | readOnly projection, backend balances |
| Accounts Payable | `GET /api/v1/reports/payables` | readOnly projection, backend balances |
| Customer Receipts | `GET /api/v1/financial-documents?document_type=CUSTOMER_RECEIPT` | create/edit draft, post with `Idempotency-Key` |
| Supplier Payments | `GET /api/v1/financial-documents?document_type=SUPPLIER_PAYMENT` | same lifecycle |
| Customer Invoices | `GET /api/v1/financial-documents?document_type=CUSTOMER_INVOICE` | print preview, post, reverse |
| Supplier Bills | `…document_type=SUPPLIER_BILL` | |
| Credit Notes | `…document_type=CREDIT_NOTE` | |
| Unified document browser | `GET /api/v1/financial-documents` | server pagination `page,page_size,q,status,from_date,to_date,sort_by` |
| Document detail | `GET /api/v1/financial-documents/{id}` | lines, allocations, posted journal, party names |
| Draft save | `POST/PUT /api/v1/financial-documents` | `DOCUMENT_WRITE_SCHEMA` + `lines`, as the web form posts |
| Post / reverse | `POST …/{id}/post`, `POST …/{id}/reverse` | both carry `Idempotency-Key` headers; reverse sends `{reason}` |
| Invoice print model | `GET /api/v1/financial-documents/{id}/print-data` | reconciled JSON → PDF rendered on device |
| Service Charges | `GET /api/v1/service-charges` (+`/{id}`) | one charge → many fee lines, backend totals |
| Journal Vouchers | `GET /api/v1/journal-entries` (+`/{id}`) | debit/credit lines, read-only on mobile |
| Trial Balance / General Ledger | `POST /api/v1/reports/trial-balance|general-ledger/generate` (+`/export` CSV) | on-demand generation, backend aggregation |

Permissions shown in the UI come from `/auth/me` `permissions` (page codes such as
`financial_document.submit`, `reports.accounts_receivable.view`); the backend remains the sole authority.

## Folder structure

```
mobile/
  lib/
    main.dart                 entry point
    app/                      router, theme, landing screens, MaterialApp
    core/
      api/                    Dio client (cookies, CSRF, bearer, 401 refresh), error mapping
      auth/                   session state controller
      config/                 --dart-define environment
      models/                 pagination envelope, paged-list state, paging extension
      utils/                  money/date/status formatting
      widgets/                record cards, summary rows, filter sheet, error/empty states, list scaffold
    features/
      authentication/         login screen
      dashboard/              exactly four summary cards
      documents/              financial-document list/detail/form/PDF preview (shared engine)
      service_charges/        charge list + fee-line detail
      journals/               journal voucher list + detail
      reports/                dashboard/AR/AP repository, trial balance & general ledger runner
  test/                       unit + widget tests
  integration_test/           end-to-end drive against a seeded backend
```

## Testing

```powershell
flutter test
# integration (device/emulator + seeded backend):
flutter test integration_test -d <device> `
  --dart-define=API_BASE_URL=http://10.0.2.2:8000 `
  --dart-define=TEST_USERNAME=... --dart-define=TEST_PASSWORD=...
```

Unit tests cover money/date/status formatting, document & pagination parsing, error mapping,
repository contracts (filters, idempotency, POST/PUT, 400/401/403/409 handling) and widgets
(login validation, exactly-four dashboard cards, empty/error states).

## Android emulator connection

```powershell
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

`10.0.2.2` is the emulator's alias for the host loopback. The dev compose stack
(`infrastructure/.env`) must include `10.0.2.2` in `ALLOWED_HOSTS` — otherwise
every request is rejected by the backend's trusted-host middleware with
`400 Invalid host header`, which the app surfaces as a connection error.

## Physical-device connection

The release APK has the backend URL baked in via `--dart-define`, so build (or
use) the variant that matches how the phone connects:

1. **USB + adb reverse (recommended, no firewall changes):**
   ```powershell
   adb reverse tcp:8000 tcp:8000        # re-run after each reconnect
   # APK built with: --dart-define=API_BASE_URL=http://localhost:8000
   ```
   The phone reaches the backend at `http://localhost:8000` through the USB
   cable. This variant was verified end-to-end on a device-class build.

2. **Wi-Fi/LAN:**
   ```powershell
   # APK built with: --dart-define=API_BASE_URL=http://<PC-LAN-IP>:8000
   ```
   Requires (a) the API published beyond loopback — `API_BIND_HOST=0.0.0.0` in
   `infrastructure/.env` (already set; only the API is exposed, the databases
   stay loopback-only), (b) `<PC-LAN-IP>` in `ALLOWED_HOSTS`, and (c) a Windows
   Firewall inbound rule for TCP 8000, run once as admin:
   ```powershell
   New-NetFirewallRule -DisplayName "LCS dev API (TCP 8000)" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000 -Profile Any
   ```

Cleartext HTTP in release builds is permitted **only** for the dev addresses
listed in `android/app/src/main/res/xml/network_security_config.xml`
(emulator alias, localhost/adb-reverse, dev-PC LAN IPs). Everything else stays
cleartext-forbidden. For a production HTTPS build, remove that file and the
`android:networkSecurityConfig` manifest attribute.

Prebuilt release APKs live in `mobile/releases/`:
`LCS-Finance-v1.0-usb.apk` and `LCS-Finance-v1.0-lan.apk` (built against
`http://localhost:8000` and `http://192.168.0.3:8000` respectively).

## Android release build

```powershell
flutter build apk --release --dart-define=API_BASE_URL=https://...
```

The main manifest declares `android.permission.INTERNET` (required for release builds).

## iOS build

`flutter build ios --release` on a macOS machine with Xcode + signing. **Not executed in this
environment (Windows); readiness only.** For LAN development on iOS, allow cleartext HTTP via
`NSAppTransportSecurity` in `ios/Runner/Info.plist` or use an HTTPS endpoint.

## Backend modification (kept minimal and backward-compatible)

`backend/app/modules/reports/service.py::dashboard` now also returns
`summary.totalReceived` and `summary.totalPaid` (sums of **posted** `CUSTOMER_RECEIPT` /
`SUPPLIER_PAYMENT` totals, same no-conversion convention as the existing receivables/payables
totals). Additive keys; the web app ignores them. Covered by
`backend/tests/test_reporting_values.py::test_dashboard_payment_totals_reflect_posted_documents`.

## Known limitations

- PDF print preview exists for **customer invoices** only — the backend `print-data` endpoint serves
  that document type exclusively (`printing.py`); other types show no print action rather than a fake one.
- Payment **allocation** between a receipt and invoices is displayed read-only in details; the
  allocate action needs an invoice-picker workflow and was left to the web app for now.
- Dashboard card totals follow the backend's document-currency sum convention (identical to the web
  dashboard). When a total mixes currencies the app shows a per-currency breakdown from
  `summary.*ByCurrency` (additive backend keys) instead of hiding the mixed unit; the base-currency
  ledger figure is `cashBankBalance`.
- Service Charges and Journals are read-only on mobile; their create/edit workflows remain on desktop.
- CSV export hands the file to the OS share sheet; PDF/Excel renderings of reports are not backend
  endpoints today, so none are faked.
- iOS build not verified here (no macOS toolchain).
- Most list/detail labels are English literals; the ARB (en/km) strings cover detail-screen labels
  and the app follows the device locale. A full Khmer rollout of every list label remains open.

## Integration testing against a dedicated test backend

Never point the app at the production database for tests. A dedicated seeded SQLite backend is
provisioned with the project's own seed tooling:

```powershell
# 1. Create the dedicated test database (insert-missing seeds, demo users admin/ops.pp/finance/sales)
backend/.venv/Scripts/python.exe backend/scripts/seed_mobile_test_db.py `
  "sqlite+aiosqlite:///C:/Users/<you>/AppData/Local/Temp/opencode/lcs-mobile-test/lcs.db"

# 2. Run a second backend instance on port 8010 against it
cd backend
$env:DATABASE_URL = "sqlite+aiosqlite:///C:/Users/<you>/AppData/Local/Temp/opencode/lcs-mobile-test/lcs.db"
$env:CACHE_ENABLED = "false"; $env:REDIS_ENABLED = "false"
$env:BACKUP_SCHEDULER_ENABLED = "false"; $env:TELEGRAM_WORKER_ENABLED = "false"
$env:ALLOWED_HOSTS = "localhost,127.0.0.1,testserver,10.0.2.2,host"
.venv/Scripts/uvicorn.exe app.main:app --host 127.0.0.1 --port 8010

# 3. Drive the real app on the emulator (no financial writes; reads seeded data)
cd ../mobile
flutter test integration_test -d emulator-5554 `
  --dart-define=API_BASE_URL=http://10.0.2.2:8010 `
  --dart-define=TEST_USERNAME=admin --dart-define=TEST_PASSWORD=Passw0rd!
```

Document write flows (draft → post → idempotency replay → reverse) were verified against this
backend with safe seeded records only (see the verification report).

## Troubleshooting

- **Login fails with network error** — the backend isn't reachable at the configured base URL; check
  `--dart-define=API_BASE_URL` (emulator: `10.0.2.2`, physical device: LAN IP; backend must listen on it).
- **403 on a module** — your LCS role lacks the page permission; grant it in the web admin.
- **Print preview errors** — the document is not a customer invoice, or stored totals fail the
  backend's reconciliation check (that is the backend protecting the document, not an app bug).
- **Dashboard shows stale values** — the backend caches report aggregates briefly; pull-to-refresh
  re-requests, and cache TTL applies server-side.
