# Vehicle Search Agent System

An automated agent system that monitors luxury vehicle listings and notifies you of matches.

## Features
- **Multi-Agent Support:** Define multiple search profiles in `config/agents.yaml`.
- **Async Architecture:** Built with Python 3.12, SQLAlchemy 2.0, and Playwright for high performance.
- **Neon PostgreSQL:** Persistent storage for listings and deduplication.
- **Bring A Trailer Integration:** Scrapes BaT auctions using headless Chrome.
- **Email Notifications:** Instant alerts via Gmail SMTP.

## Setup

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **Configure Environment:**
   Edit `.env` with your Neon Database URL and Gmail App Password.
   ```env
   DATABASE_URL=postgresql+asyncpg://...
   GMAIL_USER=your-email@gmail.com
   GMAIL_APP_PASSWORD=your-app-password
   ```

3. **Define Agents:**
   Edit `config/agents.yaml` to add your clients' search parameters.

4. **Run the Background Agent:**
   ```bash
   python main.py
   ```

5. **Run the User Interface:**
   ```bash
   streamlit run src/ui/app.py
   ```

## Project Structure
- `src/core/`: Orchestration and filtering logic.
- `src/data/`: Data providers (Scrapers/APIs).
- `src/storage/`: Database models and connection.
- `src/notifications/`: Email alerting.
- `config/`: YAML configuration files.
