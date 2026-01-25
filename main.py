import asyncio
import signal
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.utils.config import AppSettings, load_agents_from_yaml
from src.storage.database import init_db, get_session_factory
from src.core.agent_manager import AgentManager
import structlog

logger = structlog.get_logger()

async def main():
    # 1. Load Settings
    settings = AppSettings()
    structlog.configure(
        processors=[
            structlog.processors.JSONRenderer()
        ]
    )
    
    logger.info("starting_luxelink_agent")

    # 2. Initialize Database
    engine = await init_db(settings.DATABASE_URL)
    session_factory = get_session_factory(engine)

    # 3. Load Agents
    agents_config = load_agents_from_yaml("config/agents.yaml")
    if not agents_config:
        logger.error("no_agents_found_in_config")
        return

    # 4. Initialize Manager
    manager = AgentManager(session_factory, settings, agents_config)

    # 5. Setup Scheduler
    scheduler = AsyncIOScheduler()
    
    # Run all active agents from database every 4 hours (default)
    # The manager.run_all_agents now pulls directly from the DB
    scheduler.add_job(
        manager.run_all_agents,
        'interval',
        hours=4
    )
    
    # Also run once immediately on startup
    await manager.run_all_agents()

    scheduler.start()
    logger.info("scheduler_started")

    # Keep the script running
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        logger.info("shutting_down")
        scheduler.shutdown()
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
