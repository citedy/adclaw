# -----------------------------------------------------------------------------
# Stage 1: build console frontend (dist not committed in repo).
# -----------------------------------------------------------------------------
FROM agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/node:slim AS console-builder
WORKDIR /app
COPY console /app/console
RUN mkdir -p /app/src/adclaw/console
RUN cd /app/console && npm ci --include=dev && NODE_OPTIONS="--max-old-space-size=3072" npm run build

# -----------------------------------------------------------------------------
# Stage 2: runtime image with Python, optional Chromium, and app.
# -----------------------------------------------------------------------------
FROM agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/node:slim

# Build variant: "core" | "browser" | "full"
#   core    — Python + AdClaw + Telegram only (no Chromium, no optional channels)
#   browser — core + Chromium/xvfb + Playwright/PinchTab/agent-browser
#   full    — browser + Feishu/Discord/DingTalk channels + desktop tools
ARG ADCLAW_VARIANT=full

# Pip extras to install (overrides variant default if provided).
# Variant defaults: core="[local]", browser="[browser,local]", full="[all,local]"
ARG ADCLAW_PIP_EXTRAS=""

# Preload default local embedding model during image build by default.
ARG ADCLAW_PRELOAD_EMBEDDINGS=1

# ENV variables
ENV NODE_ENV=production
ENV WORKSPACE_DIR=/app
ENV ADCLAW_WORKING_DIR=/app/working
ENV HF_HOME=/app/model-cache/huggingface
ENV SENTENCE_TRANSFORMERS_HOME=/app/model-cache/sentence-transformers
ENV ADCLAW_MEMORY_MANAGER_START_MODE=background
ENV ADCLAW_ENABLE_REME=0
ENV ADCLAW_REME_LIGHT_TOKEN_COUNTER=1
ENV ADCLAW_MEMORY_MANAGER_BACKGROUND_DELAY_SECONDS=5
ENV ADCLAW_MEMORY_MANAGER_MAX_LOADAVG=2.0
ENV ADCLAW_MEMORY_COMPACT_BATCH_MESSAGES=80
ENV ADCLAW_REME_RETENTION_DAYS=30
ENV MEMORY_STORE_BACKEND=sqlite
ENV FTS_ENABLED=true

# Default enabled channels (can be overridden at runtime with -e ADCLAW_ENABLED_CHANNELS=...).
ARG ADCLAW_ENABLED_CHANNELS="discord,dingtalk,feishu,qq,console,telegram"
ENV ADCLAW_ENABLED_CHANNELS=${ADCLAW_ENABLED_CHANNELS}

ARG DEBIAN_FRONTEND=noninteractive

# -----------------------------------------------------------------------------
# Base system packages (all variants)
# -----------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --fix-missing \
    curl  \
    python3  \
    python3-pip  \
    python3-venv \
    build-essential  \
    libssl-dev  \
    git  \
    supervisor  \
    vim  \
    gettext-base \
  && rm -rf /var/lib/apt/lists/* \
  && apt-get clean

# -----------------------------------------------------------------------------
# Browser stack (only for browser/full variants)
# -----------------------------------------------------------------------------
RUN if [ "$ADCLAW_VARIANT" != "core" ]; then \
      apt-get update && apt-get install -y --fix-missing \
        xfce4 \
        xfce4-terminal \
        xvfb \
        dbus-x11 \
        fonts-wqy-zenhei \
        fonts-wqy-microhei \
        chromium \
        chromium-sandbox \
        libx11-xcb1 \
        libxcomposite1 \
        libxdamage1 \
        libxext6 \
        libxfixes3 \
        libxi6 \
        libxtst6 \
        libnss3 \
        libglib2.0-0 \
        libdrm2 \
        libgbm1 \
        libasound2 \
        fonts-liberation \
        libu2f-udev \
      && rm -rf /var/lib/apt/lists/* \
      && apt-get clean \
      && sed -i 's/^CHROMIUM_FLAGS=""/CHROMIUM_FLAGS="--no-sandbox"/' /usr/bin/chromium ; \
    fi

# PinchTab: token-efficient browser control for AI agents (browser/full only).
RUN if [ "$ADCLAW_VARIANT" != "core" ]; then \
      curl -fsSL https://pinchtab.com/install.sh | bash \
      && cp /root/.pinchtab/bin/*/pinchtab-linux-* /usr/local/bin/pinchtab-bin \
      && chmod 755 /usr/local/bin/pinchtab-bin ; \
    fi
ENV PINCHTAB_PORT=9867

# agent-browser: install CLI globally (browser/full only).
RUN if [ "$ADCLAW_VARIANT" != "core" ]; then \
      npm install -g agent-browser sitefetch ; \
    fi

# Browser env vars (harmless if binaries missing)
ENV AGENT_BROWSER_EXECUTABLE_PATH=/usr/bin/chromium
ENV PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
ENV ADCLAW_RUNNING_IN_CONTAINER=1
ENV ADCLAW_VARIANT=${ADCLAW_VARIANT}

WORKDIR ${WORKSPACE_DIR}

RUN python3 -m venv venv
ENV PATH="/app/venv/bin:$PATH"

COPY pyproject.toml README.md ./
COPY src ./src
# Inject console dist from build stage (vite outputs to ../src/adclaw/console/).
COPY --from=console-builder /app/src/adclaw/console/ ./src/adclaw/console/

# Install CPU-only PyTorch first (avoids downloading 2GB CUDA build),
# then install app with variant-specific extras.
#   core    → [local]                    — Python + AdClaw + AOM embeddings
#   browser → [browser,local]            — + Playwright
#   full    → [all,local]                — + all optional channels + desktop tools
# ADCLAW_PIP_EXTRAS can override this computed default.
RUN EXTRAS="${ADCLAW_PIP_EXTRAS}"; \
    if [ -z "$EXTRAS" ]; then \
      case "$ADCLAW_VARIANT" in \
        core)    EXTRAS="[local]" ;; \
        browser) EXTRAS="[browser,local]" ;; \
        full)    EXTRAS="[all,local]" ;; \
        *)       EXTRAS="[all,local]" ;; \
      esac; \
    fi; \
    echo ">>> Installing AdClaw with extras=${EXTRAS} (variant=${ADCLAW_VARIANT})" && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir ".${EXTRAS}"

# Preload the default local embedding model at build time so first production
# memory queries don't stall while downloading from Hugging Face.
RUN mkdir -p /app/model-cache \
    && if [ "$ADCLAW_PRELOAD_EMBEDDINGS" = "1" ]; then \
      python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" ; \
    else \
      echo ">>> Skipping embedding model preload"; \
    fi

# Non-root user for running the app (supervisord stays root for system services).
RUN groupadd -r adclaw && useradd -r -g adclaw -m -s /bin/bash adclaw \
  && mkdir -p /app/working /app/working.secret /app/logs /home/adclaw/.config/pinchtab /app/model-cache \
  && chown -R adclaw:adclaw /app/working /app/working.secret /app/logs /home/adclaw/.config /app/model-cache

# Config.json is generated at runtime by entrypoint.sh (only if missing),
# so it persists user settings across container restarts.

# AdClaw app port (default 8088). Override at runtime with -e ADCLAW_PORT=3000.
ENV ADCLAW_PORT=8088

COPY deploy/config/supervisord.conf.template /etc/supervisor/conf.d/supervisord.conf.template
COPY deploy/config/supervisord.browser.conf.template /etc/supervisor/conf.d/supervisord.browser.conf.template
COPY deploy/entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh

EXPOSE 8088

CMD ["/entrypoint.sh"]
