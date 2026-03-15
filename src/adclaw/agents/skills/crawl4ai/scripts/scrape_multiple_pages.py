#!/usr/bin/env python3
"""
Multi-page scraper using crawl4ai with pagination support

Usage:
    python scrape_multiple_pages.py <base_url> <output_dir> [--pages <num_pages>] [--delay <seconds>]
"""

import asyncio
import argparse
import json
import os
from urllib.parse import urljoin, urlparse
from crawl4ai import AsyncWebCrawler, BrowserMode

def get_page_number(url):
    """Extract page number from URL if present."""
    parsed = urlparse(url)
    path_parts = parsed.path.split('/')
    for part in path_parts:
        if part.isdigit():
            return int(part)
    return None

def generate_page_urls(base_url, start_page=1, end_page=1, format='{page}'):
    """Generate URLs for multiple pages."""
    urls = []
    for page in range(start_page, end_page + 1):
        page_url = base_url.replace('{page}', str(page)).replace('[page]', str(page))
        urls.append(page_url)
    return urls

async def scrape_pages(urls, output_dir, delay=2):
    """Scrape multiple pages with delay between requests."""
    os.makedirs(output_dir, exist_ok=True)

    results = []
    success_count = 0
    fail_count = 0

    print(f"Starting to scrape {len(urls)} pages...")
    print(f"Output directory: {output_dir}")
    print(f"Delay between requests: {delay}s\n")

    async with AsyncWebCrawler() as crawler:
        for i, url in enumerate(urls, 1):
            try:
                print(f"[{i}/{len(urls)}] Scraping: {url}")

                result = await crawler.arun(
                    url=url,
                    browser_mode=BrowserMode.LATEST,
                    headless=True,
                    javascript=True,
                    bypass_cache=True
                )

                if result.success:
                    success_count += 1
                    print(f"  ✓ Success: {len(result.markdown)} chars extracted")

                    # Save individual result
                    page_num = get_page_number(url) or i
                    page_data = {
                        'url': url,
                        'page_number': page_num,
                        'success': True,
                        'markdown': result.markdown,
                        'extracted_content': result.extracted_content or [],
                        'status_code': result.status_code
                    }

                    # Save to JSON file
                    output_file = os.path.join(output_dir, f'page_{page_num}.json')
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(page_data, f, indent=2, ensure_ascii=False)

                    # Also save markdown
                    md_file = os.path.join(output_dir, f'page_{page_num}.md')
                    with open(md_file, 'w', encoding='utf-8') as f:
                        f.write(result.markdown)

                    print(f"  ✓ Saved to: {output_file}")

                else:
                    fail_count += 1
                    print(f"  ✗ Failed: {result.error_message}")

                    page_num = get_page_number(url) or i
                    page_data = {
                        'url': url,
                        'page_number': page_num,
                        'success': False,
                        'error': result.error_message
                    }

                    output_file = os.path.join(output_dir, f'page_{page_num}.json')
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(page_data, f, indent=2, ensure_ascii=False)

                # Delay between requests
                if i < len(urls):
                    await asyncio.sleep(delay)

            except Exception as e:
                fail_count += 1
                print(f"  ✗ Error: {str(e)}")

                page_num = get_page_number(url) or i
                page_data = {
                    'url': url,
                    'page_number': page_num,
                    'success': False,
                    'error': str(e)
                }

                output_file = os.path.join(output_dir, f'page_{page_num}.json')
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(page_data, f, indent=2, ensure_ascii=False)

                if i < len(urls):
                    await asyncio.sleep(delay)

    # Save summary
    summary = {
        'total_pages': len(urls),
        'success_count': success_count,
        'fail_count': fail_count,
        'results_dir': output_dir
    }

    summary_file = os.path.join(output_dir, 'summary.json')
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Scraping complete!")
    print(f"  Total pages: {len(urls)}")
    print(f"  Success: {success_count}")
    print(f"  Failed: {fail_count}")
    print(f"  Summary: {summary_file}")
    print(f"{'='*60}")

    return results

async def main():
    parser = argparse.ArgumentParser(
        description='Scrape multiple pages using crawl4ai',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape pages with pagination
  python scrape_multiple_pages.py https://example.com/page-{page}.json output/

  # Scrape pages with brackets
  python scrape_multiple_pages.py https://example.com/page[page].html output/

  # Scrape first 5 pages
  python scrape_multiple_pages.py https://example.com/page-{page}.json output/ --pages 5

  # Custom delay
  python scrape_multiple_pages.py https://example.com/page-{page}.json output/ --delay 5
        """
    )
    parser.add_argument('base_url', help='Base URL with {page} or [page] placeholder')
    parser.add_argument('output_dir', help='Output directory for scraped data')
    parser.add_argument('--pages', type=int, default=1, help='Number of pages to scrape (default: 1)')
    parser.add_argument('--delay', type=float, default=2, help='Delay between requests in seconds (default: 2)')

    args = parser.parse_args()

    # Generate URLs
    urls = generate_page_urls(args.base_url, 1, args.pages)

    # Scrape pages
    results = await scrape_pages(urls, args.output_dir, args.delay)

if __name__ == "__main__":
    asyncio.run(main())
