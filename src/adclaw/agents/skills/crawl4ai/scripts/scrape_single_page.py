#!/usr/bin/env python3
"""
Single page scraper using crawl4ai

Usage:
    python scrape_single_page.py <url> [--output <output_file>] [--format <format>]

Formats:
    - markdown: Extract clean markdown text
    - html: Extract cleaned HTML
    - json: Extract structured JSON data
    - all: Extract all formats
"""

import asyncio
import argparse
import json
import sys
from crawl4ai import AsyncWebCrawler, BrowserMode

async def scrape_page(url, output_format="all", output_file=None):
    """Scrape a single web page and return results."""
    print(f"Scraping: {url}")

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url=url,
            browser_mode=BrowserMode.LATEST,
            headless=True,
            javascript=True,
            verbose=True
        )

        if not result.success:
            print(f"Error scraping {url}: {result.error_message}")
            return None

        print(f"✓ Successfully scraped: {url}")
        print(f"  - Markdown length: {len(result.markdown)} chars")
        print(f"  - Extracted content items: {len(result.extracted_content) if result.extracted_content else 0}")

        # Prepare results
        results = {
            'url': url,
            'success': True,
            'markdown': result.markdown,
            'clean_html': result.clean_html,
            'extracted_content': result.extracted_content or [],
            'status_code': result.status_code,
            'error': result.error_message
        }

        # Output based on format
        if output_format == "all":
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)
                print(f"✓ Results saved to: {output_file}")
        elif output_format == "markdown":
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(result.markdown)
                print(f"✓ Markdown saved to: {output_file}")
            else:
                print(result.markdown)
        elif output_format == "html":
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(result.clean_html)
                print(f"✓ HTML saved to: {output_file}")
            else:
                print(result.clean_html)
        elif output_format == "json":
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)
                print(f"✓ JSON results saved to: {output_file}")
            else:
                print(json.dumps(results, indent=2, ensure_ascii=False))

        return results

async def main():
    parser = argparse.ArgumentParser(description='Scrape a single page using crawl4ai')
    parser.add_argument('url', help='URL to scrape')
    parser.add_argument('--output', '-o', help='Output file (default: print to stdout)')
    parser.add_argument('--format', '-f', choices=['markdown', 'html', 'json', 'all'], default='all',
                        help='Output format (default: all)')

    args = parser.parse_args()

    result = await scrape_page(args.url, args.format, args.output)

    if result and not result['success']:
        sys.exit(1)

    sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
