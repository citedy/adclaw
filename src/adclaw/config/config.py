# -*- coding: utf-8 -*-
import os
import re
from typing import Optional, Union, Dict, List, Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator

from ..constant import (
    HEARTBEAT_DEFAULT_EVERY,
    HEARTBEAT_DEFAULT_TARGET,
)


class BaseChannelConfig(BaseModel):
    """Base for channel config (read from config.json, no env)."""

    enabled: bool = False
    bot_prefix: str = ""
    filter_tool_messages: bool = True


class IMessageChannelConfig(BaseChannelConfig):
    db_path: str = "~/Library/Messages/chat.db"
    poll_sec: float = 1.0


class DiscordConfig(BaseChannelConfig):
    bot_token: str = ""
    http_proxy: str = ""
    http_proxy_auth: str = ""


class DingTalkConfig(BaseChannelConfig):
    """DingTalk: client_id, client_secret; media_dir for received media."""

    client_id: str = ""
    client_secret: str = ""
    media_dir: str = "~/.adclaw/media"


class FeishuConfig(BaseChannelConfig):
    """Feishu/Lark channel: app_id, app_secret; optional encrypt_key,
    verification_token for event handler. media_dir for received media.
    """

    app_id: str = ""
    app_secret: str = ""
    encrypt_key: str = ""
    verification_token: str = ""
    media_dir: str = "~/.adclaw/media"


class QQConfig(BaseChannelConfig):
    app_id: str = ""
    client_secret: str = ""


class TelegramConfig(BaseChannelConfig):
    """Telegram channel: bot_token from BotFather; optional proxy."""

    bot_token: str = ""
    http_proxy: str = ""
    http_proxy_auth: str = ""
    show_typing: Optional[bool] = None


class ConsoleConfig(BaseChannelConfig):
    """Console channel: prints agent responses to stdout."""

    enabled: bool = True


class ChannelConfig(BaseModel):
    """Built-in channel configs; extra keys allowed for plugin channels."""

    model_config = ConfigDict(extra="allow")

    imessage: IMessageChannelConfig = IMessageChannelConfig()
    discord: DiscordConfig = DiscordConfig()
    dingtalk: DingTalkConfig = DingTalkConfig()
    feishu: FeishuConfig = FeishuConfig()
    qq: QQConfig = QQConfig()
    telegram: TelegramConfig = TelegramConfig()
    console: ConsoleConfig = ConsoleConfig()


class LastApiConfig(BaseModel):
    host: Optional[str] = None
    port: Optional[int] = None


class ActiveHoursConfig(BaseModel):
    """Optional active window for heartbeat (e.g. 08:00–22:00)."""

    start: str = "08:00"
    end: str = "22:00"


class HeartbeatConfig(BaseModel):
    """Heartbeat: run agent with HEARTBEAT.md as query at interval."""

    model_config = {"populate_by_name": True}

    enabled: bool = Field(default=False, description="Whether heartbeat is on")
    every: str = Field(default=HEARTBEAT_DEFAULT_EVERY)
    target: str = Field(default=HEARTBEAT_DEFAULT_TARGET)
    active_hours: Optional[ActiveHoursConfig] = Field(
        default=None,
        alias="activeHours",
    )


class AgentsDefaultsConfig(BaseModel):
    heartbeat: Optional[HeartbeatConfig] = None


class AgentsRunningConfig(BaseModel):
    """Agent runtime behavior configuration."""

    max_iters: int = Field(
        default=50,
        ge=1,
        description=(
            "Maximum number of reasoning-acting iterations for ReAct agent"
        ),
    )
    max_input_length: int = Field(
        default=128 * 1024,  # 128K = 131072 tokens
        ge=1000,
        description=(
            "Maximum input length (tokens) for the model context window"
        ),
    )


class AOMConfig(BaseModel):
    """Always-On Memory Agent configuration."""

    enabled: bool = False
    embedding_backend: Literal["local", "api"] = "local"
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_api_url: str = ""
    embedding_dimensions: int = 384
    consolidation_interval_minutes: int = 60
    consolidation_enabled: bool = True
    auto_capture_mcp: bool = True
    auto_capture_skills: bool = True
    auto_capture_chat: bool = True
    file_inbox_enabled: bool = False
    importance_threshold: float = 0.3
    max_memories: int = 100_000
    # Advanced multimodal mode
    multimodal_provider: Literal["gemini", "openai", "anthropic"] = "gemini"
    multimodal_api_key: str = ""
    multimodal_model: str = ""
    multimodal_api_url: str = ""


class PersonaCronConfig(BaseModel):
    """Cron configuration for a persona."""
    enabled: bool = False
    schedule: str = ""
    prompt: str = ""
    output: str = "chat"  # "chat" | "file" | "both"


class PersonaConfig(BaseModel):
    """Configuration for a single agent persona."""
    id: str
    name: str
    soul_md: str = ""
    model_provider: str = ""
    model_name: str = ""
    skills: list[str] = []
    mcp_clients: list[str] = []
    is_coordinator: bool = False
    cron: PersonaCronConfig | None = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, v):
        if not re.match(r'^[a-z0-9_-]+$', v):
            raise ValueError(f"Persona ID must be lowercase alphanumeric, hyphens, underscores: {v}")
        return v


def validate_single_coordinator(personas: list[PersonaConfig]) -> None:
    coordinators = [p for p in personas if p.is_coordinator]
    if len(coordinators) > 1:
        raise ValueError(f"Only one coordinator allowed, found: {[c.id for c in coordinators]}")


class AgentsConfig(BaseModel):
    defaults: AgentsDefaultsConfig = Field(
        default_factory=AgentsDefaultsConfig,
    )
    running: AgentsRunningConfig = Field(
        default_factory=AgentsRunningConfig,
    )
    language: str = Field(
        default="en",
        description="Language for agent MD files (en/zh)",
    )
    installed_md_files_language: Optional[str] = Field(
        default=None,
        description="Language of currently installed md files",
    )
    always_on_memory: AOMConfig = Field(
        default_factory=AOMConfig,
        description="Always-On Memory Agent configuration",
    )
    personas: list[PersonaConfig] = []

    @model_validator(mode='after')
    def _validate_single_coordinator(self):
        coordinators = [p for p in self.personas if p.is_coordinator]
        if len(coordinators) > 1:
            raise ValueError(f"Only one coordinator allowed, found: {[c.id for c in coordinators]}")
        return self


class LastDispatchConfig(BaseModel):
    """Last channel/user/session that received a user-originated reply."""

    channel: str = ""
    user_id: str = ""
    session_id: str = ""


class MCPClientConfig(BaseModel):
    """Configuration for a single MCP client."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    description: str = ""
    enabled: bool = True
    transport: Literal["stdio", "streamable_http", "sse"] = "stdio"
    url: str = ""
    headers: Dict[str, str] = Field(default_factory=dict)
    command: str = ""
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    cwd: str = ""

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_fields(cls, data):
        """Normalize common MCP field aliases from third-party examples."""
        if not isinstance(data, dict):
            return data

        payload = dict(data)

        if "isActive" in payload and "enabled" not in payload:
            payload["enabled"] = payload["isActive"]

        if "baseUrl" in payload and "url" not in payload:
            payload["url"] = payload["baseUrl"]

        if "type" in payload and "transport" not in payload:
            payload["transport"] = payload["type"]

        if (
            "transport" not in payload
            and (payload.get("url") or payload.get("baseUrl"))
            and not payload.get("command")
        ):
            payload["transport"] = "streamable_http"

        raw_transport = payload.get("transport")
        if isinstance(raw_transport, str):
            normalized = raw_transport.strip().lower()
            transport_alias_map = {
                "streamablehttp": "streamable_http",
                "http": "streamable_http",
                "stdio": "stdio",
                "sse": "sse",
            }
            payload["transport"] = transport_alias_map.get(
                normalized,
                normalized,
            )

        return payload

    @model_validator(mode="after")
    def _validate_transport_config(self):
        """Validate required fields for each MCP transport type."""
        if self.transport == "stdio":
            if not self.command.strip():
                raise ValueError("stdio MCP client requires non-empty command")
            return self

        if not self.url.strip():
            raise ValueError(
                f"{self.transport} MCP client requires non-empty url",
            )

        # Auto-inject Authorization header from CITEDY_API_KEY for Citedy MCP
        from urllib.parse import urlparse as _urlparse
        _parsed = _urlparse(self.url)
        if (
            _parsed.scheme == "https"
            and _parsed.hostname == "mcp.citedy.com"
            and "Authorization" not in self.headers
        ):
            api_key = self.env.get("CITEDY_API_KEY") or os.getenv(
                "CITEDY_API_KEY", ""
            )
            if api_key:
                self.headers["Authorization"] = f"Bearer {api_key}"
                self.headers.setdefault(
                    "Accept", "application/json, text/event-stream"
                )

        return self


class MCPConfig(BaseModel):
    """MCP clients configuration.

    Uses a dict to allow dynamic client definitions.
    Default tavily_search client is created and auto-enabled if API key exists.
    """

    clients: Dict[str, MCPClientConfig] = Field(
        default_factory=lambda: {
            "tavily_search": MCPClientConfig(
                name="tavily_mcp",
                # Auto-enable if TAVILY_API_KEY exists in environment
                enabled=bool(os.getenv("TAVILY_API_KEY")),
                command="npx",
                args=["-y", "tavily-mcp@latest"],
                env={"TAVILY_API_KEY": os.getenv("TAVILY_API_KEY", "")},
            ),
            "citedy": MCPClientConfig(
                name="citedy_mcp",
                description="Citedy SEO & Marketing Tools (52 tools)",
                enabled=bool(os.getenv("CITEDY_API_KEY")),
                transport="streamable_http",
                url="https://mcp.citedy.com/mcp",
                headers={},
                env={"CITEDY_API_KEY": os.getenv("CITEDY_API_KEY", "")},
            ),
            # --- Browser & Web Scraping MCP Servers ---
            "agent_browser": MCPClientConfig(
                name="agent_browser_mcp",
                description="Agent Browser: headless browser for AI agents (Vercel)",
                enabled=True,
                command="npx",
                args=[
                    "-y",
                    "@agent-infra/mcp-server-browser@latest",
                    "--headless",
                ],
                env={
                    "AGENT_BROWSER_EXECUTABLE_PATH": os.getenv(
                        "AGENT_BROWSER_EXECUTABLE_PATH",
                        os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH", ""),
                    ),
                },
            ),
            "playwright": MCPClientConfig(
                name="playwright_mcp",
                description="Playwright browser automation (Microsoft)",
                enabled=False,
                command="npx",
                args=["-y", "@playwright/mcp@latest", "--headless"],
            ),
            "puppeteer": MCPClientConfig(
                name="puppeteer_mcp",
                description="Puppeteer headless Chrome automation",
                enabled=False,
                command="npx",
                args=["-y", "@modelcontextprotocol/server-puppeteer"],
                env={
                    "PUPPETEER_LAUNCH_OPTIONS": '{"headless":true,"args":["--no-sandbox"]}',
                },
            ),
            "browser_use": MCPClientConfig(
                name="browser_use_mcp",
                description="AI-driven browser automation agent",
                enabled=False,
                command="uvx",
                args=["--from", "browser-use[cli]", "browser-use", "--mcp"],
                env={"BROWSER_USE_HEADLESS": "true"},
            ),
            "browserbase": MCPClientConfig(
                name="browserbase_mcp",
                description="Stagehand/Browserbase AI-first browser (cloud)",
                enabled=bool(os.getenv("BROWSERBASE_API_KEY")),
                command="npx",
                args=["-y", "@browserbasehq/mcp-server-browserbase"],
                env={
                    "BROWSERBASE_API_KEY": os.getenv("BROWSERBASE_API_KEY", ""),
                    "BROWSERBASE_PROJECT_ID": os.getenv("BROWSERBASE_PROJECT_ID", ""),
                },
            ),
            "firecrawl": MCPClientConfig(
                name="firecrawl_mcp",
                description="Firecrawl web scraping & crawling",
                enabled=bool(os.getenv("FIRECRAWL_API_KEY")),
                command="npx",
                args=["-y", "firecrawl-mcp"],
                env={
                    "FIRECRAWL_API_KEY": os.getenv("FIRECRAWL_API_KEY", ""),
                },
            ),
            "crawl4ai": MCPClientConfig(
                name="crawl4ai_mcp",
                description="Crawl4AI open-source web crawler for AI",
                enabled=False,
                transport="sse",
                url="http://localhost:11235/mcp/sse",
            ),
            # --- AI-Powered Search ---
            "xai_search": MCPClientConfig(
                name="xai_search_mcp",
                description="xAI Grok: web search + X/Twitter search",
                enabled=bool(os.getenv("XAI_API_KEY")),
                command="python3",
                args=["-m", "adclaw.tools.xai_search_mcp"],
                env={"XAI_API_KEY": os.getenv("XAI_API_KEY", "")},
            ),
            "exa": MCPClientConfig(
                name="exa_mcp",
                description="Exa AI search: web, code, people, companies",
                enabled=bool(os.getenv("EXA_API_KEY")),
                command="npx",
                args=["-y", "exa-mcp-server"],
                env={"EXA_API_KEY": os.getenv("EXA_API_KEY", "")},
            ),
            # --- SEO & Search ---
            "ahrefs": MCPClientConfig(
                name="ahrefs_mcp",
                description="Ahrefs SEO: backlinks, keywords, traffic (official)",
                enabled=bool(os.getenv("AHREFS_API_KEY")),
                command="npx",
                args=["-y", "ahrefs-mcp-server"],
                env={"AHREFS_API_KEY": os.getenv("AHREFS_API_KEY", "")},
            ),
            "dataforseo": MCPClientConfig(
                name="dataforseo_mcp",
                description="DataForSEO: SERP, keywords, domains (official)",
                enabled=bool(os.getenv("DATAFORSEO_LOGIN")),
                command="npx",
                args=["-y", "@dataforseo/mcp-server"],
                env={
                    "DATAFORSEO_LOGIN": os.getenv("DATAFORSEO_LOGIN", ""),
                    "DATAFORSEO_PASSWORD": os.getenv("DATAFORSEO_PASSWORD", ""),
                },
            ),
            "seo_mcp": MCPClientConfig(
                name="seo_mcp",
                description="Free SEO research powered by Ahrefs data",
                enabled=False,
                command="npx",
                args=["-y", "seo-mcp"],
            ),
            "google_search_console": MCPClientConfig(
                name="gsc_mcp",
                description="Google Search Console SEO insights",
                enabled=False,
                command="npx",
                args=["-y", "mcp-gsc"],
            ),
            # --- Analytics ---
            "google_analytics": MCPClientConfig(
                name="ga4_mcp",
                description="Google Analytics GA4 (official, 200+ metrics)",
                enabled=False,
                command="npx",
                args=["-y", "@google-analytics/mcp"],
            ),
            # --- Advertising ---
            "google_ads": MCPClientConfig(
                name="google_ads_mcp",
                description="Google Ads campaigns & reporting (official)",
                enabled=bool(os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")),
                command="npx",
                args=["-y", "@googleads/mcp-server"],
                env={
                    "GOOGLE_ADS_DEVELOPER_TOKEN": os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", ""),
                },
            ),
            "meta_ads": MCPClientConfig(
                name="meta_ads_mcp",
                description="Meta/Facebook & Instagram Ads management",
                enabled=bool(os.getenv("META_ADS_ACCESS_TOKEN")),
                command="npx",
                args=["-y", "meta-ads-mcp"],
                env={
                    "META_ADS_ACCESS_TOKEN": os.getenv("META_ADS_ACCESS_TOKEN", ""),
                },
            ),
            # --- Social Media ---
            "twitter": MCPClientConfig(
                name="twitter_mcp",
                description="Twitter/X: posts, search, threads, followers",
                enabled=bool(os.getenv("TWITTER_API_KEY")),
                command="npx",
                args=["-y", "twitter-mcp"],
                env={
                    "TWITTER_API_KEY": os.getenv("TWITTER_API_KEY", ""),
                    "TWITTER_API_SECRET": os.getenv("TWITTER_API_SECRET", ""),
                    "TWITTER_ACCESS_TOKEN": os.getenv("TWITTER_ACCESS_TOKEN", ""),
                    "TWITTER_ACCESS_SECRET": os.getenv("TWITTER_ACCESS_SECRET", ""),
                },
            ),
            "youtube": MCPClientConfig(
                name="youtube_mcp",
                description="YouTube: videos, analytics, Shorts",
                enabled=bool(os.getenv("YOUTUBE_API_KEY")),
                command="npx",
                args=["-y", "youtube-mcp-server"],
                env={"YOUTUBE_API_KEY": os.getenv("YOUTUBE_API_KEY", "")},
            ),
            "instagram": MCPClientConfig(
                name="instagram_mcp",
                description="Instagram: insights, publish photos & videos",
                enabled=bool(os.getenv("INSTAGRAM_ACCESS_TOKEN")),
                command="npx",
                args=["-y", "ig-mcp"],
                env={
                    "INSTAGRAM_ACCESS_TOKEN": os.getenv("INSTAGRAM_ACCESS_TOKEN", ""),
                },
            ),
            "linkedin": MCPClientConfig(
                name="linkedin_mcp",
                description="LinkedIn: posts, profiles, companies, scraping",
                enabled=False,
                command="npx",
                args=["-y", "linkedin-mcp-server"],
            ),
            # --- Email Marketing ---
            "sendgrid": MCPClientConfig(
                name="sendgrid_mcp",
                description="SendGrid email: contacts, templates, campaigns",
                enabled=bool(os.getenv("SENDGRID_API_KEY")),
                command="npx",
                args=["-y", "sendgrid-mcp"],
                env={"SENDGRID_API_KEY": os.getenv("SENDGRID_API_KEY", "")},
            ),
            # --- CRM ---
            "hubspot": MCPClientConfig(
                name="hubspot_mcp",
                description="HubSpot CRM: contacts, deals, companies",
                enabled=bool(os.getenv("HUBSPOT_ACCESS_TOKEN")),
                command="npx",
                args=["-y", "mcp-hubspot"],
                env={
                    "HUBSPOT_ACCESS_TOKEN": os.getenv("HUBSPOT_ACCESS_TOKEN", ""),
                },
            ),
            # --- Utilities ---
            "agent_inbox": MCPClientConfig(
                name="agent_inbox_mcp",
                description="Disposable email inboxes for agents (GSD)",
                enabled=False,
                command="npx",
                args=["-y", "gsd-agent-inbox"],
            ),
            # --- Multimodal (Image/Video/Speech/Music) ---
            "minimax": MCPClientConfig(
                name="minimax_mcp",
                description="MiniMax: image, video, speech, music generation (official)",
                enabled=bool(os.getenv("MINIMAX_API_KEY")),
                command="npx",
                args=["-y", "minimax-mcp-js"],
                env={
                    "MINIMAX_API_KEY": os.getenv("MINIMAX_API_KEY", ""),
                    "MINIMAX_API_HOST": os.getenv("MINIMAX_API_HOST", "https://api.minimaxi.chat"),
                    "MINIMAX_RESOURCE_MODE": "url",
                },
            ),
        },
    )


class Config(BaseModel):
    """Root config (config.json)."""

    channels: ChannelConfig = ChannelConfig()
    mcp: MCPConfig = MCPConfig()
    last_api: LastApiConfig = LastApiConfig()
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    last_dispatch: Optional[LastDispatchConfig] = None
    # When False, channel output hides tool call/result details (show "...").
    show_tool_details: bool = False


ChannelConfigUnion = Union[
    IMessageChannelConfig,
    DiscordConfig,
    DingTalkConfig,
    FeishuConfig,
    QQConfig,
    TelegramConfig,
    ConsoleConfig,
]
