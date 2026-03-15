#!/usr/bin/env python3
"""
HTML data extractor using crawl4ai

Extract structured data from HTML using CSS selectors or JSON-LD.

Usage:
    python extract_from_html.py <input_file> <output_file> [--selector <css_selector>]
                              [--json-ld] [--links] [--images]
"""

import asyncio
import argparse
import json
import re
from pathlib import Path

async def extract_from_html(input_file, output_file, css_selector=None, extract_json_ld=True,
                            extract_links=True, extract_images=True):
    """Extract structured data from HTML file."""

    # Read HTML file
    with open(input_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    from crawl4ai import AsyncWebCrawler

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url=f"file://{input_file}",
            browser_mode=BrowserMode.LATEST,
            headless=True,
            verbose=False
        )

        if not result.success:
            print(f"Error processing HTML: {result.error_message}")
            return None

        extracted_data = {
            'metadata': {
                'input_file': str(input_file),
                'url': f"file://{input_file}",
                'extraction_timestamp': None  # Will set in main
            },
            'extracted_content': result.extracted_content or []
        }

        # Extract by CSS selector if provided
        if css_selector:
            try:
                import bs4
                soup = bs4.BeautifulSoup(html_content, 'html.parser')
                elements = soup.select(css_selector)

                # Extract text from elements
                text_data = []
                for elem in elements:
                    text_data.append(elem.get_text(strip=True))

                extracted_data['css_selector_extraction'] = {
                    'selector': css_selector,
                    'count': len(elements),
                    'results': text_data
                }
            except ImportError:
                print("Warning: beautifulsoup4 not installed. CSS selector extraction requires bs4.")
            except Exception as e:
                print(f"Warning: CSS selector extraction failed: {str(e)}")

        # Extract JSON-LD structured data
        if extract_json_ld:
            json_ld_pattern = r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>'
            json_ld_matches = re.findall(json_ld_pattern, html_content, re.DOTALL)

            if json_ld_matches:
                json_ld_data = []
                for match in json_ld_matches:
                    try:
                        data = json.loads(match)
                        if isinstance(data, list):
                            json_ld_data.extend(data)
                        else:
                            json_ld_data.append(data)
                    except json.JSONDecodeError:
                        continue

                extracted_data['json_ld'] = json_ld_data

        # Extract all links
        if extract_links:
            links = result.links if hasattr(result, 'links') and result.links else []
            extracted_data['links'] = links

        # Extract images
        if extract_images:
            import bs4
            soup = bs4.BeautifulSoup(html_content, 'html.parser')
            images = [img.get('src') for img in soup.find_all('img') if img.get('src')]
            extracted_data['images'] = images

        # Set metadata
        extracted_data['metadata']['extraction_timestamp'] = None  # In real use, this would be a datetime

        # Save results
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(extracted_data, f, indent=2, ensure_ascii=False)

        print(f"✓ Extraction complete!")
        print(f"  - Input file: {input_file}")
        print(f"  - Output file: {output_file}")
        print(f"  - Extracted content items: {len(extracted_data['extracted_content'])}")
        print(f"  - CSS selector matches: {extracted_data.get('css_selector_extraction', {}).get('count', 0)}")

        return extracted_data

def main():
    parser = argparse.ArgumentParser(
        description='Extract structured data from HTML using crawl4ai',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract all structured data
  python extract_from_html.py input.html output.json

  # Extract specific elements by CSS selector
  python extract_from_html.py input.html output.json --selector '.product'

  # Extract JSON-LD only
  python extract_from_html.py input.html output.json --json-ld

  # Extract links and images
  python extract_from_html.py input.html output.json --links --images
        """
    )
    parser.add_argument('input_file', help='Input HTML file')
    parser.add_argument('output_file', help='Output JSON file')
    parser.add_argument('--selector', help='CSS selector to extract elements')
    parser.add_argument('--no-json-ld', action='store_true', help='Skip JSON-LD extraction')
    parser.add_argument('--no-links', action='store_true', help='Skip link extraction')
    parser.add_argument('--no-images', action='store_true', help='Skip image extraction')

    args = parser.parse_args()

    # Run extraction
    result = asyncio.run(extract_from_html(
        args.input_file,
        args.output_file,
        args.selector,
        not args.no_json_ld,
        not args.no_links,
        not args.no_images
    ))

    if result is None:
        return 1

    return 0

if __name__ == "__main__":
    exit(main())
