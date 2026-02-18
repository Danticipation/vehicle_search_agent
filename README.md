# LuxeLink

An automated agent system that monitors luxury vehicle listings and notifies you of matches.

## Features
- **Multi-Agent Support:** Define multiple search profiles in `config/agents.yaml`.
- **Async Architecture:** Built with Python 3.12, SQLAlchemy 2.0, and Playwright for high performance.
- **Neon PostgreSQL:** Persistent storage for listings and deduplication.
- **Multi-Provider Integration:** Scrapes listings from Bring A Trailer, Carfax, Cars.com, and AutoNation using Playwright.
- **Marketcheck API Support:** Integrated with Marketcheck for high-quality vehicle data.
- **Email Notifications:** Instant alerts via Gmail SMTP.

## Setup

1. **Create and activate a virtual environment** (recommended):
   ```bash
   # Create venv
   python -m venv venv

   # Activate (Windows)
   venv\Scripts\activate        # CMD
   # or
   .\venv\Scripts\Activate.ps1  # PowerShell (see note below)

   # Activate (macOS/Linux)
   source venv/bin/activate
   ```
   **PowerShell:** If you see "running scripts is disabled", run:
   `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
   **Multiple Pythons:** Use `py -3.12 -m venv venv` to pick a specific version.

2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

3. **Configure Environment:**
   Edit `.env` with your Neon Database URL, Gmail App Password, and optional API keys.
   ```env
   DATABASE_URL=postgresql+asyncpg://...
   GMAIL_USER=your-email@gmail.com
   GMAIL_APP_PASSWORD=your-app-password
   MARKETCHECK_API_KEY=your-api-key (optional)
   ```

4. **Define Agents:**
   Edit `config/agents.yaml` to add your clients' search parameters.

5. **Run the Background Agent:**
   ```bash
   python main.py
   ```

6. **Run the User Interface:**
   ```bash
   streamlit run src/ui/app.py
   ```

## Project Structure
- `src/core/`: Orchestration and filtering logic.
- `src/data/`: Data providers (Scrapers/APIs).
- `src/storage/`: Database models and connection.
- `src/notifications/`: Email alerting.
- `config/`: YAML configuration files.

---

## Application Status & Next Steps to Go Live

### Current status (summary)

| Area | Status | Notes |
|------|--------|--------|
| **Core** | ✅ Ready | `main.py` loads settings, inits DB, syncs agents from YAML → DB, runs scheduler (every 4h + once on startup). |
| **Database** | ✅ Ready | Neon PostgreSQL via asyncpg; `agents` + `listings` tables created on startup; SSL handled for Neon. |
| **Agents** | ✅ Ready | YAML agents are synced to DB on startup; `AgentManager` runs enabled agents from DB; filter engine (make/model/year/price/mileage/excludes) works. |
| **Data providers** | ⚠️ Mixed | **Marketcheck** (API): solid if key set. **Bring A Trailer**: Playwright scraper; may need selector updates if site changes. **Cars.com / Carfax / AutoNation**: Playwright; risk of blocks or layout changes. |
| **Notifications** | ✅ Ready | Gmail SMTP (STARTTLS 587); HTML listing alerts. |
| **UI** | ✅ Ready | Streamlit dashboard: view listings, manage profiles (add/toggle/delete), run from UI (button is placeholder—does not call backend). |

**Fix applied:** Agents from `config/agents.yaml` are now upserted into the DB on startup, so the first run actually executes your configured agents (previously only DB agents ran, so a fresh DB did nothing).

### Next steps to get the application live and running

1. **Environment**
   - Create a **Neon** project and copy the connection string into `.env` as `DATABASE_URL` (use `postgresql+asyncpg://...`).
   - Set **Gmail**: `GMAIL_USER` and `GMAIL_APP_PASSWORD` (App Password, not normal password) in `.env`.
   - Optional: add `MARKETCHECK_API_KEY` in `.env` for Marketcheck results.

2. **Run locally**
   - From project root with venv activated:
     - `python main.py` — starts the agent (syncs YAML → DB, runs agents immediately, then every 4 hours).
     - `streamlit run src/ui/app.py` — opens the dashboard (ensure `main.py` has run at least once so DB has schema and agents).

3. **Optional improvements before production**
   - **“Run Now” in UI:** Wire the Streamlit “Run Now” button to the same logic as `manager.run_all_agents()` (e.g. small FastAPI/Flask API or subprocess call) so runs can be triggered from the dashboard.
   - **Scrapers:** Monitor logs for 403s or empty results; refresh Playwright selectors if sites change; consider rate limiting or proxy rotation if blocks increase.
   - **Deployment:** Run `main.py` as a long-lived process (systemd, Docker, or a PaaS like Railway/Render). Run Streamlit behind auth/reverse proxy if the UI is exposed.
   - **Secrets:** Keep `.env` out of git; use env vars or a secrets manager in production.
