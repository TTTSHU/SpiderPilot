import scrapy
import json
import re

class EmpikTestSpider(scrapy.Spider):
    name = "empik_test"
    start_urls = [
        "https://www.empik.com/ps5-ds-midnight-black-cfi-zct2w-eas-sony-interactive-enterteinment,p1688380969,multimedia-p"
    ]
    custom_settings = {
        "DOWNLOAD_DELAY": 1.0,
        "CONCURRENT_REQUESTS": 2,
        "FEED_EXPORT_ENCODING": "utf-8",
    }

    def parse(self, response):
        item = {}
        # Extract price from JSON embedded in HTML
        price = self.extract_price(response)
        item["price"] = price if price else None

        # Extract title (fallback HTML selectors since JSON path unresolved)
        title = self.extract_title(response)
        item["title"] = title if title else ""

        yield item

    def extract_price(self, response):
        """Try to find JSON with offer data and extract originalPrice."""
        try:
            # Search for JSON in script tags (common in modern JS frameworks)
            for script in response.css("script::text").getall():
                # Skip empty or non-JSON scripts
                if not script or script.strip()[:1] not in ("{", "["):
                    continue
                try:
                    data = json.loads(script)
                except (json.JSONDecodeError, ValueError):
                    continue
                # Navigate the JSONPath manually: $.data.getProduct.bestOffer.originalPrice
                if isinstance(data, dict):
                    price = self.get_json_path(data, "data.getProduct.bestOffer.originalPrice")
                    if price is not None:
                        self.logger.info(f"Found price from JSON: {price}")
                        return str(price)
            # Fallback: try to find JSON-LD script (e.g., application/ld+json)
            ld_scripts = response.xpath('//script[@type="application/ld+json"]/text()').getall()
            for script in ld_scripts:
                try:
                    data = json.loads(script)
                except (json.JSONDecodeError, ValueError):
                    continue
                # Some JSON-LD might contain offers with price
                offers = self.get_json_path(data, "offers.price")
                if offers is not None:
                    return str(offers)
        except Exception as e:
            self.logger.error(f"Error extracting price: {e}")
        self.logger.warning("Price not found in any embedded JSON")
        return None

    def extract_title(self, response):
        """Extract title from HTML meta tags or headings."""
        try:
            # Try Open Graph meta tag
            title = response.css('meta[property="og:title"]::attr(content)').get()
            if title:
                return title.strip()
            # Try standard title tag
            title = response.css("title::text").get()
            if title:
                return title.strip()
            # Try H1 heading
            title = response.css("h1::text").get()
            if title:
                return title.strip()
            # Additional fallback: product name from class
            title = response.css('[class*="product-name"]::text').get()
            if title:
                return title.strip()
        except Exception as e:
            self.logger.error(f"Error extracting title: {e}")
        self.logger.warning("Title not found via HTML selectors")
        return ""

    def get_json_path(self, data, path):
        """Navigate a JSON structure using dot-separated keys (e.g., 'data.getProduct.bestOffer.originalPrice').
        Supports integer indices in brackets (e.g., 'items[0].name'). Returns None if not found."""
        if not path:
            return data
        # Remove leading "$." if present
        if path.startswith("$."):
            path = path[2:]
        keys = re.split(r'\.|(?=\[)', path)  # Split by dot or before bracket
        current = data
        for key in keys:
            if not key:
                continue
            # Handle array index: key like "[0]" or "items[0]"
            if "[" in key and key.endswith("]"):
                # Extract key name and index
                base_key = key.split("[")[0]
                index_str = key.split("[")[1].rstrip("]")
                if index_str.isdigit():
                    idx = int(index_str)
                else:
                    return None
                # Navigate to base_key if exists
                if base_key:
                    if isinstance(current, dict) and base_key in current:
                        current = current[base_key]
                    else:
                        return None
                # Now current should be a list
                if isinstance(current, list) and 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return None
            else:
                # Regular dict key
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return None
        return current