# Crawl4ai Error Handling and Troubleshooting

## Common Errors and Solutions

### 1. "To get started with GitHub CLI, please run: gh auth login"

**Cause:** Not authenticated with GitHub CLI

**Solution:**
```bash
gh auth login
```

---

### 2. "Connection refused" or "DNS lookup failed"

**Cause:** Network connectivity issue or firewall blocking

**Solutions:**
- Check internet connectivity
- Try a VPN if accessing geo-restricted content
- Check if firewall is blocking the connection
- Try a different network

---

### 3. "Page not found" (404)

**Cause:** Invalid URL or page has been moved/deleted

**Solutions:**
- Verify the URL is correct
- Check if the page exists at a different URL
- Try the homepage first
- Look for redirects in the browser

---

### 4. "Access denied" or "403 Forbidden"

**Cause:** Site blocked scraping or requires authentication

**Solutions:**
- Check if the site has robots.txt: `https://site.com/robots.txt`
- Try with a different user-agent
- The site may require login or cookies
- Consider if scraping violates the site's terms of service

---

### 5. "JavaScript not executing" or "Dynamic content not loading"

**Cause:** JavaScript not enabled or not waiting long enough

**Solutions:**
```python
# Enable JavaScript
result = await crawler.arun(
    url=url,
    javascript=True,
    wait_for="body",  # Wait for body to load
    delay=2.0  # Add delay after load
)
```

---

### 6. "Timeout expired"

**Cause:** Request taking too long or site too slow

**Solutions:**
```python
# Increase timeout
result = await crawler.arun(
    url=url,
    timeout=60000  # 60 seconds
)

# Or implement retry logic
async def with_retry(func, max_retries=3):
    for i in range(max_retries):
        try:
            return await func()
        except TimeoutError:
            if i == max_retries - 1:
                raise
            await asyncio.sleep(2 ** i)  # Exponential backoff
```

---

### 7. "Empty result" or "No data extracted"

**Cause:** Selectors incorrect or data not in expected format

**Solutions:**
1. Inspect the page with browser DevTools to find correct selectors
2. Check if JavaScript is needed to load the data
3. Verify the selectors in your code match the HTML structure
4. Use verbose mode to see what's being processed

```python
# Enable verbose mode to see what's happening
result = await crawler.arun(
    url=url,
    verbose=True
)
```

---

### 8. "Memory error" or "Out of memory"

**Cause:** Processing large pages or too many requests

**Solutions:**
- Reduce the amount of content to process
- Process pages in batches with delays
- Use streaming if available
- Close the crawler when done
- Increase system memory

---

### 9. "Rate limit exceeded" (HTTP 429)

**Cause:** Too many requests to the same server

**Solutions:**
```python
# Add delays between requests
for url in urls:
    result = await crawler.arun(url=url)
    await asyncio.sleep(2)  # Wait 2 seconds before next request

# Or use a rate limiter
from asyncio import Semaphore

async def rate_limited_scrape(url, semaphore):
    async with semaphore:
        return await scrape_url(url)

semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests

# ... then use rate_limited_scrape for each URL
```

---

## Debugging Tips

### Enable Verbose Mode

```python
result = await crawler.arun(
    url=url,
    verbose=True  # Shows detailed progress
)
```

### Check Result Status

```python
async with AsyncWebCrawler() as crawler:
    result = await crawler.arun(url=url)

    if not result.success:
        print(f"Error: {result.error_message}")
        print(f"Status code: {result.status_code}")
        return None
```

### Inspect Page Source

```python
result = await crawler.arun(url=url)

# Save HTML to file for inspection
with open('debug.html', 'w') as f:
    f.write(result.clean_html)

# Use browser DevTools to inspect the saved file
```

### Test Selectors in Browser

```python
# Use browser DevTools (F12) to test CSS selectors
# Check if selectors match the HTML structure
```

### Log Request Details

```python
result = await crawler.arun(
    url=url,
    verbose=True
)

# Check if the final URL is correct
print(f"Final URL: {result.url}")
print(f"Status code: {result.status_code}")
```

---

## Common Issues by Category

### Network Issues

| Issue | Solution |
|-------|----------|
| Connection refused | Check network, try VPN |
| DNS lookup failed | Check DNS settings |
| Slow loading | Increase timeout, add delays |
| SSL errors | Verify URL is https |

### Site-Specific Issues

| Issue | Solution |
|-------|----------|
| Cloudflare protection | Use different browser, add delays |
| Cloudflare bot detection | Use residential proxy, vary user-agent |
| Cloudflare 521/520 | Site is down or under attack |
| CAPTCHA | Site requires human interaction |

### Data Extraction Issues

| Issue | Solution |
|-------|----------|
| No data extracted | Check selectors, enable JavaScript |
| Wrong data | Verify selectors, inspect HTML |
| Incomplete data | Check if lazy loading, wait longer |
| Duplicate data | Check for pagination, avoid re-scraping |

---

## Retry Strategies

### Simple Retry

```python
async def scrape_with_retry(url, max_retries=3):
    for i in range(max_retries):
        result = await crawler.arun(url=url)

        if result.success:
            return result

        print(f"Attempt {i+1} failed: {result.error_message}")
        await asyncio.sleep(2 ** i)  # Exponential backoff

    return None
```

### Exponential Backoff

```python
async def scrape_with_backoff(url):
    import time
    backoff = 1  # Start with 1 second

    while True:
        try:
            result = await crawler.arun(url=url)
            return result
        except Exception as e:
            print(f"Error: {e}. Retrying in {backoff}s...")
            await asyncio.sleep(backoff)
            backoff *= 2  # Double the delay each time
            if backoff > 60:  # Max 60 second delay
                backoff = 60
```

---

## Rate Limiting

### Request Throttling

```python
import asyncio
from collections import deque
from datetime import datetime

class RateLimiter:
    def __init__(self, max_requests, time_window):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()

    async def wait_if_needed(self):
        now = datetime.now()
        # Remove requests outside the time window
        while self.requests and (now - self.requests[0]).total_seconds() > self.time_window:
            self.requests.popleft()

        # If at limit, wait until oldest request expires
        while len(self.requests) >= self.max_requests:
            await asyncio.sleep(1)
            await self.wait_if_needed()

        self.requests.append(now)

# Usage
limiter = RateLimiter(max_requests=10, time_window=60)  # 10 requests per minute

async def rate_limited_scrape(url):
    await limiter.wait_if_needed()
    return await crawler.arun(url=url)
```

---

## Performance Optimization

### Reduce Memory Usage

```python
# Process in smaller batches
async def batch_process(urls, batch_size=10):
    for i in range(0, len(urls), batch_size):
        batch = urls[i:i + batch_size]
        results = await asyncio.gather(*[scrape_url(url) for url in batch])
        yield results
```

### Cache Results

```python
import hashlib
import json
from pathlib import Path

def get_cache_key(url):
    return hashlib.md5(url.encode()).hexdigest()

def is_cached(url):
    cache_file = Path('cache') / f"{get_cache_key(url)}.json"
    return cache_file.exists()

def get_cached_result(url):
    cache_file = Path('cache') / f"{get_cache_key(url)}.json"
    with open(cache_file) as f:
        return json.load(f)

def save_result(url, result):
    cache_file = Path('cache') / f"{get_cache_key(url)}.json"
    Path(cache_file).parent.mkdir(exist_ok=True)
    with open(cache_file, 'w') as f:
        json.dump(result, f)
```

---

## Emergency Troubleshooting

If all else fails:

1. **Save the page source**: Save HTML to file for inspection
2. **Test with browser**: Try accessing the URL in a browser first
3. **Check site status**: Look for site-wide issues or outages
4. **Review logs**: Check verbose output for details
5. **Consider alternatives**: Try different scraping tools or services
