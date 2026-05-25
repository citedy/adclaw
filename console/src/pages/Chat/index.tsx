import React, { useMemo, useState, useEffect, useRef } from "react";
import {
  AgentScopeRuntimeWebUI,
  IAgentScopeRuntimeWebUIOptions,
} from "@agentscope-ai/chat";
import { Modal, Button, Result } from "antd";
import { ExclamationCircleOutlined, SettingOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import sessionApi from "./sessionApi";
import { useLocalStorageState } from "ahooks";
import defaultConfig, { DefaultConfig } from "./OptionsPanel/defaultConfig";
import Weather from "./Weather";
import PersonaSelector from "./PersonaSelector";
import { getPersonaColor } from "./personaColors";
import { getApiUrl, getApiToken } from "../../api/config";
import { providerApi } from "../../api/modules/provider";
import { personaApi } from "../../api/modules/persona";
import type { Persona } from "../../api/types/persona";
import styles from "./index.module.less";

interface PersonaTabsProps {
  personas: Persona[];
  activeTab: string;
  onTabChange: (tabId: string) => void;
}

function hexToRgba(color: string, alpha: number): string {
  const normalized = color.replace("#", "");

  if (normalized.length !== 6) {
    return `rgba(99, 102, 241, ${alpha})`;
  }

  const red = parseInt(normalized.slice(0, 2), 16);
  const green = parseInt(normalized.slice(2, 4), 16);
  const blue = parseInt(normalized.slice(4, 6), 16);

  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

function PersonaTabs({ personas, activeTab, onTabChange }: PersonaTabsProps) {
  const nonCoordinator = personas.filter((p) => !p.is_coordinator);

  const containerStyle: React.CSSProperties = {
    display: "flex",
    flexWrap: "wrap",
    alignItems: "center",
    gap: 8,
    padding: "12px 24px 10px",
    flexShrink: 0,
  };

  const baseTabStyle: React.CSSProperties = {
    minHeight: 34,
    padding: "0 14px",
    borderRadius: 999,
    fontSize: 13,
    fontWeight: 500,
    cursor: "pointer",
    color: "#64748b",
    transition:
      "background 0.15s ease, border-color 0.15s ease, color 0.15s ease, box-shadow 0.15s ease",
    display: "flex",
    alignItems: "center",
    gap: 8,
    userSelect: "none",
    background: "rgba(255, 255, 255, 0.78)",
    border: "1px solid rgba(226, 232, 240, 0.9)",
    boxShadow: "0 1px 2px rgba(15, 23, 42, 0.04)",
    outline: "none",
  };

  const allTabColor = "#64748b";
  const isAllActive = activeTab === "all";

  return (
    <div style={containerStyle}>
      <button
        style={{
          ...baseTabStyle,
          background: isAllActive
            ? hexToRgba(allTabColor, 0.12)
            : baseTabStyle.background,
          borderColor: isAllActive
            ? hexToRgba(allTabColor, 0.24)
            : "rgba(226, 232, 240, 0.9)",
          color: isAllActive ? allTabColor : "#94a3b8",
          boxShadow: isAllActive
            ? `0 8px 20px ${hexToRgba(allTabColor, 0.12)}`
            : baseTabStyle.boxShadow,
        }}
        onClick={() => onTabChange("all")}
        aria-pressed={isAllActive}
      >
        <span
          style={{
            width: 7,
            height: 7,
            borderRadius: "50%",
            background: allTabColor,
            display: "inline-block",
            flexShrink: 0,
          }}
        />
        All
      </button>

      {nonCoordinator.map((persona) => {
        const color = getPersonaColor(persona);
        const isActive = activeTab === persona.id;
        return (
          <button
            key={persona.id}
            style={{
              ...baseTabStyle,
              background: isActive
                ? hexToRgba(color, 0.12)
                : baseTabStyle.background,
              borderColor: isActive
                ? hexToRgba(color, 0.24)
                : "rgba(226, 232, 240, 0.9)",
              color: isActive ? color : "#94a3b8",
              boxShadow: isActive
                ? `0 8px 20px ${hexToRgba(color, 0.12)}`
                : baseTabStyle.boxShadow,
            }}
            onClick={() => onTabChange(persona.id)}
            aria-pressed={isActive}
          >
            <span
              style={{
                width: 7,
                height: 7,
                borderRadius: "50%",
                background: color,
                display: "inline-block",
                flexShrink: 0,
              }}
            />
            {persona.name}
          </button>
        );
      })}
    </div>
  );
}

interface CustomWindow extends Window {
  currentSessionId?: string;
  currentUserId?: string;
  currentChannel?: string;
}

declare const window: CustomWindow;

type OptionsConfig = DefaultConfig;
type LiveChatStage = "thinking" | "tools" | "writing" | "waking" | "error";

const LIVE_STATUS_SLOW_SECONDS = 12;
const LIVE_STATUS_LONG_SECONDS = 45;
const LIVE_STATUS_SUCCESS_CLEAR_DELAY_MS = 900;
const WORKSPACE_WAKE_POLL_INTERVAL_MS = 5000;
const WORKSPACE_WAKE_MAX_POLLS = 36;
const WORKSPACE_WAKE_TITLE = "Waking your marketing office";
const WORKSPACE_WAKE_DETAIL =
  "Your message is saved. We will send it as soon as AdClaw is ready. Usually 1-2 minutes.";
const WORKSPACE_WAKE_LONG_DETAIL =
  "Still waking your marketing office. Your message is saved and will be sent automatically.";
const WORKSPACE_WAKE_READY_DETAIL =
  "AdClaw is ready. Sending your saved message now.";
// The AgentScope stream consumer only parses the body on 2xx responses.
// Synthetic chat failures use SSE with 200 so the UI renders a failed bubble.
const STREAM_FAILURE_STATUS = 200;

interface LiveChatStatus {
  requestId: string;
  personaName: string;
  stage: LiveChatStage;
  detail: string;
  startedAt: number;
}

interface StreamFailureMetadata {
  upstream_status?: number;
  upstream_status_text?: string;
}

interface StreamEventInspection {
  stage: LiveChatStage | null;
  hasRenderableOutput: boolean;
}

interface WorkspaceWakePayload {
  code?: string;
  message?: string;
  wake_url?: string;
  status_url?: string;
  return_to?: string;
  retry_after_seconds?: number;
  state?: {
    status?: string;
  };
}

interface RuntimeSession {
  session_id?: string;
  user_id?: string;
  channel?: string;
}

interface RuntimeMessageContent {
  type?: string;
  text?: string;
  [key: string]: unknown;
}

interface RuntimeMessage {
  content?: RuntimeMessageContent | RuntimeMessageContent[] | string;
  session?: RuntimeSession;
  [key: string]: unknown;
}

interface CustomFetchData {
  input: RuntimeMessage[];
  biz_params?: Record<string, unknown>;
  signal?: AbortSignal;
}

function isRuntimeMessageContent(
  value: unknown,
): value is RuntimeMessageContent {
  return typeof value === "object" && value !== null;
}

function displayPersonaName(personas: Persona[], personaId: string | null) {
  if (!personaId) return "AdClaw";
  return (
    personas.find((persona) => persona.id === personaId)?.name || personaId
  );
}

function isUserCancellation(signal?: AbortSignal): boolean {
  return signal?.aborted === true;
}

function isWorkspaceWakeCode(code: unknown): boolean {
  return code === "workspace_sleeping" || code === "workspace_waking";
}

function isWorkspaceWakePayload(value: unknown): value is WorkspaceWakePayload {
  if (typeof value !== "object" || value === null) return false;
  return isWorkspaceWakeCode((value as WorkspaceWakePayload).code);
}

function isHostedSleepingModelPreflightError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);
  return (
    message.includes("workspace_sleeping") ||
    message.includes("workspace_waking") ||
    message.includes("Your AdClaw office is sleeping") ||
    message.includes("Your AdClaw office is waking")
  );
}

async function workspaceWakePayloadFromResponse(
  response: Response,
): Promise<WorkspaceWakePayload | null> {
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) return null;
  if (![202, 409].includes(response.status)) return null;

  try {
    const payload = (await response.clone().json()) as unknown;
    return isWorkspaceWakePayload(payload) ? payload : null;
  } catch {
    return null;
  }
}

function sleepWithAbort(ms: number, signal?: AbortSignal): Promise<void> {
  if (signal?.aborted) {
    return Promise.reject(new DOMException("Aborted", "AbortError"));
  }

  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(resolve, ms);
    const onAbort = () => {
      window.clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    };
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

async function wakeWorkspaceForQueuedMessage(
  payload: WorkspaceWakePayload,
  signal: AbortSignal | undefined,
  onStatus: (detail: string) => void,
): Promise<void> {
  if (!payload.status_url) {
    throw new Error("Workspace wake status URL is missing.");
  }

  if (payload.code === "workspace_sleeping") {
    if (!payload.wake_url) {
      throw new Error("Workspace wake URL is missing.");
    }

    onStatus(WORKSPACE_WAKE_DETAIL);
    const wakeResponse = await fetch(payload.wake_url, {
      method: "POST",
      headers: { accept: "application/json" },
      credentials: "same-origin",
      signal,
    });

    if (![200, 202, 409].includes(wakeResponse.status)) {
      throw new Error("Wake request was rejected. Retry from the dashboard.");
    }
  }

  for (let attempt = 0; attempt < WORKSPACE_WAKE_MAX_POLLS; attempt += 1) {
    const statusResponse = await fetch(payload.status_url, {
      headers: { accept: "application/json" },
      credentials: "same-origin",
      signal,
    });

    if (statusResponse.ok) {
      const statusPayload = (await statusResponse.json()) as {
        state?: { status?: string };
      };
      const status = statusPayload.state?.status;

      if (status === "running") {
        onStatus(WORKSPACE_WAKE_READY_DETAIL);
        return;
      }

      if (status === "error") {
        throw new Error("Workspace wake failed. Retry from the dashboard.");
      }

      onStatus(
        status === "starting"
          ? WORKSPACE_WAKE_LONG_DETAIL
          : WORKSPACE_WAKE_DETAIL,
      );
    } else if ([401, 403].includes(statusResponse.status)) {
      throw new Error("Your AdClaw session expired. Sign in and retry.");
    } else if (statusResponse.status === 404) {
      throw new Error(
        "Workspace wake status is unavailable. Retry from the dashboard.",
      );
    } else if (statusResponse.status >= 400) {
      throw new Error(
        "Workspace wake status failed. Retry from the dashboard.",
      );
    }

    await sleepWithAbort(WORKSPACE_WAKE_POLL_INTERVAL_MS, signal);
  }

  throw new Error(
    "Wake is taking longer than expected. Retry from the dashboard.",
  );
}

function encodeStreamFailure(
  code: string,
  message: string,
  metadata: StreamFailureMetadata = {},
): Uint8Array {
  const now = Math.floor(Date.now() / 1000);
  const id = `stream_failure_${now}`;
  return new TextEncoder().encode(
    `data: ${JSON.stringify({
      id: `response_${id}`,
      object: "response",
      status: "failed",
      created_at: now,
      completed_at: now,
      error: { code, message, ...metadata },
      output: [
        {
          id,
          object: "message",
          status: "failed",
          error: null,
          type: "error",
          role: "assistant",
          content: [],
          code,
          message,
          metadata,
        },
      ],
    })}\n\n`,
  );
}

function createStreamFailureResponse(
  code: string,
  message: string,
  metadata: StreamFailureMetadata = {},
): Response {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(encodeStreamFailure(code, message, metadata));
      controller.close();
    },
  });
  const headers = new Headers({
    "Content-Type": "text/event-stream; charset=utf-8",
    "Cache-Control": "no-cache",
  });

  if (metadata.upstream_status) {
    headers.set("X-AdClaw-Upstream-Status", String(metadata.upstream_status));
  }

  return new Response(stream, {
    status: STREAM_FAILURE_STATUS,
    headers,
  });
}

function enqueueStreamFailure(
  controller: ReadableStreamDefaultController<Uint8Array>,
  code: string,
  message: string,
) {
  try {
    controller.enqueue(encodeStreamFailure(code, message));
  } catch {
    closeStreamQuietly(controller);
    return;
  }

  closeStreamQuietly(controller);
}

function closeStreamQuietly(
  controller: ReadableStreamDefaultController<Uint8Array>,
) {
  try {
    controller.close();
  } catch {
    // The consumer may have already cancelled the stream.
  }
}

function streamDataFromEvent(eventText: string): string {
  return eventText
    .split(/\r?\n/)
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n")
    .trim();
}

function classifyStreamText(value: string): LiveChatStage | null {
  const lower = value.toLowerCase();
  if (
    lower.includes("mcp_call") ||
    lower.includes("mcp_tool_call") ||
    lower.includes("mcp_tool_call_output") ||
    lower.includes("plugin_call") ||
    lower.includes("function_call") ||
    lower.includes("tool_call")
  ) {
    return "tools";
  }
  if (lower.includes("reasoning") || lower.includes("thinking")) {
    return "thinking";
  }
  if (
    lower.includes("message_delta") ||
    lower.includes("response.output_text") ||
    lower.includes("text_delta") ||
    lower.includes('"role":"assistant"') ||
    lower.includes('"role": "assistant"')
  ) {
    return "writing";
  }
  return null;
}

function classifyStreamPayload(payload: unknown): LiveChatStage | null {
  if (typeof payload !== "object" || payload === null) return null;

  const record = payload as Record<string, unknown>;
  const type = typeof record.type === "string" ? record.type.toLowerCase() : "";
  const object =
    typeof record.object === "string" ? record.object.toLowerCase() : "";

  if (
    type.includes("mcp_call") ||
    type.includes("mcp_tool_call") ||
    type.includes("plugin_call") ||
    type.includes("function_call") ||
    type.includes("tool_call")
  ) {
    return "tools";
  }

  if (type === "reasoning" || object === "reasoning") {
    return "thinking";
  }

  if (
    type === "message" ||
    type.includes("message_delta") ||
    type.includes("output_text") ||
    type.includes("text_delta") ||
    type.includes("content_delta") ||
    object === "message_delta"
  ) {
    return "writing";
  }

  return null;
}

function assistantOutputValueHasText(value: unknown): boolean {
  if (typeof value === "string") return value.trim().length > 0;
  if (Array.isArray(value)) return value.some(assistantOutputValueHasText);
  if (typeof value !== "object" || value === null) return false;

  const record = value as Record<string, unknown>;
  return ["content", "text", "refusal", "delta", "output_text"].some(
    (key) => key in record && assistantOutputValueHasText(record[key]),
  );
}

function contentHasAssistantOutput(content: unknown): boolean {
  if (typeof content === "string") return content.trim().length > 0;
  if (!Array.isArray(content)) return assistantOutputValueHasText(content);

  return content.some((item) => {
    if (typeof item === "string") return item.trim().length > 0;
    if (!isRuntimeMessageContent(item)) return false;

    return (
      assistantOutputValueHasText(item.text) ||
      assistantOutputValueHasText(item.refusal) ||
      assistantOutputValueHasText(item.delta)
    );
  });
}

function toolOutputValueHasText(value: unknown): boolean {
  if (typeof value === "string") return value.trim().length > 0;
  if (typeof value === "number" || typeof value === "boolean") return true;
  if (Array.isArray(value)) return value.some(toolOutputValueHasText);
  if (typeof value !== "object" || value === null) return false;

  const record = value as Record<string, unknown>;
  return ["output", "result", "text", "content", "data"].some(
    (key) => key in record && toolOutputValueHasText(record[key]),
  );
}

function contentHasToolOutput(content: unknown): boolean {
  if (typeof content === "string") return content.trim().length > 0;
  if (!Array.isArray(content)) return false;

  return content.some((item) => {
    if (typeof item === "string") return item.trim().length > 0;
    if (!isRuntimeMessageContent(item)) return false;

    return (
      toolOutputValueHasText(item.data) ||
      toolOutputValueHasText(item.output) ||
      toolOutputValueHasText(item.result) ||
      toolOutputValueHasText(item.text) ||
      toolOutputValueHasText(item.content)
    );
  });
}

function isToolOutputPayload(type: string, object: string): boolean {
  return (
    type.includes("mcp_call_output") ||
    type.includes("mcp_tool_call_output") ||
    type.includes("plugin_call_output") ||
    type.includes("function_call_output") ||
    type.includes("tool_call_output") ||
    object.includes("call_output")
  );
}

function isAssistantContentPayload(type: string, object: string): boolean {
  return (
    type === "message" ||
    type.includes("message_delta") ||
    type.includes("output_text") ||
    type.includes("text_delta") ||
    type.includes("content_delta") ||
    object === "message_delta" ||
    object === "content"
  );
}

function payloadHasRenderableOutput(payload: unknown): boolean {
  if (typeof payload !== "object" || payload === null) return false;

  const record = payload as Record<string, unknown>;
  const type = typeof record.type === "string" ? record.type.toLowerCase() : "";
  const object =
    typeof record.object === "string" ? record.object.toLowerCase() : "";

  if (
    isAssistantContentPayload(type, object) &&
    contentHasAssistantOutput(record.content)
  ) {
    return true;
  }

  if (object === "content" && type === "data") {
    return toolOutputValueHasText(record.data);
  }

  if (isToolOutputPayload(type, object)) {
    return (
      contentHasToolOutput(record.content) ||
      toolOutputValueHasText(record.output) ||
      toolOutputValueHasText(record.result) ||
      toolOutputValueHasText(record.text) ||
      toolOutputValueHasText(record.data)
    );
  }

  if (object === "content") {
    return (
      assistantOutputValueHasText(record.text) ||
      assistantOutputValueHasText(record.refusal) ||
      assistantOutputValueHasText(record.delta)
    );
  }

  if (
    type.includes("output_text") ||
    type.includes("text_delta") ||
    type.includes("content_delta")
  ) {
    return (
      assistantOutputValueHasText(record.text) ||
      assistantOutputValueHasText(record.output_text) ||
      assistantOutputValueHasText(record.delta)
    );
  }

  return false;
}

function inspectStreamEvent(eventText: string): StreamEventInspection {
  const data = streamDataFromEvent(eventText);

  if (!data || data === "[DONE]") {
    return { stage: null, hasRenderableOutput: false };
  }

  try {
    const payload = JSON.parse(data);
    const structuredStage = classifyStreamPayload(payload);
    return {
      stage: structuredStage || classifyStreamText(data),
      hasRenderableOutput: payloadHasRenderableOutput(payload),
    };
  } catch {
    return {
      stage: classifyStreamText(data),
      hasRenderableOutput: false,
    };
  }
}

function liveDetailForStage(stage: LiveChatStage) {
  if (stage === "tools") return "Checking workspace tools and Citedy services.";
  if (stage === "writing") return "Writing the answer now.";
  if (stage === "waking") return WORKSPACE_WAKE_DETAIL;
  if (stage === "error") return "AdClaw could not finish the answer.";
  return "Thinking through the request.";
}

function liveDetailForElapsed(status: LiveChatStatus, elapsedSeconds: number) {
  if (status.stage === "error") return status.detail;
  if (status.stage === "waking") {
    if (elapsedSeconds > LIVE_STATUS_LONG_SECONDS) {
      return WORKSPACE_WAKE_LONG_DETAIL;
    }
    return status.detail;
  }

  if (elapsedSeconds > LIVE_STATUS_LONG_SECONDS) {
    return "Still working. Long article or tool work can take a few minutes.";
  }

  if (elapsedSeconds > LIVE_STATUS_SLOW_SECONDS) {
    return `${status.detail} No action needed.`;
  }

  return status.detail;
}

function LiveProgressStatus({ status }: { status: LiveChatStatus }) {
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    setNow(Date.now());
    if (status.stage === "error") return undefined;

    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [status.requestId, status.startedAt, status.stage]);

  const elapsedSeconds = Math.max(
    0,
    Math.round((now - status.startedAt) / 1000),
  );
  const liveDetail = liveDetailForElapsed(status, elapsedSeconds);

  return (
    <div className={styles.liveProgress}>
      <div className={styles.liveProgressInner}>
        <span
          className={
            status.stage === "error"
              ? styles.liveProgressError
              : styles.liveProgressPulse
          }
          aria-hidden="true"
        />
        <div
          className={styles.liveProgressText}
          role="status"
          aria-live="polite"
          aria-atomic="true"
        >
          <div className={styles.liveProgressTitle}>
            {status.stage === "error"
              ? `${status.personaName} needs a retry`
              : status.stage === "waking"
              ? WORKSPACE_WAKE_TITLE
              : `${status.personaName} is working`}
          </div>
          <div className={styles.liveProgressDetail}>{liveDetail}</div>
        </div>
        {status.stage !== "error" && (
          <span className={styles.liveProgressElapsed} aria-hidden="true">
            {elapsedSeconds}s
          </span>
        )}
      </div>
    </div>
  );
}

export default function ChatPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [showModelPrompt, setShowModelPrompt] = useState(false);
  const [selectedPersona, setSelectedPersona] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>("all");
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [liveChatStatus, setLiveChatStatus] = useState<LiveChatStatus | null>(
    null,
  );
  const clearStatusTimers = useRef<number[]>([]);
  const [optionsConfig] = useLocalStorageState<OptionsConfig>(
    "agent-scope-runtime-webui-options",
    {
      defaultValue: defaultConfig,
      listenStorageChange: true,
    },
  );

  useEffect(() => {
    personaApi
      .listPersonas()
      .then((list) => {
        if (Array.isArray(list)) setPersonas(list);
      })
      .catch((err) => console.warn("Failed to load personas:", err));
  }, []);

  useEffect(() => {
    return () => {
      clearStatusTimers.current.forEach((timer) => window.clearTimeout(timer));
      clearStatusTimers.current = [];
    };
  }, []);

  const handleTabChange = (tabId: string) => {
    setActiveTab(tabId);
    if (tabId === "all") {
      window.currentSessionId = "";
    } else {
      window.currentSessionId = `${tabId}::console--default`;
    }
  };

  const handleConfigureModel = () => {
    setShowModelPrompt(false);
    navigate("/models");
  };

  const handleSkipConfiguration = () => {
    setShowModelPrompt(false);
  };

  // Compute session_id from React state (not global)
  const currentSessionId =
    activeTab === "all" ? "" : `${activeTab}::console--default`;

  const options = useMemo(() => {
    const updateLiveStatus = (
      requestId: string,
      patch: Partial<Omit<LiveChatStatus, "requestId" | "startedAt">>,
    ) => {
      setLiveChatStatus((current) =>
        current?.requestId === requestId ? { ...current, ...patch } : current,
      );
    };

    const clearLiveStatus = (
      requestId: string,
      delayMs = LIVE_STATUS_SUCCESS_CLEAR_DELAY_MS,
    ) => {
      const timer = window.setTimeout(() => {
        clearStatusTimers.current = clearStatusTimers.current.filter(
          (item) => item !== timer,
        );
        setLiveChatStatus((current) =>
          current?.requestId === requestId ? null : current,
        );
      }, delayMs);
      clearStatusTimers.current.push(timer);
    };

    const clearLiveStatusNow = (requestId: string) => {
      setLiveChatStatus((current) =>
        current?.requestId === requestId ? null : current,
      );
    };

    const failLiveStatus = (requestId: string, detail: string) => {
      updateLiveStatus(requestId, {
        stage: "error",
        detail,
      });
    };

    const handleModelError = () => {
      setShowModelPrompt(true);
      return new Response(
        JSON.stringify({
          error: "Model not configured",
          message: "Please configure a model first",
        }),
        {
          status: 400,
          headers: { "Content-Type": "application/json" },
        },
      );
    };

    const customFetch = async (data: CustomFetchData): Promise<Response> => {
      try {
        const activeModels = await providerApi.getActiveModels();

        if (
          !activeModels?.active_llm?.provider_id ||
          !activeModels?.active_llm?.model
        ) {
          return handleModelError();
        }
      } catch (error) {
        if (isHostedSleepingModelPreflightError(error)) {
          console.info(
            "Hosted workspace is sleeping during model preflight; continuing to agent wake flow.",
          );
        } else {
          console.error("Failed to check model configuration:", error);
          return handleModelError();
        }
      }

      const { input, biz_params } = data;

      const lastMessage = input[input.length - 1];
      const session = lastMessage?.session || {};

      const session_id = currentSessionId || session?.session_id || "";
      const user_id = window.currentUserId || session?.user_id || "default";
      const channel = window.currentChannel || session?.channel || "console";
      const requestId = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
      const activePersonaId =
        selectedPersona || (activeTab === "all" ? null : activeTab);
      const personaName = displayPersonaName(personas, activePersonaId);
      clearStatusTimers.current.forEach((timer) => window.clearTimeout(timer));
      clearStatusTimers.current = [];
      setLiveChatStatus({
        requestId,
        personaName,
        stage: "thinking",
        detail: liveDetailForStage("thinking"),
        startedAt: Date.now(),
      });

      // Prepend @persona tag if a persona is selected via chip bar
      const processedInput = input.slice(-1).map((msg) => {
        if (selectedPersona && msg?.content) {
          const contents = Array.isArray(msg.content)
            ? msg.content
            : [msg.content];
          const tagged = contents.map((content) => {
            if (
              isRuntimeMessageContent(content) &&
              content.type === "text" &&
              typeof content.text === "string" &&
              !content.text.startsWith("@")
            ) {
              return {
                ...content,
                text: `@${selectedPersona} ${content.text}`,
              };
            }
            return content;
          });
          return { ...msg, content: tagged };
        }
        return msg;
      });

      const requestBody = {
        input: processedInput,
        session_id,
        user_id,
        channel,
        stream: true,
        ...biz_params,
      };

      const headers: HeadersInit = {
        "Content-Type": "application/json",
      };

      const token = getApiToken();
      if (token) {
        (headers as Record<string, string>).Authorization = `Bearer ${token}`;
      }

      const url = optionsConfig?.api?.baseURL || getApiUrl("/agent/process");
      const sendAgentRequest = () =>
        fetch(url, {
          method: "POST",
          headers,
          body: JSON.stringify(requestBody),
          signal: data.signal,
        });
      let response: Response;

      try {
        response = await sendAgentRequest();
      } catch (error) {
        if (isUserCancellation(data.signal)) {
          clearLiveStatusNow(requestId);
          throw error;
        }

        failLiveStatus(
          requestId,
          "Connection interrupted before AdClaw could start answering. Retry once.",
        );
        return createStreamFailureResponse(
          "Connection interrupted",
          "Connection interrupted before AdClaw could start answering. Retry once.",
        );
      }

      const wakePayload = await workspaceWakePayloadFromResponse(response);
      if (wakePayload) {
        try {
          updateLiveStatus(requestId, {
            stage: "waking",
            detail: WORKSPACE_WAKE_DETAIL,
          });
          await wakeWorkspaceForQueuedMessage(
            wakePayload,
            data.signal,
            (detail) =>
              updateLiveStatus(requestId, {
                stage: "waking",
                detail,
              }),
          );
          response = await sendAgentRequest();
        } catch (error) {
          if (isUserCancellation(data.signal)) {
            clearLiveStatusNow(requestId);
            throw error;
          }

          const message =
            error instanceof Error
              ? error.message
              : "Workspace wake failed. Retry from the dashboard.";
          failLiveStatus(requestId, message);
          return createStreamFailureResponse("Workspace wake failed", message);
        }
      }

      if (!response.ok) {
        failLiveStatus(
          requestId,
          "AdClaw could not start the answer. Retry once.",
        );
        return createStreamFailureResponse(
          "Answer needs retry",
          "AdClaw could not start the answer. Retry once.",
          {
            upstream_status: response.status,
            upstream_status_text: response.statusText,
          },
        );
      }

      if (!response.body) {
        failLiveStatus(
          requestId,
          "AdClaw returned an empty response. Retry once.",
        );
        return createStreamFailureResponse(
          "Empty response",
          "AdClaw returned an empty response. Retry once.",
        );
      }

      const decoder = new TextDecoder();
      const stream = new ReadableStream<Uint8Array>({
        async start(controller) {
          const reader = response.body!.getReader();
          let eventBuffer = "";
          let sawRenderableOutput = false;
          let releasedRenderableStream = false;
          const pendingChunks: Uint8Array[] = [];
          const flushPendingChunks = () => {
            pendingChunks
              .splice(0)
              .forEach((chunk) => controller.enqueue(chunk));
            releasedRenderableStream = true;
          };
          try {
            for (;;) {
              const { done, value } = await reader.read();
              if (done) break;
              if (value) {
                let chunkHasRenderableOutput = false;
                eventBuffer += decoder.decode(value, { stream: true });
                const events = eventBuffer.split(/\r?\n\r?\n/);
                eventBuffer = events.pop() || "";

                for (const eventText of events) {
                  const inspection = inspectStreamEvent(eventText);
                  if (inspection.hasRenderableOutput) {
                    sawRenderableOutput = true;
                    chunkHasRenderableOutput = true;
                  }
                  if (inspection.stage) {
                    updateLiveStatus(requestId, {
                      stage: inspection.stage,
                      detail: liveDetailForStage(inspection.stage),
                    });
                  }
                }

                if (releasedRenderableStream) {
                  controller.enqueue(value);
                } else {
                  pendingChunks.push(value);
                  if (chunkHasRenderableOutput) {
                    flushPendingChunks();
                  }
                }
              }
            }

            eventBuffer += decoder.decode();
            if (eventBuffer.trim()) {
              const inspection = inspectStreamEvent(eventBuffer);
              if (inspection.hasRenderableOutput) {
                sawRenderableOutput = true;
              }
              if (inspection.stage) {
                updateLiveStatus(requestId, {
                  stage: inspection.stage,
                  detail: liveDetailForStage(inspection.stage),
                });
              }
            }

            if (sawRenderableOutput && !releasedRenderableStream) {
              flushPendingChunks();
            }

            if (!sawRenderableOutput) {
              failLiveStatus(
                requestId,
                "AdClaw stopped before sending an answer. Retry once.",
              );
              enqueueStreamFailure(
                controller,
                "Answer needs retry",
                "AdClaw stopped before sending an answer. Retry once.",
              );
              return;
            }

            updateLiveStatus(requestId, {
              stage: "writing",
              detail: "Answer is ready.",
            });
            controller.close();
            clearLiveStatus(requestId);
          } catch {
            if (isUserCancellation(data.signal)) {
              clearLiveStatusNow(requestId);
              closeStreamQuietly(controller);
              return;
            }

            failLiveStatus(
              requestId,
              "Connection interrupted while AdClaw was answering. Retry once.",
            );
            enqueueStreamFailure(
              controller,
              "Connection interrupted",
              "Connection interrupted while AdClaw was answering. Retry once.",
            );
          } finally {
            reader.releaseLock();
          }
        },
      });

      return new Response(stream, {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
      });
    };

    return {
      ...optionsConfig,
      session: {
        multiple: true,
        api: sessionApi,
      },
      theme: {
        ...optionsConfig.theme,
      },
      api: {
        ...optionsConfig.api,
        fetch: customFetch,
        cancel(data: { session_id: string }) {
          console.log(data);
        },
      },
      sender: {
        ...optionsConfig?.sender,
        beforeUI: (
          <PersonaSelector
            personas={personas}
            selected={selectedPersona}
            onSelect={setSelectedPersona}
          />
        ),
      },
      customToolRenderConfig: {
        "weather search mock": Weather,
      },
    } as unknown as IAgentScopeRuntimeWebUIOptions;
  }, [optionsConfig, selectedPersona, activeTab, personas, currentSessionId]);

  return (
    <div
      style={{
        height: "100%",
        width: "100%",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {personas.length > 0 && (
        <PersonaTabs
          personas={personas}
          activeTab={activeTab}
          onTabChange={handleTabChange}
        />
      )}
      <div className={styles.chatStage}>
        <AgentScopeRuntimeWebUI key={activeTab} options={options} />
        {liveChatStatus && <LiveProgressStatus status={liveChatStatus} />}
      </div>

      <Modal open={showModelPrompt} closable={false} footer={null} width={480}>
        <Result
          icon={<ExclamationCircleOutlined style={{ color: "#f59e0b" }} />}
          title={t("modelConfig.promptTitle")}
          subTitle={t("modelConfig.promptMessage")}
          extra={[
            <Button key="skip" onClick={handleSkipConfiguration}>
              {t("modelConfig.skipButton")}
            </Button>,
            <Button
              key="configure"
              type="primary"
              icon={<SettingOutlined />}
              onClick={handleConfigureModel}
            >
              {t("modelConfig.configureButton")}
            </Button>,
          ]}
        />
      </Modal>
    </div>
  );
}
