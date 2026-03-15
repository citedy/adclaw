# Crawl4ai API Reference

## Core Classes

### AsyncWebCrawler

The main crawler class for web scraping operations.

```python
from crawl4ai import AsyncWebCrawler, BrowserMode

async with AsyncWebCrawler() as crawler:
    result = await crawler.arun(
        url=url,
        **kwargs
    )
```

#### Parameters

- **url (str)**: Target URL to scrape
- **browser_mode (BrowserMode)**: Browser mode setting
  - `BrowserMode.LATEST`: Use latest browser
  - `BrowserMode.SLAVERY`: Use scraping ant technology
  - `BrowserMode.BEST`: Auto-select best mode
  - `BrowserMode.FIREFOX`: Use Firefox browser
  - `BrowserMode.CHROME`: Use Chrome browser
- **headless (bool)**: Run in headless mode (default: True)
- **javascript (bool)**: Execute JavaScript (default: False)
- **verbose (bool)**: Print verbose output (default: False)
- **screenshot (bool)**: Capture screenshot (default: False)
- **delay (float)**: Delay after page load in seconds
- **wait_for (str)**: Wait for specific element/selector
- **timeout (int)**: Request timeout in milliseconds
- **bypass_cache (bool)**: Bypass browser cache (default: False)
- **js_code (str)**: Custom JavaScript code to execute
- **js_only (bool)**: Only execute JS, don't download resources (default: False)

#### Result Object

```python
result = {
    'success': bool,           # Whether scraping succeeded
    'status_code': int,        # HTTP status code
    'url': str,                # Final URL after redirects
    'markdown': str,           # Clean markdown text
    'clean_html': str,         # Structured HTML
    'extracted_content': list, # Structured data items
    'links': list,             # All links found
    'error_message': str,      # Error message if failed
    'screenshot': bytes        # Screenshot data if enabled
}
```

## Extracted Content Structure

The `extracted_content` field contains structured data extracted from the page.

### Item Types

```python
extracted_content = [
    {
        'type': 'product',  # Type of content
        'name': 'Product Name',
        'price': '$29.99',
        'url': '/products/item',
        # Additional type-specific fields
        'description': 'Product description...',
        'image': 'image_url',
        # ...
    },
    {
        'type': 'article',
        'title': 'Article Title',
        'author': 'Author Name',
        'publish_date': '2024-01-01',
        # ...
    },
    {
        'type': 'table',
        'headers': ['Name', 'Price', 'Stock'],
        'rows': [
            ['Item 1', '$10', '100'],
            ['Item 2', '$20', '50']
        ]
    }
]
```

## Common Browser Settings

### Headless Browser

```python
async with AsyncWebCrawler() as crawler:
    result = await crawler.arun(
        url=url,
        browser_mode=BrowserMode.LATEST,
        headless=True
    )
```

### JavaScript Execution

```python
async with AsyncWebCrawler() as crawler:
    result = await crawler.arun(
        url=url,
        javascript=True,
        wait_for="body",      # Wait for body element
        delay=1.5             # 1.5 second delay after load
    )
```

### Custom JavaScript

```python
async with AsyncWebCrawler() as crawler:
    result = await crawler.arun(
        url=url,
        js_code="""
            const products = document.querySelectorAll('.product');
            return Array.from(products).map(p => ({
                name: p.querySelector('.name')?.textContent,
                price: p.querySelector('.price')?.textContent,
                url: p.querySelector('a')?.href
            }));
        """,
        js_only=True
    )
    # result.extracted_content will contain the products
```

### Error Handling

```python
async with AsyncWebCrawler() as crawler:
    result = await crawler.arun(url=url, timeout=30000)

    if result.success:
        print(f"Scraped: {result.markdown}")
    else:
        print(f"Error: {result.error_message}")
```

## Advanced Features

### Session Management

```python
from crawl4ai import AsyncWebCrawler

async def multi_page_scrape(base_url):
    async with AsyncWebCrawler() as crawler:
        results = []
        for page in range(1, 11):
            url = f"{base_url}?page={page}"
            result = await crawler.arun(
                url=url,
                session_id=f"session_{page}",
                bypass_cache=True
            )
            results.append(result)
        return results
```

### Custom User Agent

```python
async with AsyncWebCrawler() as crawler:
    result = await crawler.arun(
        url=url,
        user_agent="Mozilla/5.0 (Custom User Agent)"
    )
```

### Blocking Specific Elements

```python
async with AsyncWebCrawler() as crawler:
    result = await crawler.arun(
        url=url,
        remove_tags=['script', 'style', 'nav', 'footer'],
        only_main_content=True
    )
```

## Integration with Other Libraries

### BeautifulSoup for Parsing

```python
from bs4 import BeautifulSoup

html = result.clean_html
soup = BeautifulSoup(html, 'html.parser')

# Find all links
links = [a.get('href') for a in soup.find_all('a', href=True)]

# Extract data by CSS selector
products = soup.select('.product')
for product in products:
    name = product.select_one('.name').text
    price = product.select_one('.price').text
```

### Pandas for Data Analysis

```python
import pandas as pd

# Convert extracted content to DataFrame
df = pd.DataFrame(result.extracted_content)
df.to_csv('scraped_data.csv', index=False)
```

## Performance Tips

1. **Use headless mode** by default to save resources
2. **Set appropriate delays** between requests to avoid overwhelming servers
3. **Use caching** when appropriate to avoid repeated requests
4. **Filter extracted content** to only what you need
5. **Implement retry logic** for failed requests
6. **Use session management** for maintaining state across requests
7. **Set timeouts** to prevent hanging on slow servers

## Error Codes

- `200-299`: Successful requests
- `300-399`: Redirects
- `400-499`: Client errors (invalid URL, blocked by site)
- `500-599`: Server errors (unavailable, down)
