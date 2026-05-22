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
type LiveChatStage = "thinking" | "tools" | "writing" | "error";

const LIVE_STATUS_SLOW_SECONDS = 12;
const LIVE_STATUS_LONG_SECONDS = 45;
const LIVE_STATUS_SUCCESS_CLEAR_DELAY_MS = 900;
const LIVE_STATUS_ERROR_CLEAR_DELAY_MS = 5000;

interface LiveChatStatus {
  requestId: string;
  personaName: string;
  stage: LiveChatStage;
  detail: string;
  startedAt: number;
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

function classifyStreamText(value: string): LiveChatStage | null {
  const lower = value.toLowerCase();
  if (
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

  if (type === "message" || object === "message_delta") {
    return "writing";
  }

  return null;
}

function classifyStreamEvent(eventText: string): LiveChatStage | null {
  const data = eventText
    .split(/\r?\n/)
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n")
    .trim();

  if (!data || data === "[DONE]") return null;

  try {
    const structuredStage = classifyStreamPayload(JSON.parse(data));
    return structuredStage || classifyStreamText(data);
  } catch {
    return classifyStreamText(data);
  }
}

function liveDetailForStage(stage: LiveChatStage) {
  if (stage === "tools") return "Checking workspace tools and Citedy services.";
  if (stage === "writing") return "Writing the answer now.";
  if (stage === "error") return "The answer stream was interrupted.";
  return "Thinking through the request.";
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
  const [statusClock, setStatusClock] = useState(Date.now());
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
    if (!liveChatStatus) return undefined;
    const timer = window.setInterval(() => setStatusClock(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [liveChatStatus]);

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
        console.error("Failed to check model configuration:", error);
        return handleModelError();
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
      let response: Response;

      try {
        response = await fetch(url, {
          method: "POST",
          headers,
          body: JSON.stringify(requestBody),
          signal: data.signal,
        });
      } catch (error) {
        updateLiveStatus(requestId, {
          stage: "error",
          detail:
            error instanceof Error
              ? error.message
              : "The answer request failed before streaming.",
        });
        clearLiveStatus(requestId, LIVE_STATUS_ERROR_CLEAR_DELAY_MS);
        throw error;
      }

      if (!response.ok) {
        updateLiveStatus(requestId, {
          stage: "error",
          detail: "The answer request failed before streaming.",
        });
        clearLiveStatus(requestId, LIVE_STATUS_ERROR_CLEAR_DELAY_MS);
        return response;
      }

      if (!response.body) {
        updateLiveStatus(requestId, {
          stage: "error",
          detail: "The answer response was empty.",
        });
        clearLiveStatus(requestId, LIVE_STATUS_ERROR_CLEAR_DELAY_MS);
        return response;
      }

      const decoder = new TextDecoder();
      const stream = new ReadableStream<Uint8Array>({
        async start(controller) {
          const reader = response.body!.getReader();
          let eventBuffer = "";
          try {
            for (;;) {
              const { done, value } = await reader.read();
              if (done) break;
              if (value) {
                eventBuffer += decoder.decode(value, { stream: true });
                const events = eventBuffer.split(/\r?\n\r?\n/);
                eventBuffer = events.pop() || "";

                for (const eventText of events) {
                  const stage = classifyStreamEvent(eventText);
                  if (stage) {
                    updateLiveStatus(requestId, {
                      stage,
                      detail: liveDetailForStage(stage),
                    });
                  }
                }
                controller.enqueue(value);
              }
            }

            eventBuffer += decoder.decode();
            if (eventBuffer.trim()) {
              const stage = classifyStreamEvent(eventBuffer);
              if (stage) {
                updateLiveStatus(requestId, {
                  stage,
                  detail: liveDetailForStage(stage),
                });
              }
            }

            updateLiveStatus(requestId, {
              stage: "writing",
              detail: "Answer is ready.",
            });
            controller.close();
            clearLiveStatus(requestId);
          } catch (error) {
            updateLiveStatus(requestId, {
              stage: "error",
              detail:
                error instanceof Error
                  ? error.message
                  : "The answer stream was interrupted.",
            });
            controller.error(error);
            clearLiveStatus(requestId, LIVE_STATUS_ERROR_CLEAR_DELAY_MS);
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

  const elapsedSeconds = liveChatStatus
    ? Math.max(0, Math.round((statusClock - liveChatStatus.startedAt) / 1000))
    : 0;
  const liveDetail =
    liveChatStatus && elapsedSeconds > LIVE_STATUS_LONG_SECONDS
      ? "Still working. Long article or tool work can take a few minutes."
      : liveChatStatus && elapsedSeconds > LIVE_STATUS_SLOW_SECONDS
      ? `${liveChatStatus.detail} No action needed.`
      : liveChatStatus?.detail;

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
        {liveChatStatus && (
          <div
            className={styles.liveProgress}
            role="status"
            aria-live="polite"
            aria-atomic="true"
          >
            <div className={styles.liveProgressInner}>
              <span className={styles.liveProgressPulse} aria-hidden="true" />
              <div>
                <div className={styles.liveProgressTitle}>
                  {liveChatStatus.personaName} is working
                </div>
                <div className={styles.liveProgressDetail}>
                  {liveDetail}
                  <span aria-hidden="true"> {elapsedSeconds}s</span>
                </div>
              </div>
            </div>
          </div>
        )}
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
