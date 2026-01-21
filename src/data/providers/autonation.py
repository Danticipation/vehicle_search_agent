import asyncio
import re
from typing import List, Optional
from playwright.async_api import async_playwright
from src.data.base_provider import BaseProvider, RawListing
import structlog

logger = structlog.get_logger()

class AutoNationProvider(BaseProvider):
    def __init__(self):
        self.source_name = "autonation"
        self.base_url = "https://www.autonation.com/cars-for-sale"

    async def search(self, params: dict) -> List[RawListing]:
        listings = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ])
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            # Mask automation
            await page.evaluate("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            make = params.get("makes", [""])[0].lower()
            model = params.get("models", [""])[0].lower().replace(" ", "-")
            
            # AutoNation handling for Raptor
            if make == "ford" and "raptor" in model:
                url = f"{self.base_url}?make=Ford&model=F-150&trim=Raptor"
            else:
                url = f"{self.base_url}?make={make}&model={model}"
            
            logger.info("searching_autonation", url=url)
            
            try:
                # Use domcontentloaded instead of networkidle to avoid timeouts from background trackers
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                
                # Wait for results
                try:
                    await page.wait_for_selector(".vehicle-card, [class*='vehicle-card'], .inventory-item", timeout=30000)
                except Exception:
                    logger.warn("no_results_found_on_autonation")
                    return []

                items = await page.query_selector_all(".vehicle-card, [class*='vehicle-card'], .inventory-item")
                
                for item in items:
                    try:
                        title_el = await item.query_selector(".vehicle-title, [class*='title'], h3")
                        title = (await title_el.inner_text()).strip() if title_el else ""
                        
                        link_el = await item.query_selector("a")
                        url_attr = await link_el.get_attribute("href") if link_el else ""
                        if url_attr and not url_attr.startswith("http"):
                            url_attr = "https://www.autonation.com" + url_attr
                        
                        price_el = await item.query_selector(".price, [class*='price']")
                        price_text = (await price_el.inner_text()).strip() if price_el else ""
                        price = self._parse_price(price_text)
                        
                        mileage_el = await item.query_selector(".mileage, [class*='mileage']")
                        mileage_text = (await mileage_el.inner_text()).strip() if mileage_el else ""
                        mileage = self._parse_mileage(mileage_text)
                        
                        year_match = re.search(r'(\d{4})', title)
                        year = int(year_match.group(1)) if year_match else None
                        
                        ext_id = url_attr.split("/")[-1] if url_attr else title
                        
                        if title:
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
                        logger.error("error_parsing_autonation_item", error=str(e))
                        continue
                        
            except Exception as e:
                logger.error("autonation_search_failed", error=str(e))
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass
                
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
