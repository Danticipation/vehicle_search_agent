import asyncio
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.storage.database import Agent, Listing
from src.utils.config import AgentConfig
from src.core.filter_engine import FilterEngine
from src.data.providers.bring_a_trailer import BringATrailerProvider
from src.data.providers.cars_com import CarsComProvider
from src.data.providers.carfax import CarfaxProvider
from src.data.providers.autonation import AutoNationProvider
from src.data.providers.marketcheck import MarketcheckProvider
from src.notifications.email_client import EmailClient
import structlog

logger = structlog.get_logger()

class AgentManager:
    def __init__(self, session_factory, settings, agents_config: List[AgentConfig]):
        self.session_factory = session_factory
        self.settings = settings
        self.agents_config = agents_config
        self.filter_engine = FilterEngine()
        self.email_client = EmailClient(
            hostname="smtp.gmail.com",
            port=587,
            username=settings.GMAIL_USER,
            password=settings.GMAIL_APP_PASSWORD
        )
        
        # Initialize providers
        self.providers = {
            "bringatrailer": BringATrailerProvider(),
            "cars_com": CarsComProvider(),
            "carfax": CarfaxProvider(),
            "autonation": AutoNationProvider(),
            "marketcheck": MarketcheckProvider(api_key=settings.MARKETCHECK_API_KEY)
        }

    async def run_all_agents(self):
        logger.info("starting_all_agents_run")
        
        # Load agents from database to ensure we have the latest modular profiles
        async with self.session_factory() as session:
            stmt = select(Agent).where(Agent.enabled == True)
            result = await session.execute(stmt)
            db_agents = result.scalars().all()
            
        tasks = []
        for db_agent in db_agents:
            try:
                agent_cfg = AgentConfig(**db_agent.config_json)
                tasks.append(self.run_agent(agent_cfg))
            except Exception as e:
                logger.error("failed_to_parse_agent_config", agent_id=db_agent.id, error=str(e))
        
        if tasks:
            await asyncio.gather(*tasks)
        logger.info("finished_all_agents_run")

    async def run_agent(self, agent_cfg: AgentConfig):
        logger.info("running_agent", agent_id=agent_cfg.id)
        
        all_raw_listings = []
        params_dict = agent_cfg.parameters.model_dump()
        
        for source in agent_cfg.sources:
            provider = self.providers.get(source)
            if not provider:
                continue
                
            try:
                # Some providers (like BaT) return all listings at once and don't need per-vehicle loops
                if source == "bringatrailer":
                    raw = await provider.search(params_dict)
                    all_raw_listings.extend(raw)
                    continue

                # If specific vehicles are defined, we may need multiple searches per provider
                if agent_cfg.parameters.vehicles:
                    consecutive_failures = 0
                    for vehicle in agent_cfg.parameters.vehicles:
                        # Create a temporary params dict for this specific vehicle search
                        v_params = params_dict.copy()
                        v_params["makes"] = [vehicle.make]
                        v_params["models"] = [vehicle.model]
                        v_params["year_min"] = vehicle.year_min
                        v_params["year_max"] = vehicle.year_max
                        
                        try:
                            raw = await provider.search(v_params)
                            if raw:
                                all_raw_listings.extend(raw)
                                consecutive_failures = 0
                            else:
                                consecutive_failures += 1
                            
                            # If a scraper fails 5 times in a row, it's likely blocked or down
                            # Increased from 3 to 5 because rare vehicles often return 0 results
                            # We only skip if we are reasonably sure it's a block, not just 0 results.
                            # For now, we'll keep the counter but maybe we should check provider-specific block flags.
                            if consecutive_failures >= 10 and source not in ["marketcheck", "bringatrailer"]:
                                logger.warn("provider_likely_blocked_skipping", source=source)
                                break
                                
                            # Add a small human-like delay between vehicle searches for scrapers
                            if source != "marketcheck":
                                await asyncio.sleep(2)
                        except Exception as e:
                            logger.error("vehicle_search_failed", source=source, vehicle=vehicle.model, error=str(e))
                            consecutive_failures += 1
                else:
                    raw = await provider.search(params_dict)
                    all_raw_listings.extend(raw)
            except Exception as e:
                logger.error("provider_search_failed", source=source, error=str(e))

        # Filter and Store
        new_matches = []
        async with self.session_factory() as session:
            # Ensure agent exists in DB
            db_agent = await session.get(Agent, agent_cfg.id)
            if not db_agent:
                db_agent = Agent(id=agent_cfg.id, name=agent_cfg.name, config_json=agent_cfg.model_dump())
                session.add(db_agent)
                await session.commit()

            for raw in all_raw_listings:
                is_match, score = self.filter_engine.evaluate(raw, agent_cfg.parameters)
                if is_match:
                    # Check if already exists
                    stmt = select(Listing).where(Listing.external_id == raw.external_id)
                    result = await session.execute(stmt)
                    existing = result.scalar_one_or_none()
                    
                    if not existing:
                        new_listing = Listing(
                            agent_id=agent_cfg.id,
                            source=raw.source,
                            external_id=raw.external_id,
                            url=raw.url,
                            title=raw.title,
                            price=raw.price,
                            mileage=raw.mileage,
                            year=raw.year,
                            make=raw.make,
                            model=raw.model,
                            raw_json=raw.raw_data,
                            match_score=score
                        )
                        session.add(new_listing)
                        new_matches.append(new_listing)
            
            await session.commit()

            if new_matches:
                logger.info("new_matches_found", agent_id=agent_cfg.id, count=len(new_matches))
                to_emails = agent_cfg.notifications.get("email_to", [self.settings.GMAIL_USER])
                await self.email_client.send_listing_alerts(to_emails, agent_cfg.name, new_matches)
                
                # Mark as alerted
                for m in new_matches:
                    m.alerted = True
                await session.commit()
