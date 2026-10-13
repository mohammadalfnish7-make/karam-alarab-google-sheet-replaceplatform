# Karam Al Arab load plan

Internal replacement for the sea, air, and exit workbook. The API imports `excel sheet/WM _NEW  Load Plan.xlsx` once on startup. The container tracker workbook is not imported.

## Air shipment

Take only the carton, without the pallet. Maximum weight is 5T.

Development sign-in, from `.env.example`: `admin@example.com` / `change-me`. Change `ADMIN_PASSWORD`, `JWT_SECRET`, and `POSTGRES_PASSWORD` before anyone else can reach the server. If those three values change, keep `DATABASE_URL` in sync with the Postgres user, password, and database name. Use a URL-safe database password, or edit `DATABASE_URL` in `docker-compose.yml` when the password contains reserved characters.

## Run

```bash
cp .env.example .env
docker compose up --build
```

Open http://localhost.

The first start applies database migrations, creates the admin user when the user table is empty, and imports the workbook if that filename has not been imported yet. Uploaded PDFs and the Postgres data directory are named Docker volumes (`pdf_uploads`, `postgres_data`).

PDF extraction calls Gemini only when `GEMINI_API_KEY` is set (`GEMINI_MODEL` defaults to `gemini-2.5-flash`). Without a key, upload still stores the file and extract returns 503. Nothing is invented in place of a real extraction.

## VPS

Install Docker Engine and the Compose plugin. Copy this project and a production `.env` onto the server. Point a DNS name at the machine and open TCP port 80. Then:

```bash
docker compose up -d --build
```

The web container serves the app on port 80 and proxies `/api` to the API. Put HTTPS in front of it (Caddy or a host reverse proxy) when the site is reachable beyond the office.

## Tests

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

Tests use SQLite. The import test reads the real workbook and expects 1859 sea rows, 549 air rows, 465 exit rows, and system code `DL3027`.
