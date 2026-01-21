import asyncio
import re
from typing import List, Optional
from playwright.async_api import async_playwright
from src.data.base_provider import BaseProvider, RawListing
import structlog

logger = structlog.get_logger()

class CarfaxProvider(BaseProvider):
    def __init__(self):
        self.source_name = "carfax"
        self.base_url = "https://www.carfax.com/cars-for-sale"

    async def search(self, params: dict) -> List[RawListing]:
        listings = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ])
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1280, 'height': 1000}
            )
            page = await context.new_page()
            # Mask automation
            await page.evaluate("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            make = params.get("makes", [""])[0].lower()
            model = params.get("models", [""])[0].lower().replace(" ", "-")
            year_min = params.get("year_min")
            
            # Carfax URL structure based on user feedback
            # https://www.carfax.com/cars-for-sale/ford/f-150/raptor
            if make == "ford" and "raptor" in model:
                url = f"{self.base_url}/ford/f-150/raptor"
            else:
                url = f"{self.base_url}/{make}/{model}"
            
            query_params = []
            if year_min:
                query_params.append(f"yearMin={year_min}")
            
            # Add a broad zip code if not provided to ensure we get results
            zip_code = params.get("location", {}).get("zip", "60601")
            query_params.append(f"zip={zip_code}")
            
            if query_params:
                url += "?" + "&".join(query_params)
            
            logger.info("searching_carfax", url=url)
            
            try:
                # Use a more resilient navigation strategy
                response = await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                
                if response and response.status == 403:
                    logger.error("carfax_blocked_403")
                    # Try one fallback URL structure
                    fallback_url = f"https://www.carfax.com/Used-{make.title()}-{model.title()}"
                    logger.info("trying_fallback_url", url=fallback_url)
                    await page.goto(fallback_url, wait_until="domcontentloaded", timeout=30000)

                # Wait for any listing-like element
                try:
                    await page.wait_for_selector("article, .srp-list-item, [class*='listing']", timeout=15000)
                except Exception:
                    logger.warn("carfax_no_listings_found_selector")
                    return []

                items = await page.query_selector_all("article, .srp-list-item, [class*='listing-container']")
                
                for item in items:
                    try:
                        # Extract title - usually contains year make model
                        title_el = await item.query_selector("h4, [class*='title']")
                        title = (await title_el.inner_text()).strip() if title_el else ""
                        if not title: continue

                        # Extract URL
                        link_el = await item.query_selector("a")
                        url_attr = await link_el.get_attribute("href") if link_el else ""
                        if url_attr and not url_attr.startswith("http"):
                            url_attr = "https://www.carfax.com" + url_attr
                        
                        # Extract Price
                        price_el = await item.query_selector("[class*='price'], .srp-list-item-price")
                        price_text = (await price_el.inner_text()).strip() if price_el else ""
                        price = self._parse_price(price_text)
                        
                        # Extract Mileage
                        mileage_el = await item.query_selector("[class*='mileage'], .srp-list-item-basic-info-mileage")
                        mileage_text = (await mileage_el.inner_text()).strip() if mileage_el else ""
                        mileage = self._parse_mileage(mileage_text)
                        
                        year_match = re.search(r'(\d{4})', title)
                        year = int(year_match.group(1)) if year_match else None
                        
                        ext_id = url_attr.split("/")[-1] if url_attr else title
                        
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
                    except Exception as e:
                        continue
                        
            except Exception as e:
                logger.error("carfax_search_failed", error=str(e))
            finally:
                await browser.close()
                
        return listings

    def _parse_price(self, price_str: str) -> Optional[float]:
        if not price_str: return None
        cleaned = re.sub(r'[^\d.]', '', price_str)
        try: return float(cleaned)
        except ValueError: return None

    def _parse_mileage(self, mileage_str: str) -> Optional[int]:
        if not mileage_str: return None
        cleaned = re.sub(r'[^\d]', '', mileage_str)
        try: return int(cleaned)
        except ValueError: return None
