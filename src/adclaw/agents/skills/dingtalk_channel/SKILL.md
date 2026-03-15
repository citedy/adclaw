---
name: dingtalk_channel_connect
description: "Automate DingTalk channel setup using a visible browser. Handles the developer console, Client ID/Secret, bot creation, and Stream mode binding. Pauses at login pages for the user to authenticate."
metadata:
  {
    "adclaw":
      {
        "emoji": "🤖",
        "requires": {}
      }
  }
---

# DingTalk Channel Auto-Connect (Visible Browser)

This skill automates DingTalk app creation and AdClaw channel binding using a visible browser.

## Mandatory Rules

1. Must launch the browser in visible mode:

```json
{"action": "start", "headed": true}
```

2. Must pause at login gates:
   - If the page shows a login screen (e.g., login form, QR code login, phone/password login), stop all automated actions immediately.
   - Clearly instruct the user to log in manually first, then wait for the user to reply "logged in" or "continue".
   - Do not proceed with subsequent steps until the user confirms.

3. Any app configuration change requires creating a new version and publishing before it takes effect:
   - After configuring bot-related settings, **you must publish the bot**.
   - Whether creating a new app or modifying app info (name, description, icon, bot config, etc.), you **must create a new version and publish**.
   - Do not claim the configuration is active until publishing is complete.

## Pre-Execution Confirmation (Must Do First)

Before starting automated clicks, send the user a "configuration confirmation" that clearly states customizable fields, image specifications, and default values. Use the following structured confirmation:

1. Let the user customize the following fields:
   - App name
   - App description
   - Bot icon image URL or local path
   - Bot message preview image URL or local path

2. Clearly state image specifications (prominently):
   - Bot icon: JPG/PNG only, `240x240px` minimum, `1:1` aspect ratio, under `2MB`, no rounded corners.
   - Bot message preview image: `png/jpeg/jpg` format, under `2MB`.

3. Clearly state default values (used automatically if the user does not specify):
   - App name: `AdClaw`
   - App description: `Your personal assistant`
   - Bot icon: `https://img.alicdn.com/imgextra/i4/O1CN01M0iyHF1FVNzM9qjC0_!!6000000000492-2-tps-254-254.png`
   - Bot message preview image: `https://img.alicdn.com/imgextra/i4/O1CN01M0iyHF1FVNzM9qjC0_!!6000000000492-2-tps-254-254.png`

4. If the user provides no custom values, you must explicitly reply:
   - "Proceeding with all default settings (AdClaw / Your personal assistant / default images)."

## Image Upload Strategy (Both Links and Paths Supported)

1. If the user provides a local path, use it directly for upload.
2. If the user provides an image link, download it to a local temporary file first, then upload.
3. The upload action sequence must be:
   - Click the upload entry point on the page (to trigger the file chooser)
   - Then call `file_upload` with the local path array (`paths_json`)
4. If an upload error occurs due to image specification mismatch (dimensions, aspect ratio, file size, format):
   - Pause automation immediately
   - Clearly ask the user to manually upload a compliant image
   - After the user confirms "uploaded" or "continue", resume the workflow from the current step

### Upload Practical Tips

1. The `paths_json` parameter of `file_upload` must be a "JSON string array" — note the escaping:

```json
{
  "action": "file_upload",
  "paths_json": "[\"xxx.png\"]",
  "frame_selector": "iframe[src*=\"/fe/app?isHideOuterFrame=true\"]"
}
```

2. If the page content is inside an iframe, always include `frame_selector` — otherwise the upload control or file chooser may not be found.

3. You must click the upload entry point before calling `file_upload`. Calling it directly will result in:
   - `No chooser. Click upload then file_upload.`

4. Common structural features of the bot icon area that can be used for locating elements (examples):
   - `text: "* Bot Icon"`
   - `button: "Use App Icon"`
   - `button: "avatar"` (usually contains an `img "avatar"` inside)

5. When the snapshot shows both "Use App Icon" and "avatar", prefer clicking the `avatar` button to trigger the upload, then call `file_upload`.

## Automation Workflow

### Step 1: Open the DingTalk Developer Console

1. Launch the browser in visible mode (`headed: true`)
2. Navigate to `https://open-dev.dingtalk.com/`
3. Call `snapshot` to check if login is required

If login is required, pause with the following message:

> Login to the DingTalk Developer Console is required. I have paused automation — please log in using the browser window that appeared. Once done, reply "continue" and I will resume from the current page.

### Step 2: Create an Internal Enterprise App

After the user confirms login, continue:

1. Navigate to the creation path:
   - App Development -> Internal Enterprise Apps -> DingTalk Apps -> Create App
2. Fill in the app information (use user-provided values first, otherwise use defaults):
   - App name: default `AdClaw`
   - App description: default `Your personal assistant`
3. Save and create the app

If the page layout or text differs from expectations, re-run `snapshot` and locate elements based on visible text semantics.

### Step 3: Add Bot Capability and Publish

1. Click **Add App Capability** under **App Capabilities**, find **Bot**, and add it
2. Toggle the switch button next to **Bot Configuration** to enabled
3. Fill in **Bot Name**, **Bot Summary**, and **Bot Description**
4. Upload the **Bot Icon** (user-provided or default):
   - Click the image below the bot icon label
   - Default image URL: `https://img.alicdn.com/imgextra/i4/O1CN01M0iyHF1FVNzM9qjC0_!!6000000000492-2-tps-254-254.png`
   - If a link is provided, download it locally first, then upload
   - If the image is rejected as non-compliant, pause and ask the user to manually upload a compliant image before continuing
5. Upload the **Bot Message Preview Image** (user-provided or default):
   - Click the image below the bot message preview image label
   - Default image URL: `https://img.alicdn.com/imgextra/i4/O1CN01M0iyHF1FVNzM9qjC0_!!6000000000492-2-tps-254-254.png`
   - If a link is provided, download it locally first, then upload
   - If the image is rejected as non-compliant, pause and ask the user to manually upload a compliant image before continuing
6. Confirm the message receiving mode is set to `Stream Mode`
7. Select **Publish** — a confirmation dialog will appear, confirm the publish. Note: **You must publish the bot** before proceeding to the next step

### Step 4: Create a Version and Publish

1. Go to `App Publishing -> Version Management & Publishing`
2. Create a new version (required after every configuration change)
3. Fill in the version description, set app visibility to all employees
4. Follow the on-screen prompts to complete publishing — a new dialog will appear, confirm the publish
5. Only after seeing a successful publish status may you proceed to subsequent steps or tell the user the configuration is active

### Step 5: Retrieve Credentials

1. Go to `Basic Information -> Credentials & Basic Info`
2. Inform the user that the `Client ID` (AppKey) and `Client Secret` (AppSecret) are on this page. Do not modify them proactively — guide the user to bind them on their own

## AdClaw Binding Methods

After obtaining the credentials, guide the user to choose one of the following methods:

1. Console UI configuration:
   - In the AdClaw console, go to `Settings -> Channels -> DingTalk`
   - Enter the `Client ID` and `Client Secret`

2. Configuration file method:

```json
"dingtalk": {
  "enabled": true,
  "bot_prefix": "[BOT]",
  "client_id": "Your Client ID",
  "client_secret": "Your Client Secret"
}
```

Path: `~/.adclaw/config.json`, under `channels.dingtalk`.

### Credential Delivery Requirements (Mandatory)

1. The agent is only responsible for guiding the user to the credentials page and displaying the `Client ID` and actual `Client Secret`.
2. The agent must not proactively modify the `console` configuration or `~/.adclaw/config.json`.
3. The agent must instruct the user to fill in the credentials manually using one of these two methods:
   - Console UI: `Settings -> Channels -> DingTalk`
   - Configuration file: edit the `channels.dingtalk` section in `~/.adclaw/config.json`

## Browser Tool Call Pattern

Follow this default sequence:

1. `start` with `headed: true`
2. `open`
3. `snapshot`
4. `click` / `type` / `select_option` / `press_key` as needed
5. frequent `snapshot` after page transitions
6. `stop` when done

## Stability and Recovery Strategy

- Prefer using `ref` from the latest `snapshot`; only use `selector` when necessary.
- After each critical click or navigation, use a short wait (`wait_for`) and immediately re-run `snapshot`.
- If the session expires or re-login is required mid-process, pause again and wait for the user to log in before resuming from the current step.
- If automation is blocked by tenant permissions, admin approval, or similar issues, clearly explain the blocker and ask the user to complete that step manually before continuing.
