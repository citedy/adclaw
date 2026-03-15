---
name: browser_visible
description: "Launch a real visible browser window (headed mode) instead of headless. Use browser_use with the headed parameter to open, snapshot, click, etc. Ideal for demos, debugging, or when the user wants to see the page."
metadata:
  {
    "adclaw":
      {
        "emoji": "🖥️",
        "requires": {}
      }
  }
---

# Visible Browser (Real Window) Reference

By default, **browser_use** runs in headless mode in the background without opening a browser window. When the user explicitly wants to **open a real browser window**, **see the browser interface**, **use a browser with a GUI**, or **use a visible browser**, this skill should be used: first launch the browser in **headed** mode, then open pages and interact as needed.

## When to Use

- The user says: "Open a real browser", "Open a browser with a GUI", "I want to see the browser", "Don't run in the background, I want to see the window"
- The user wants to watch the page loading, clicking, form filling, etc. in real time (for demos, debugging, or teaching)
- The user needs to interact with a visible page (e.g., login, CAPTCHA, or other scenarios requiring manual intervention)

## How to Use (browser_use)

1. **Launch the browser in visible mode first**
   Call **browser_use** with `action` set to `start` and pass **headed=true**:
   ```json
   {"action": "start", "headed": true}
   ```
   On success, a real Chromium browser window will appear.

2. **Open pages and interact as needed**
   Usage is the same as in headless mode, for example:
   - Open a URL: `{"action": "open", "url": "https://example.com"}`
   - Get the page structure: `{"action": "snapshot"}`
   - Click, type, etc.: use `ref` or `selector` for click, type, and other actions

3. **Close the visible browser**
   When finished, call: `{"action": "stop"}` to close the browser.

## Differences from Default (Headless) Mode

| Mode         | Launch Method                          | Opens a Window?       |
|--------------|----------------------------------------|-----------------------|
| Headless     | `{"action": "start"}`                  | No (background)       |
| Visible      | `{"action": "start", "headed": true}`  | Yes (real window)     |

## Notes

- If a browser is already running, you must `stop` it first and then `start` again with `headed: true` to switch to a visible window.
- Visible mode requires a desktop and graphical environment. It may not work on servers or environments without a display.
