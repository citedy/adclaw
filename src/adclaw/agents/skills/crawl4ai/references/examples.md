# Crawl4ai Examples

## Common Scraping Scenarios

### 1. E-commerce Product Scraping

**Scenario:** Extract product information from an online store.

```python
from crawl4ai import AsyncWebCrawler

async def scrape_products(url):
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url=url,
            javascript=True,  # Product data often loaded via JS
            screenshot=True,
            js_code="""
                const products = document.querySelectorAll('.product-card');
                return Array.from(products).map(p => ({
                    name: p.querySelector('.product-name')?.textContent,
                    price: p.querySelector('.price')?.textContent,
                    url: p.querySelector('a')?.href,
                    image: p.querySelector('img')?.src,
                    rating: p.querySelector('.rating')?.textContent,
                    stock: p.querySelector('.stock')?.textContent
                })).filter(p => p.name);  // Remove items without names
            """
        )

        if result.success:
            products = result.extracted_content
            for product in products:
                print(f"{product['name']}: {product['price']}")
            return products
        return None
```

**User prompt examples:**
- "Extract product details from this e-commerce site"
- "Scrape this page for products with prices"
- "Get all products from this shop"

---

### 2. Article Content Extraction

**Scenario:** Extract article titles, authors, and content from blogs or news sites.

```python
from crawl4ai import AsyncWebCrawler

async def scrape_article(url):
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url=url,
            javascript=True,
            remove_tags=['script', 'style', 'nav', 'footer', 'comment'],
            only_main_content=True
        )

        if result.success:
            article = {
                'title': None,
                'author': None,
                'publish_date': None,
                'content': result.markdown
            }

            # Try to extract from specific selectors
            if result.extracted_content:
                for item in result.extracted_content:
                    if item.get('type') == 'article':
                        article['title'] = item.get('name', item.get('title'))
                        article['author'] = item.get('author')
                        article['publish_date'] = item.get('date')
                        article['content'] = item.get('text', result.markdown)

            return article
        return None
```

**User prompt examples:**
- "Extract article content from this page"
- "Get title, author, and content from this blog post"
- "Scrape this article for me"

---

### 3. Table Data Extraction

**Scenario:** Extract data from HTML tables.

```python
from crawl4ai import AsyncWebCrawler
import pandas as pd

async def scrape_table(url, table_selector='.data-table'):
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url=url,
            javascript=True
        )

        if result.success and result.extracted_content:
            for item in result.extracted_content:
                if item.get('type') == 'table' and item.get('selector') == table_selector:
                    # Create DataFrame from table data
                    df = pd.DataFrame({
                        col: item['rows'][i][idx]
                        for idx, col in enumerate(item['headers'])
                        for i in range(len(item['rows']))
                    })
                    return df
        return None
```

**User prompt examples:**
- "Extract this table into a CSV file"
- "Get the data from this table"
- "Parse this HTML table"

---

### 4. Pagination Scraping

**Scenario:** Scrape multiple pages of results.

```python
from crawl4ai import AsyncWebCrawler, BrowserMode

async def scrape_paginated(base_url, max_pages=10, delay=2):
    all_results = []
    seen_urls = set()

    async with AsyncWebCrawler() as crawler:
        for page in range(1, max_pages + 1):
            url = f"{base_url}?page={page}"

            # Skip if already scraped
            if url in seen_urls:
                continue
            seen_urls.add(url)

            print(f"Scraping page {page}: {url}")

            result = await crawler.arun(
                url=url,
                browser_mode=BrowserMode.LATEST,
                headless=True,
                javascript=True,
                delay=delay
            )

            if result.success:
                all_results.extend(result.extracted_content or [])
                print(f"  Found {len(result.extracted_content or [])} items")
            else:
                print(f"  Failed to scrape page {page}")
                break

            # Check if next page button is disabled (end of results)
            if not result.extracted_content:
                break

    return all_results
```

**User prompt examples:**
- "Scrape all pages from this search result"
- "Get all results from this pagination site"
- "Scrape this website for all items"

---

### 5. Dynamic Content Handling

**Scenario:** Websites that load data via AJAX or infinite scroll.

```python
from crawl4ai import AsyncWebCrawler

async def scrape_dynamic_site(url):
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url=url,
            javascript=True,
            wait_for=".content-container",  # Wait for main content
            delay=3,  # Give time for JS to execute
            js_code="""
                // Scroll to bottom to trigger lazy loading
                window.scrollTo(0, document.body.scrollHeight);
                return new Promise(resolve => {
                    setTimeout(() => resolve('scrolled'), 2000);
                });
            """
        )

        if result.success:
            return result.markdown
        return None
```

**User prompt examples:**
- "Scrape this site with dynamic content"
- "This page loads data with JavaScript"
- "Extract content from this infinite scroll page"

---

### 6. API Mock Scraping

**Scenario:** Extract structured data from JSON-LD marked content.

```python
from crawl4ai import AsyncWebCrawler

async def scrape_json_ld(url):
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url, verbose=False)

        if result.success and result.extracted_content:
            # Filter for JSON-LD structured data
            json_ld_data = [
                item for item in result.extracted_content
                if item.get('type') == 'json-ld'
            ]

            if json_ld_data:
                return json_ld_data

            # Or extract manually from page
            import re
            json_ld_pattern = r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>'
            matches = re.findall(json_ld_pattern, result.clean_html, re.DOTALL)

            results = []
            for match in matches:
                try:
                    import json
                    data = json.loads(match)
                    results.extend(data if isinstance(data, list) else [data])
                except:
                    continue

            return results

        return None
```

**User prompt examples:**
- "Extract structured data from this page"
- "Get JSON-LD data from this website"
- "Parse this structured data"

---

### 7. Custom HTML Parsing

**Scenario:** Use CSS selectors to extract specific elements.

```python
from crawl4ai import AsyncWebCrawler

async def custom_extraction(url, selectors):
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url, verbose=False)

        if not result.success:
            return None

        extracted = {}

        for name, selector in selectors.items():
            import bs4
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(result.clean_html, 'html.parser')
            elements = soup.select(selector)

            if elements:
                extracted[name] = [
                    {
                        'text': elem.get_text(strip=True),
                        'html': str(elem)[:500] + '...' if len(str(elem)) > 500 else str(elem)
                    }
                    for elem in elements
                ]
            else:
                extracted[name] = []

        return extracted
```

**Usage:**
```python
selectors = {
    'titles': 'h1, h2, h3',
    'paragraphs': 'p',
    'links': 'a[href]',
    'images': 'img[src]'
}

result = await custom_extraction(url, selectors)
```

**User prompt examples:**
- "Extract headings and paragraphs from this page"
- "Get all links from this site"
- "Parse this HTML for specific elements"

---

### 8. Error Handling and Retry Logic

**Scenario:** Robust scraping with retries and error handling.

```python
from crawl4ai import AsyncWebCrawler
import asyncio

async def robust_scrape(url, max_retries=3, delay=2):
    for attempt in range(max_retries):
        try:
            async with AsyncWebCrawler() as crawler:
                result = await crawler.arun(
                    url=url,
                    timeout=30000,  # 30 seconds
                    headless=True
                )

                if result.success:
                    return result

                print(f"Attempt {attempt + 1} failed: {result.error_message}")

        except Exception as e:
            print(f"Attempt {attempt + 1} error: {str(e)}")

        if attempt < max_retries - 1:
            await asyncio.sleep(delay * (attempt + 1))  # Exponential backoff

    return None
```

---

## Output Formats

### Markdown Output
```python
result.markdown  # Clean, readable text
```

### HTML Output
```python
result.clean_html  # Structured HTML with tags removed
```

### Structured Data
```python
result.extracted_content  # List of structured data items
```

### Links
```python
result.links  # All links found on page
```

### Screenshot
```python
result.screenshot  # Binary image data
```
