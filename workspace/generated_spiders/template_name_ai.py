import scrapy
import re

class EmpikProductSpider(scrapy.Spider):
    name = "empik_product"
    allowed_domains = ["empik.com"]
    start_urls = [
        "https://www.empik.com/ps5-ds-midnight-black-cfi-zct2w-eas-sony-interactive-enterteinment,p1688380969,multimedia-p"
    ]
    custom_settings = {
        "DOWNLOAD_DELAY": 2.0,
        "CONCURRENT_REQUESTS": 1,
        "ROBOTSTXT_OBEY": False,
        "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    def parse(self, response):
        item = {}

        # Check for maintenance page or no product data
        if "maintenance" in response.text.lower() or "serwis techniczny" in response.text.lower():
            self.logger.warning("Maintenance page detected - no product data available")
            item["title"] = None
            item["price"] = None
            yield item
            return

        # Attempt to extract title using various common selectors
        title = None
        title_selectors = [
            'h1[data-product-name]::text',
            'h1.product-title::text',
            'h1 span::text',
            'meta[property="og:title"]::attr(content)',
            'title::text'
        ]
        for sel in title_selectors:
            title = response.css(sel).get()
            if title:
                title = title.strip()
                break

        # Fallback: try to extract from JSON-LD
        if not title:
            script = response.css('script[type="application/ld+json"]::text').get()
            if script:
                try:
                    import json
                    data = json.loads(script)
                    if isinstance(data, dict):
                        title = data.get("name")
                    elif isinstance(data, list):
                        title = data[0].get("name")
                except Exception:
                    pass

        # Extract price
        price = None
        price_selectors = [
            '.price-value::text',
            '.product-price span::text',
            '.cena span::text',
            'meta[property="product:price:amount"]::attr(content)',
            'span[data-price]::attr(data-price)'
        ]
        for sel in price_selectors:
            price_raw = response.css(sel).get()
            if price_raw:
                # Clean price string
                price_clean = re.sub(r'[^\d.,]', '', price_raw.replace(',', '.'))
                try:
                    price = float(price_clean)
                    break
                except ValueError:
                    continue

        # Fallback: try to extract from JSON-LD
        if not price:
            script = response.css('script[type="application/ld+json"]::text').get()
            if script:
                try:
                    import json
                    data = json.loads(script)
                    if isinstance(data, dict):
                        offers = data.get("offers")
                        if isinstance(offers, dict):
                            price = offers.get("price")
                        elif isinstance(offers, list):
                            price = offers[0].get("price")
                    elif isinstance(data, list):
                        offers = data[0].get("offers")
                        if isinstance(offers, dict):
                            price = offers.get("price")
                        elif isinstance(offers, list):
                            price = offers[0].get("price")
                except Exception:
                    pass

        # Final fallback: if no price found, log warning
        if not price:
            self.logger.warning("Could not extract price for %s", response.url)

        item["title"] = title
        item["price"] = price

        yield item