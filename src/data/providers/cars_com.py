import asyncio
import re
import random
from typing import List, Optional
from playwright.async_api import async_playwright
from src.data.base_provider import BaseProvider, RawListing
import structlog

logger = structlog.get_logger()

class CarsComProvider(BaseProvider):
    def __init__(self):
        self.source_name = "cars_com"
        self.base_url = "https://www.cars.com/shopping/results/"

    async def search(self, params: dict) -> List[RawListing]:
        listings = []
        async with async_playwright() as p:
            # Enhanced stealth arguments
            browser = await p.chromium.launch(headless=True, args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--window-size=1920,1080"
            ])
            
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080},
                extra_http_headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"Windows"',
                }
            )
            page = await context.new_page()
            
            # Mask automation
            await page.evaluate("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            make = params.get("makes", [""])[0].lower()
            model = params.get("models", [""])[0].lower().replace(" ", "-")
            year_min = params.get("year_min", "")
            
            if make == "ford" and "raptor" in model:
                search_model = "ford-f-150-raptor"
            else:
                search_model = f"{make}-{model}"
            
            url = f"{self.base_url}?makes[]={make}&models[]={search_model}&zip=60601&distance=all"
            if year_min:
                url += f"&year_min={year_min}"
            
            logger.info("searching_cars_com", url=url)
            
            try:
                # WARM-UP: Visit the home page first to get cookies and look like a real user
                try:
                    await page.goto("https://www.cars.com/", wait_until="domcontentloaded", timeout=20000)
                    await asyncio.sleep(random.uniform(1, 2))
                except Exception:
                    pass # Continue even if warm-up fails

                # Navigate to search results
                response = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                
                if response and response.status == 403:
                    logger.error("cars_com_blocked_403")
                    return []

                # Wait for results or no-results indicator
                try:
                    await page.wait_for_selector(".vehicle-card, [data-testid='vehicle-card'], .no-results", timeout=15000)
                except Exception:
                    cards = await page.query_selector_all(".vehicle-card")
                    if not cards:
                        logger.warn("no_results_found_on_cars_com_timeout")
                        return []

                items = await page.query_selector_all(".vehicle-card, [data-testid='vehicle-card']")
                logger.info("cars_com_items_found", count=len(items))
                
                for item in items:
                    try:
                        title_el = await item.query_selector(".title, [class*='title']")
                        title = (await title_el.inner_text()).strip() if title_el else ""
                        if not title: continue

                        link_el = await item.query_selector("a.vehicle-card-link, a[href*='/vehicledetail/']")
                        url_attr = await link_el.get_attribute("href") if link_el else ""
                        if url_attr and not url_attr.startswith("http"):
                            url_attr = "https://www.cars.com" + url_attr
                        
                        price_el = await item.query_selector(".primary-price, [class*='price']")
                        price_text = (await price_el.inner_text()).strip() if price_el else ""
                        price = self._parse_price(price_text)
                        
                        mileage_el = await item.query_selector(".mileage, [class*='mileage']")
                        mileage_text = (await mileage_el.inner_text()).strip() if mileage_el else ""
                        mileage = self._parse_mileage(mileage_text)
                        
                        year_match = re.search(r'(\d{4})', title)
                        year = int(year_match.group(1)) if year_match else None
                        
                        ext_id_match = re.search(r'listing/(\d+)', url_attr)
                        ext_id = ext_id_match.group(1) if ext_id_match else url_attr
                        
                        listings.append(RawListing(
                            external_id=ext_id,
                            source=self.source_name,
                            url=url_attr,
                            title=title,
                            year=year,
                            price=price,
                            mileage=mileage,
                            raw_data={"price_text": price_text, "mileage_text": mileage_text}
                        ))
                    except Exception:
                        continue
                        
            except Exception as e:
                logger.error("cars_com_search_failed", error=str(e))
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass
                
        return listings

    def _parse_price(self, price_str: str) -> Optional[float]:
        if not price_str: return None
        # Remove everything except digits
        cleaned = re.sub(r'[^\d]', '', price_str)
        try:
            val = float(cleaned)
            # Sanity check: prices shouldn't be astronomical (e.g. concatenated strings)
            if val > 10000000: return None 
            return val
        except ValueError: return None

    def _parse_mileage(self, mileage_str: str) -> Optional[int]:
        if not mileage_str: return None
        cleaned = re.sub(r'[^\d]', '', mileage_str)
        try: return int(cleaned)
        except ValueError: return None
