import { useState, useEffect } from "react";
import { Button, Empty, Modal, Card } from "@agentscope-ai/design";
import type { MCPClientCreateRequest, MCPClientInfo } from "../../../api/types";
import { MCPClientCard } from "./components";
import { useMCP } from "./useMCP";
import { useTranslation } from "react-i18next";
import { request } from "../../../api/request";

type MCPTransport = "stdio" | "streamable_http" | "sse";
const CITEDY_MCP_TOOLS_URL = "https://www.citedy.com/tools/mcp";
type MCPClientPayload = MCPClientCreateRequest["client"];
type NormalizedMCPClientPayload = {
  name: string;
  description: string;
  enabled: boolean;
  transport: MCPTransport;
  url: string;
  headers: Record<string, string>;
  command: string;
  args: string[];
  env: Record<string, string>;
  cwd: string;
};

interface CitedyStatus {
  configured: boolean;
  api_key_prefix?: string;
  balance?: { credits: number; status: string } | null;
  developer_url: string;
  billing_url: string;
}

type MCPClientDraft = Partial<MCPClientPayload> & {
  type?: unknown;
  baseUrl?: unknown;
  isActive?: unknown;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function normalizeTransport(raw?: unknown): MCPTransport | undefined {
  if (typeof raw !== "string") return undefined;
  const value = raw.trim().toLowerCase();
  switch (value) {
    case "stdio":
      return "stdio";
    case "sse":
      return "sse";
    case "streamablehttp":
    case "streamable_http":
    case "http":
      return "streamable_http";
    default:
      return undefined;
  }
}

function normalizeClientData(
  key: string,
  rawData: MCPClientDraft,
): NormalizedMCPClientPayload {
  const transport =
    normalizeTransport(rawData.transport ?? rawData.type) ??
    (rawData.url || rawData.baseUrl || !rawData.command
      ? "streamable_http"
      : "stdio");

  const command =
    transport === "stdio" ? (rawData.command ?? "").toString() : "";
  const enabled =
    typeof rawData.enabled === "boolean"
      ? rawData.enabled
      : typeof rawData.isActive === "boolean"
      ? rawData.isActive
      : true;

  return {
    name: rawData.name || key,
    description: rawData.description || "",
    enabled,
    transport,
    url: (rawData.url || rawData.baseUrl || "").toString(),
    headers: rawData.headers || {},
    command,
    args: Array.isArray(rawData.args) ? rawData.args : [],
    env: rawData.env || {},
    cwd: (rawData.cwd || "").toString(),
  };
}

function MCPPage() {
  const { t } = useTranslation();
  const {
    clients,
    loading,
    toggleEnabled,
    deleteClient,
    createClient,
    updateClient,
  } = useMCP();
  const [hoverKey, setHoverKey] = useState<string | null>(null);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [citedyStatus, setCitedyStatus] = useState<CitedyStatus | null>(null);

  useEffect(() => {
    request<CitedyStatus>("/citedy/status")
      .then(setCitedyStatus)
      .catch(() => {});
  }, []);
  const [newClientJson, setNewClientJson] = useState(`{
  "mcpServers": {
    "example-client": {
      "command": "npx",
      "args": ["-y", "@example/mcp-server"],
      "env": {
        "API_KEY": "<YOUR_API_KEY>"
      }
    }
  }
}`);

  const handleToggleEnabled = async (
    client: MCPClientInfo,
    e?: React.MouseEvent,
  ) => {
    e?.stopPropagation();
    await toggleEnabled(client);
  };

  const handleDelete = async (client: MCPClientInfo, e?: React.MouseEvent) => {
    e?.stopPropagation();
    await deleteClient(client);
  };

  const handleCreateClient = async () => {
    try {
      const parsed: unknown = JSON.parse(newClientJson);

      // Support two formats:
      // Format 1: { "mcpServers": { "key": { "command": "...", ... } } }
      // Format 2: { "key": { "command": "...", ... } }
      // Format 3: { "key": "...", "name": "...", "command": "...", ... } (direct)

      const clientsToCreate: Array<{
        key: string;
        data: NormalizedMCPClientPayload;
      }> = [];

      if (isRecord(parsed) && isRecord(parsed.mcpServers)) {
        // Format 1: nested mcpServers
        Object.entries(parsed.mcpServers).forEach(([key, data]) => {
          if (!isRecord(data)) return;

          const normalizedData = normalizeClientData(
            key,
            data as MCPClientDraft,
          );
          clientsToCreate.push({
            key,
            data: normalizedData,
          });
        });
      } else if (
        isRecord(parsed) &&
        typeof parsed.key === "string" &&
        (parsed.command || parsed.url || parsed.baseUrl)
      ) {
        // Format 3: direct format with key field
        const { key, ...clientData } = parsed;
        if (typeof key === "string") {
          clientsToCreate.push({
            key,
            data: normalizeClientData(key, clientData as MCPClientDraft),
          });
        }
      } else if (isRecord(parsed)) {
        // Format 2: direct client objects with keys
        Object.entries(parsed).forEach(([key, data]) => {
          if (
            !isRecord(data) ||
            (!data.command && !data.url && !data.baseUrl)
          ) {
            return;
          }

          clientsToCreate.push({
            key,
            data: normalizeClientData(key, data as MCPClientDraft),
          });
        });
      }

      // Create all clients
      let allSuccess = true;
      for (const { key, data } of clientsToCreate) {
        const success = await createClient(key, data);
        if (!success) allSuccess = false;
      }

      if (allSuccess) {
        setCreateModalOpen(false);
        setNewClientJson(`{
  "mcpServers": {
    "example-client": {
      "command": "npx",
      "args": ["-y", "@example/mcp-server"],
      "env": {
        "API_KEY": "<YOUR_API_KEY>"
      }
    }
  }
}`);
      }
    } catch {
      alert("Invalid JSON format");
    }
  };

  return (
    <div style={{ padding: 24 }}>
      <div className="citedy-page-header">
        <div>
          <h1 className="citedy-page-title">{t("mcp.title")}</h1>
          <p className="citedy-page-description">{t("mcp.description")}</p>
        </div>
        <Button type="primary" onClick={() => setCreateModalOpen(true)}>
          {t("mcp.create")}
        </Button>
      </div>

      {citedyStatus && (
        <Card
          className={`citedy-promo-card ${
            citedyStatus.configured ? "configured" : "unconfigured"
          }`}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <div>
              <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>
                <a
                  href={CITEDY_MCP_TOOLS_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Citedy SEO & Marketing Tools
                </a>
              </h3>
              <p style={{ margin: "4px 0 0", color: "#475569", fontSize: 13 }}>
                {citedyStatus.configured
                  ? `API Key: ${citedyStatus.api_key_prefix || "configured"}`
                  : "API key not configured — get a free key to unlock 59 marketing tools"}
                {citedyStatus.balance &&
                  ` | Balance: ${citedyStatus.balance.credits} credits`}
              </p>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              {!citedyStatus.configured && (
                <Button
                  type="primary"
                  onClick={() =>
                    window.open(citedyStatus.developer_url, "_blank")
                  }
                >
                  Get API Key
                </Button>
              )}
              {citedyStatus.configured && (
                <Button
                  onClick={() =>
                    window.open(citedyStatus.billing_url, "_blank")
                  }
                >
                  Top Up Balance
                </Button>
              )}
            </div>
          </div>
        </Card>
      )}

      {loading ? (
        <div style={{ textAlign: "center", padding: 60 }}>
          <p style={{ color: "#64748b" }}>{t("common.loading")}</p>
        </div>
      ) : clients.length === 0 ? (
        <Empty description={t("mcp.emptyState")} />
      ) : (
        <div className="citedy-content-grid">
          {clients.map((client) => (
            <MCPClientCard
              key={client.key}
              client={client}
              onToggle={handleToggleEnabled}
              onDelete={handleDelete}
              onUpdate={updateClient}
              isHovered={hoverKey === client.key}
              onMouseEnter={() => setHoverKey(client.key)}
              onMouseLeave={() => setHoverKey(null)}
            />
          ))}
        </div>
      )}

      <Modal
        title={t("mcp.create")}
        open={createModalOpen}
        onCancel={() => setCreateModalOpen(false)}
        footer={
          <div style={{ textAlign: "right" }}>
            <Button
              onClick={() => setCreateModalOpen(false)}
              style={{ marginRight: 8 }}
            >
              {t("common.cancel")}
            </Button>
            <Button type="primary" onClick={handleCreateClient}>
              {t("common.create")}
            </Button>
          </div>
        }
        width={800}
      >
        <div style={{ marginBottom: 12 }}>
          <p style={{ margin: 0, fontSize: 13, color: "#475569" }}>
            {t("mcp.formatSupport")}:
          </p>
          <ul
            style={{
              margin: "8px 0",
              padding: "0 0 0 20px",
              fontSize: 12,
              color: "#64748b",
            }}
          >
            <li>
              Standard format:{" "}
              <code>{`{ "mcpServers": { "key": {...} } }`}</code>
            </li>
            <li>
              Direct format: <code>{`{ "key": {...} }`}</code>
            </li>
            <li>
              Single format:{" "}
              <code>{`{ "key": "...", "name": "...", "command": "..." }`}</code>
            </li>
          </ul>
        </div>
        <textarea
          value={newClientJson}
          onChange={(e) => setNewClientJson(e.target.value)}
          style={{
            width: "100%",
            minHeight: 400,
            fontFamily: "Monaco, Courier New, monospace",
            fontSize: 13,
            padding: 16,
            border: "1px solid #e2e8f0",
            borderRadius: 4,
            resize: "vertical",
          }}
        />
      </Modal>
    </div>
  );
}

export default MCPPage;
