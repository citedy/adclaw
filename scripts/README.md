# Scripts

Run from **repo root**.

## Build wheel (with latest console)

```bash
bash scripts/wheel_build.sh
```

- Builds the console frontend (`console/`), copies `console/dist` to `src/adclaw/console/dist`, then builds the wheel. Output: `dist/*.whl`.

## Build Docker image

```bash
bash scripts/docker_build.sh [IMAGE_TAG] [EXTRA_ARGS...]
```

- Default tag: `adclaw:latest`. Uses `deploy/Dockerfile` (multi-stage: builds console then Python app).
- Example: `bash scripts/docker_build.sh myreg/adclaw:v1 --no-cache`.

## AdClaw AI model-selection browser E2E

```bash
python scripts/host_ai_model_selection_e2e.py --base-url http://127.0.0.1:8088 --out artifacts/host-ai-model-selection-e2e
```

- Verifies the AdClaw AI provider appears first in Models, included-message balance is visible under the model selector, model selection persists, and Chat answers through the selected model.
- Requires `playwright` and a running AdClaw app with the `adclaw-host-ai` provider configured.
