#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Browser E2E for AdClaw AI model selection and chat routing.

Prerequisites:
  - AdClaw app is running and reachable via --base-url.
  - The app has an adclaw-host-ai provider with a test key/base URL.
  - playwright is installed; run `python -m playwright install chromium` once.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from pathlib import Path

from playwright.async_api import Page, async_playwright

DEFAULT_BASE_URL = "http://127.0.0.1:8088"
DEFAULT_OUT = Path("artifacts/host-ai-model-selection-e2e")
LLAMA = "@cf/meta/llama-3.1-8b-instruct-fp8-fast"
QWEN = "@cf/qwen/qwen3-30b-a3b-fp8"
GEMMA = "@cf/google/gemma-4-26b-a4b-it"

FIND_TEXT_ELEMENT = """
(text) => {
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
  let node;
  while ((node = walker.nextNode())) {
    const ownText = Array.from(node.childNodes)
      .filter((child) => child.nodeType === Node.TEXT_NODE)
      .map((child) => child.textContent || "")
      .join("");
    if (ownText.includes(text)) {
      const rect = node.getBoundingClientRect();
      return {
        text: node.innerText,
        x: rect.x,
        y: rect.y,
        width: rect.width,
        height: rect.height,
      };
    }
  }
  return null;
}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify AdClaw AI model selection and chat routing.",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--initial-model", default=LLAMA)
    parser.add_argument("--switch-model", default=QWEN)
    parser.add_argument("--chat-model", default=GEMMA)
    parser.add_argument("--headed", action="store_true")
    return parser.parse_args()


async def click_text(page: Page, text: str) -> None:
    found = await page.evaluate(FIND_TEXT_ELEMENT, text)
    if not found:
        raise AssertionError(f"Text not found: {text}")
    await page.mouse.click(
        found["x"] + min(24, max(4, found["width"] / 2)),
        found["y"] + found["height"] / 2,
    )


async def assert_usage_hint(page: Page) -> str:
    body = await page.locator("body").inner_text()
    match = re.search(
        r"\d+\s*/\s*\d+\s+included AdClaw AI messages left this period\.",
        body,
    )
    if not match:
        raise AssertionError("AdClaw AI included-message balance was not visible")
    return match.group(0)


async def run() -> dict[str, object]:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    results: dict[str, object] = {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=not args.headed)
        page = await browser.new_page(viewport={"width": 1440, "height": 1400})

        reset_response = await page.request.put(
            f"{args.base_url}/api/models/active",
            data={"provider_id": "adclaw-host-ai", "model": args.initial_model},
        )
        if not reset_response.ok:
            raise AssertionError(
                f"Failed to reset active model: {reset_response.status}",
            )

        await page.goto(f"{args.base_url}/models", wait_until="domcontentloaded")
        await page.wait_for_timeout(2500)
        initial_text = await page.locator("body").inner_text()
        if "AdClaw AI" not in initial_text:
            raise AssertionError("AdClaw AI provider is not visible")
        if f"Active: adclaw-host-ai / {args.initial_model}" not in initial_text:
            raise AssertionError("Initial AdClaw AI model is not active")
        if "4 models" not in initial_text:
            raise AssertionError("AdClaw AI model catalog count is not visible")

        usage_hint = await assert_usage_hint(page)
        provider_cards = await page.locator(
            'div[class*="providerCards"] > div[class*="providerCard"]',
        ).all_inner_texts()
        if not provider_cards:
            raise AssertionError("Provider cards were not rendered")
        if "AdClaw AI" not in provider_cards[0]:
            raise AssertionError(f"First provider card is not AdClaw AI: {provider_cards[0]}")
        results["first_provider_card"] = provider_cards[0].splitlines()[0]
        results["usage_hint"] = usage_hint
        await page.screenshot(path=str(args.out / "models-before-switch.png"), full_page=True)

        await click_text(page, "Fast default")
        await page.wait_for_timeout(500)
        await click_text(page, "Balanced reasoning")
        await page.wait_for_timeout(500)
        switch_text = await page.locator("body").inner_text()
        if args.switch_model not in switch_text:
            raise AssertionError("Switch model was not selected")
        await assert_usage_hint(page)
        await page.screenshot(path=str(args.out / "models-switch-selected.png"), full_page=True)

        await click_text(page, "Balanced reasoning")
        await page.wait_for_timeout(500)
        await click_text(page, "Creative quality")
        await page.wait_for_timeout(500)
        chat_model_text = await page.locator("body").inner_text()
        if args.chat_model not in chat_model_text:
            raise AssertionError("Chat model was not selected")
        await assert_usage_hint(page)
        await page.screenshot(path=str(args.out / "models-chat-model-selected.png"), full_page=True)

        await click_text(page, "Save")
        await page.wait_for_timeout(1500)
        active_response = await page.request.get(f"{args.base_url}/api/models/active")
        active_payload = await active_response.json()
        active_llm = active_payload.get("active_llm", {})
        if active_llm.get("provider_id") != "adclaw-host-ai":
            raise AssertionError(f"Unexpected active provider: {active_llm}")
        if active_llm.get("model") != args.chat_model:
            raise AssertionError(f"Unexpected active model: {active_llm}")
        results["active_model_after_save"] = active_llm["model"]

        await page.goto(f"{args.base_url}/chat", wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)
        prompt = "Reply in under 20 words and include E2E_OK."
        await page.locator("textarea.adclaw-sender-input").fill(prompt)
        started = time.perf_counter()
        await page.keyboard.press("Enter")
        await page.wait_for_function(
            "(model) => document.body.innerText.includes('E2E_OK') && document.body.innerText.includes(model)",
            arg=args.chat_model,
            timeout=30000,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        chat_text = await page.locator("body").inner_text()
        if "E2E_OK" not in chat_text or args.chat_model not in chat_text:
            raise AssertionError("Chat did not respond through the selected model")
        results["chat_elapsed_ms"] = elapsed_ms
        await page.screenshot(path=str(args.out / "chat-selected-model-response.png"), full_page=True)

        await browser.close()

    results_path = args.out / "result.json"
    results_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    return results


if __name__ == "__main__":
    asyncio.run(run())
