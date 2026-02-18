import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.utils.config import AppSettings, load_agents_from_yaml
from src.storage.database import init_db, get_session_factory, Agent
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

    # 3. Load Agents from YAML and sync to DB (so first run has agents)
    agents_config = load_agents_from_yaml("config/agents.yaml")
    if not agents_config:
        logger.error("no_agents_found_in_config")
        return

    async with session_factory() as session:
        for ac in agents_config:
            existing = await session.get(Agent, ac.id)
            config_json = ac.model_dump()
            if existing:
                existing.name = ac.name
                existing.enabled = ac.enabled
                existing.config_json = config_json
            else:
                session.add(Agent(id=ac.id, name=ac.name, enabled=ac.enabled, config_json=config_json))
        await session.commit()
    logger.info("agents_synced_from_yaml", count=len(agents_config))

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
