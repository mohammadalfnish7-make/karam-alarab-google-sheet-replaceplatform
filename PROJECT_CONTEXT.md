# Project context: Karam Al Arab Load Plan platform

You are helping discuss and plan work on **Karam Al Arab Load Plan** — an internal web app that replaces Google Sheets / Excel workbooks for cargo, containers, exits, expenses, and related ops. Stack: **FastAPI + SQLAlchemy + Postgres** (backend), **React + TypeScript + React Router** (frontend), **Docker Compose**, cookie JWT auth (`admin` / `operator`).

## Purpose

Replace spreadsheet workflows for:

1. Sea / air cargo receiving and status
2. Exit (customs submission) records
3. Container tracker + related sheets (air tracker, COO, flight schedule)
4. Document expiry reminders
5. Newer standalone modules: container loading photos vs plan, expenses (Qusai), air shipment pictures
6. LLM-assisted intake (delivery note / scale photos) and PDF extraction

On startup the API can import: main load-plan workbook, document expiry sheet, and container tracker Excel (paths from env).

---

## Domain entities (database models)

### Auth & lookups

| Entity | Table | Notes |
|--------|-------|-------|
| **User** | `users` | email, password_hash, role (`admin`/`operator`), is_active |
| **Customer** | `customers` | customer code (TL marks); unique case-insensitive |
| **Company** | `companies` | supplier/company names |
| **Supplier** | `suppliers` | exit suppliers |

### Core cargo / exit (legacy load plan)

| Entity | Table | Key fields |
|--------|-------|------------|
| **SeaCargo** | `sea_cargo` | date_received, customer_code, company_name, cartons, gross/net weight, gross_is_no_pallet, system_code (DL…), shipment_number (D…), shipping_route (IRAN/TURKEY), stage (WH → delivered), legacy/needs_review/issues, soft delete |
| **AirCargo** | `air_cargo` | Same shape as sea but `status` instead of stage/route; shipment_number often AR… |
| **ExitRecord** | `exit_records` | `no` (unique when active), mark, supplier, invoice_no + invoice_numbers[], cartons, date_of_submission, status |
| **ImportBatch** | `import_batches` | Tracks which Excel filename was imported |

### Tracker workbook sheets

| Entity | Table | Purpose |
|--------|-------|---------|
| **ContainerRow** | `container_rows` | Cont Tracker: date, inv_no, qr, previous_cont, container_no, kgs, carton, driver, info/notes, foreign_invoice, russian_instrct, supplier_buyer, status, stage (этап 1–6), extra_json |
| **AirShipmentTrackerRow** | `air_shipment_tracker_rows` | Ref No, vendor, airline, date, item, cartons, weight, AWB, status, comment |
| **CooRow** | `coo_rows` | SR, inv_number, container_no, kjs, grg, k_exit |
| **FlightScheduleRow** | `flight_schedule_rows` | airline, date, day, narrow/wide, status |

### Standalone ops modules (newer)

| Entity | Table | Purpose |
|--------|-------|---------|
| **ContainerLoading** | `container_loadings` | Unique `mark` when active; optional container_no + link to container_row; plan_json/plan_filename; check_json (plan vs photos); summary_json; photos via CargoFile |
| **Expense** | `expenses` | Unique `mark`; date, amount, currency (AED default), notes; summary_json from LLM receipt read; budget concept on API |
| **AirShipmentPicture** | `air_shipment_pictures` | Unique `number` (AR-style); date; cartons; photo files |

### Files & AI

| Entity | Table | Purpose |
|--------|-------|---------|
| **CargoFile** | `cargo_files` | Polymorphic evidence: entity_type + entity_id; kind `note` \| `scale` \| `loading`; stored path, sha256, extracted_json; soft delete |
| **PdfDocument** / **PdfExtraction** | `pdf_documents` / `pdf_extractions` | Upload PDF → LLM extract → confirm rows into sea/air/exit |
| **DocumentExpiry** | `document_expiries` | company / employee / vehicle docs with expiry_date |
| **PromptKey** / **PromptVersion** | `prompt_keys` / `prompt_versions` | Versioned LLM prompts editable in Settings |
| **AppSetting** | `app_settings` | e.g. llm_model, llm_timeout_sec |
| **AgentRun** | `agent_runs` | Trace of LLM agent calls (steps, provider, model, errors) |
| **AuditLog** | `audit_log` | before/after JSON + changed_fields for create/update/delete/photos/etc. |
| **RequestLog** | `request_logs` | HTTP request middleware log |

### Shared patterns

- Soft delete: `deleted_at` / `deleted_by`; restore is admin-only on most entities
- Legacy import rows: `legacy`, `needs_review`, `issues[]`
- Audit + per-row history endpoints
- Unique marks/numbers often partial unique indexes where `deleted_at IS NULL`

### Enums (constants)

- **Sea stages**: 📦 WH, STAGE 1–4, 6, LOADING, OFF LOADING, WAITING, delivered to customer✅
- **Air statuses**: AT AIRPORT, delivered to customer✅
- **Exit statuses**: DONE, Submitted, Pending, received docs, CANCELED, NIL
- **Container stages**: этап 1 … этап 6
- **Shipping routes**: IRAN, TURKEY

---

## Backend (what exists)

**Framework:** FastAPI under `backend/app/`, routers mounted at `/api/*`.

### Routers / APIs

| Area | Prefix / routes | Capabilities |
|------|-----------------|--------------|
| Auth | `/api/auth` | login, logout, me (cookie JWT) |
| Overview | `/api/dashboard`, `/api/shipments` | Counts/breakdowns; combined shipment list |
| Records | `/api/sea`, `/api/air`, `/api/exit` | Full CRUD, soft delete/restore, history, cargo files upload/list/view/download; sea next-shipment helper |
| Lookups | `/api/lookups` | customers, companies, suppliers, users, enums |
| Intake | `/api/intake` | `read` + `read-batch` — LLM reads note/scale images in parallel |
| PDF | `/api/pdf` | upload → extract → confirm into records |
| Container tracker sheets | `/api/containers`, `/air-tracker`, `/coo`, `/flight-schedule` | CRUD + history; containers also have cargo files |
| Container loading | `/api/container-loading` | CRUD, next-mark, plan upload/clear, summarize, photo files, per-file LLM extract + edit extracted marks, plan-vs-photo check |
| Expenses | `/api/expenses` | CRUD, next-mark, budget, summarize receipts, receipt files |
| Air shipment pictures | `/api/air-shipment-pictures` | CRUD, next-number, photo files |
| Expiry | `/api/expiry` | list/patch + history |
| Audit / Agent runs / Request logs | `/api/audit`, `/agent-runs`, `/request-logs` | Admin observability |
| Users | `/api/users` | Admin user management |
| Settings | `/api/settings` | Prompt list/get/put/rollback; app settings (LLM model/timeout) |

### Important services

- `importer.py` — main load-plan Excel
- `container_import.py` — container tracker workbook
- `expiry_import.py` — document expiry
- `cargo_files.py` — shared file storage for sea/air/containers/loading/expenses/air pictures
- `container_loading_extract.py` / `container_loading_plan.py` — photo OCR-style extract + Excel plan parse + check against plan
- `expense_summarize.py` — receipt LLM summary
- `pdf_service.py` + `agents/` providers (Anthropic default) — pluggable LLM
- `prompt_store.py` / `prompt_defaults.py` — versioned prompts:
  - `intake.note`, `intake.scale`
  - `pdf.sea`, `pdf.air`, `pdf.exit`
  - `expenses.receipt`
  - `container_loading.photo`, `container_loading.check`
- `validation.py`, `audit.py`, `records.py` — shared save/validate/soft-delete

### Migrations

Alembic versions through ~0015 (prompt settings, container tracker, stage, soft-delete cargo files, container loading, expenses, air shipment pictures, loading plan check, unique mark soft-delete, etc.).

---

## Frontend (what exists)

**App shell** (`App.tsx`): auth gate, top nav, routes.

| Route | Page | What it does |
|-------|------|----------------|
| `/login` | LoginPage | Cookie auth |
| `/dashboard` | DashboardPage | Admin: sea/air/exit summaries |
| `/tracker` | TrackerPage | Shipment progress overview |
| `/sea`, `/air` | CargoPage | Table + drawer CRUD, review flags, file attachments (note/scale), history, soft delete |
| `/exit` | ExitPage | Exit records CRUD + history |
| `/containers` | SheetTrackerPage | Cont Tracker sheet CRUD (stage select, etc.) |
| `/air-tracker`, `/coo`, `/flight-schedule` | SheetTrackerPage | Same generic sheet UI, different field configs |
| `/container-loading` | ContainerLoadingPage | Marks, container link, loading photos, LLM extract of left/right pallets, Excel plan upload, plan-vs-photo check, summarize |
| `/expenses` | ExpensesPage | Expense marks, amounts, currencies, budget bar, receipt upload + LLM summarize |
| `/air-shipment-pictures` | AirShipmentPicturesPage | AR number + cartons + photos |
| `/expiry` | ExpiryPage | Document expiry list/edit |
| `/audit` | AuditPage | Human-friendly audit trail |
| `/pdf` | PdfPage | PDF upload → extract → confirm into sea/air/exit |
| `/runs` | AgentRunsPage | Admin: LLM run traces |
| `/users` | UsersPage | Admin user CRUD |
| `/settings` | SettingsPage | Admin: edit/rollback prompts + LLM app settings |

Shared UI: `ui.tsx` (Drawer, Field, History, Pager, warnings/issues), `api.ts` (fetch + audit helpers), `types.ts`, `styles.css`. Auth via `auth.tsx` (admin vs operator nav visibility).

---

## Cross-cutting product rules (useful for design discussions)

1. Soft delete everywhere critical; restores often admin-only.
2. Marks / system codes matter: TL customer marks, DL system codes, D/AR shipment numbers — prompts normalize TL to digits carefully.
3. Air shipment: carton without pallet; max weight guidance ~5T (README).
4. Cargo files are polymorphic (`entity_type` + `entity_id`), not FK per table.
5. Container loading workflow: create mark → upload photos → extract marks per pallet → upload Excel plan → check plan vs photos → optional summarize.
6. Expenses: auto next mark, optional budget, multi-receipt summarize into `summary_json`.
7. LLM failures should not invent data (upload may succeed; extract can 503 without key).
8. Roles: operators use operational pages; admins get dashboard, users, settings, agent runs, include-deleted filters.

---

## What to discuss with me

Use this context to discuss architecture, UX, data model changes, new features, bugs, or PR scope. When proposing changes, respect existing entities, soft-delete/audit patterns, and the FastAPI router + React page pairing above.

**Ask me what you want to change or clarify first; do not assume greenfield.**
