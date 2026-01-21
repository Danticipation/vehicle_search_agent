import httpx
import datetime
from typing import List, Optional
from src.data.base_provider import BaseProvider, RawListing
import structlog

logger = structlog.get_logger()

# 12 Strategic Hubs to cover the Lower 48 with 100-mile radius
STRATEGIC_HUBS = [
    "10001", # New York, NY
    "30303", # Atlanta, GA
    "60601", # Chicago, IL
    "75201", # Dallas, TX
    "80202", # Denver, CO
    "90001", # Los Angeles, CA
    "98101", # Seattle, WA
    "33101", # Miami, FL
    "19102", # Philadelphia, PA
    "85001", # Phoenix, AZ
    "63101", # St. Louis, MO
    "94101", # San Francisco, CA
]

class MarketcheckProvider(BaseProvider):
    def __init__(self, api_key: str):
        self.source_name = "marketcheck"
        self.api_key = api_key
        self.base_url = "https://api.marketcheck.com/v2/search/car/active"

    async def search(self, params: dict) -> List[RawListing]:
        if not self.api_key:
            logger.error("marketcheck_api_key_missing")
            return []

        listings = []
        
        make = params.get("makes", [""])[0]
        model = params.get("models", [""])[0]
        year_min = params.get("year_min")
        
        # Improved Hub Rotation Logic
        # Uses day of year and hour to ensure we hit a new hub every 4 hours
        now = datetime.datetime.now()
        day_of_year = now.timetuple().tm_yday
        hour = now.hour
        # This formula ensures that if the agent runs every 4 hours, it increments the hub index by 1
        hub_index = (day_of_year * 6 + (hour // 4)) % len(STRATEGIC_HUBS)
        selected_zip = STRATEGIC_HUBS[hub_index]

        query_params = {
            "api_key": self.api_key,
            "make": make,
            "model": model,
            "year_start": year_min,
            "rows": 50,
            "radius": 100, # Basic plan limit
            "zip": selected_zip
        }

        logger.info("searching_marketcheck_hub", 
                    make=make, 
                    model=model, 
                    zip=selected_zip, 
                    hub_index=hub_index)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.base_url, params=query_params)
                response.raise_for_status()
                data = response.json()

                for item in data.get("listings", []):
                    try:
                        listings.append(RawListing(
                            external_id=str(item.get("id", "")),
                            source=self.source_name,
                            url=item.get("vdp_url", ""),
                            title=item.get("heading", f"{item.get('year')} {item.get('make')} {item.get('model')}"),
                            price=float(item.get("price")) if item.get("price") else None,
                            mileage=int(item.get("miles")) if item.get("miles") else None,
                            year=int(item.get("year")) if item.get("year") else None,
                            make=item.get("make"),
                            model=item.get("model"),
                            location=f"{item.get('city')}, {item.get('state')}",
                            raw_data=item
                        ))
                    except Exception:
                        continue
        except Exception as e:
            logger.error("marketcheck_search_failed", error=str(e))

        return listings
