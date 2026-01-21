import asyncio
import re
from typing import List, Optional
from playwright.async_api import async_playwright
from src.data.base_provider import BaseProvider, RawListing
import structlog

logger = structlog.get_logger()

class BringATrailerProvider(BaseProvider):
    def __init__(self):
        self.source_name = "bringatrailer"
        self.base_url = "https://bringatrailer.com/auctions/"

    async def search(self, params: dict) -> List[RawListing]:
        """
        Scrapes Bring A Trailer auctions. 
        Note: BaT is dynamic, so we use Playwright.
        """
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
            
            # BaT search is best handled by going to the auctions page and using their filter or just scraping all live auctions
            # For the MVP, we'll scrape the main auctions page which contains all live listings
            url = self.base_url
            
            logger.info("searching_bat", url=url)
            
            try:
                # Use 'load' instead of 'networkidle' as BaT has many background requests
                await page.goto(url, wait_until="load", timeout=60000)
                
                # Wait for any listing card to appear
                try:
                    await page.wait_for_selector(".listing-card", timeout=20000)
                except Exception:
                    logger.warn("listing_cards_not_found_trying_alternate")
                    # Sometimes BaT uses different layouts
                    await page.wait_for_selector("main", timeout=10000)

                # Scroll to trigger lazy loading
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                await asyncio.sleep(2)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)

                # Extract listing items
                items = await page.query_selector_all(".listing-card, [class*='listing-card']")
                
                for item in items:
                    try:
                        # Try multiple title selectors
                        title_el = await item.query_selector(".listing-card-title, .item-title, h3")
                        title = (await title_el.inner_text()).strip() if title_el else ""
                        
                        # BaT links: The listing card itself is often an 'a' or contains one
                        url_attr = ""
                        tag_name = await item.evaluate("el => el.tagName")
                        if tag_name.lower() == "a":
                            url_attr = await item.get_attribute("href")
                        else:
                            link_el = await item.query_selector("a")
                            if link_el:
                                url_attr = await link_el.get_attribute("href")
                            
                        if url_attr and not url_attr.startswith("http"):
                            url_attr = "https://bringatrailer.com" + url_attr
                        
                        # BaT titles usually look like "2022 Porsche 911 GT3"
                        year_match = re.search(r'(\d{4})', title)
                        year = int(year_match.group(1)) if year_match else None
                        
                        # Fallback: try to get year from URL if title fails
                        if not year and url_attr:
                            url_year_match = re.search(r'/(\d{4})-', url_attr)
                            if url_year_match:
                                year = int(url_year_match.group(1))
                        
                        # Price extraction - BaT often uses .listing-card-price or .price
                        # Also check for current bid. Use a more generic search for price-like text
                        price_text = ""
                        price_el = await item.query_selector(".listing-card-price, .price, .bid-price, .current-bid, .no-reserve")
                        if price_el:
                            price_text = (await price_el.inner_text()).strip()
                        else:
                            # Fallback: search all text in the card for a dollar sign
                            all_text = await item.inner_text()
                            price_match = re.search(r'\$[\d,]+', all_text)
                            if price_match:
                                price_text = price_match.group(0)
                                
                        price = self._parse_price(price_text)
                        
                        # External ID for BaT can be the URL slug
                        ext_id = url_attr.strip("/").split("/")[-1] if url_attr else title
                        
                        listings.append(RawListing(
                            external_id=ext_id,
                            source=self.source_name,
                            url=url_attr,
                            title=title,
                            year=year,
                            price=price,
                            raw_data={"full_title": title, "price_text": price_text}
                        ))
                    except Exception as e:
                        logger.error("error_parsing_bat_item", error=str(e))
                        continue
                        
            except Exception as e:
                logger.error("bat_search_failed", error=str(e))
            finally:
                await browser.close()
                
        return listings

    def _parse_price(self, price_str: str) -> Optional[float]:
        if not price_str:
            return None
        # Remove $, commas, and non-numeric chars except decimal
        cleaned = re.sub(r'[^\d.]', '', price_str)
        try:
            return float(cleaned)
        except ValueError:
            return None
