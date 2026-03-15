import React, { useMemo, useState, useEffect } from "react";
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
import "./index.module.less";

interface PersonaTabsProps {
  personas: Persona[];
  activeTab: string;
  onTabChange: (tabId: string) => void;
}

function PersonaTabs({ personas, activeTab, onTabChange }: PersonaTabsProps) {
  const nonCoordinator = personas.filter((p) => !p.is_coordinator);

  const containerStyle: React.CSSProperties = {
    display: "flex",
    gap: 0,
    borderBottom: "1px solid rgba(226,232,240,0.6)",
    padding: "0 24px",
    flexShrink: 0,
  };

  const baseTabStyle: React.CSSProperties = {
    padding: "10px 16px",
    fontSize: 13,
    fontWeight: 500,
    cursor: "pointer",
    color: "#64748b",
    transition: "all 0.15s",
    display: "flex",
    alignItems: "center",
    gap: 6,
    userSelect: "none",
    background: "none",
    border: "none",
    borderBottom: "2px solid transparent",
    outline: "none",
  };

  const allTabColor = "#64748b";
  const isAllActive = activeTab === "all";

  return (
    <div style={containerStyle}>
      <button
        style={{
          ...baseTabStyle,
          borderBottomColor: isAllActive ? allTabColor : "transparent",
          color: isAllActive ? allTabColor : "#94a3b8",
          fontWeight: isAllActive ? 600 : 500,
        }}
        onClick={() => onTabChange("all")}
      >
        <span
          style={{
            width: 6,
            height: 6,
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
              borderBottomColor: isActive ? color : "transparent",
              color: isActive ? color : "#94a3b8",
              fontWeight: isActive ? 600 : 500,
            }}
            onClick={() => onTabChange(persona.id)}
          >
            <span
              style={{
                width: 6,
                height: 6,
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

export default function ChatPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [showModelPrompt, setShowModelPrompt] = useState(false);
  const [selectedPersona, setSelectedPersona] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>("all");
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [optionsConfig] = useLocalStorageState<OptionsConfig>(
    "agent-scope-runtime-webui-options",
    {
      defaultValue: defaultConfig,
      listenStorageChange: true,
    },
  );

  useEffect(() => {
    personaApi.listPersonas().then((list) => {
      if (Array.isArray(list)) setPersonas(list);
    }).catch((err) => console.warn("Failed to load personas:", err));
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
  const currentSessionId = activeTab === "all" ? "" : `${activeTab}::console--default`;

  const options = useMemo(() => {
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

    const customFetch = async (data: {
      input: any[];
      biz_params?: any;
      signal?: AbortSignal;
    }): Promise<Response> => {
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

      // Prepend @persona tag if a persona is selected via chip bar
      const processedInput = input.slice(-1).map((msg: any) => {
        if (selectedPersona && msg?.content) {
          const contents = Array.isArray(msg.content) ? msg.content : [msg.content];
          const tagged = contents.map((c: any) => {
            if (c?.type === "text" && c.text && !c.text.startsWith("@")) {
              return { ...c, text: `@${selectedPersona} ${c.text}` };
            }
            return c;
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
      return fetch(url, {
        method: "POST",
        headers,
        body: JSON.stringify(requestBody),
        signal: data.signal,
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
    <div style={{ height: "100%", width: "100%", display: "flex", flexDirection: "column" }}>
      {personas.length > 0 && (
        <PersonaTabs
          personas={personas}
          activeTab={activeTab}
          onTabChange={handleTabChange}
        />
      )}
      <div style={{ flex: 1, minHeight: 0 }}>
        <AgentScopeRuntimeWebUI key={activeTab} options={options} />
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
