import { useState, useEffect, useCallback } from "react";
import { Alert, Button, Card, Table, Tag, Modal, Space, Spin } from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  RefreshCw,
  Heart,
  AlertTriangle,
  XCircle,
  CheckCircle,
  RotateCcw,
} from "lucide-react";
import { diagnosticsApi } from "../../../api/modules/diagnostics";
import type {
  HealthResponse,
  ErrorEntry,
  SubsystemStatus,
} from "../../../api/modules/diagnostics";

const STATUS_CONFIG: Record<
  string,
  { color: "success" | "warning" | "error"; label: string }
> = {
  healthy: { color: "success", label: "Healthy" },
  degraded: { color: "warning", label: "Degraded" },
  unhealthy: { color: "error", label: "Unhealthy" },
};

const SUB_STATUS_CONFIG: Record<
  string,
  {
    color: "success" | "warning" | "error";
    icon: React.ReactNode;
  }
> = {
  ok: { color: "success", icon: <CheckCircle size={14} /> },
  warning: { color: "warning", icon: <AlertTriangle size={14} /> },
  error: { color: "error", icon: <XCircle size={14} /> },
};

function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

export default function DiagnosticsPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [errors, setErrors] = useState<ErrorEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [restarting, setRestarting] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [healthRes, errorsRes] = await Promise.all([
        diagnosticsApi.getHealth(),
        diagnosticsApi.getErrors(50),
      ]);
      setHealth(healthRes);
      setErrors(errorsRes.errors);
    } catch {
      // silently fail — page will show loading state
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleRestart = () => {
    Modal.confirm({
      title: "Restart AdClaw",
      content:
        "This will restart the application. All active sessions will be interrupted. Are you sure?",
      okText: "Restart",
      okButtonProps: { danger: true },
      onOk: async () => {
        setRestarting(true);
        try {
          const res = await diagnosticsApi.restart();
          if (res.restarted) {
            Modal.success({
              title: "Restarting",
              content: "AdClaw is restarting. The page will refresh shortly.",
            });
            setTimeout(fetchData, 5000);
          } else {
            Modal.error({
              title: "Restart Failed",
              content: res.error || "Unknown error",
            });
          }
        } catch (err: any) {
          Modal.error({
            title: "Restart Failed",
            content: err?.message || "Unknown error",
          });
        } finally {
          setRestarting(false);
        }
      },
    });
  };

  const levelColors: Record<string, string> = {
    ERROR: "red",
    WARNING: "orange",
    CRITICAL: "magenta",
    INFO: "blue",
    DEBUG: "default",
  };

  const columns: ColumnsType<ErrorEntry> = [
    {
      title: "Time",
      dataIndex: "timestamp",
      key: "timestamp",
      width: 180,
      render: (ts: string) => new Date(ts).toLocaleString(),
    },
    {
      title: "Level",
      dataIndex: "level",
      key: "level",
      width: 100,
      render: (level: string) => (
        <Tag color={levelColors[level] || "default"}>{level}</Tag>
      ),
    },
    {
      title: "Message",
      dataIndex: "message",
      key: "message",
      ellipsis: true,
    },
  ];

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: 80 }}>
        <Spin size="large" />
      </div>
    );
  }

  const statusCfg = health
    ? STATUS_CONFIG[health.status] || STATUS_CONFIG.unhealthy
    : STATUS_CONFIG.unhealthy;

  return (
    <div style={{ padding: 24 }}>
      {/* Overall status banner */}
      <Alert
        type={statusCfg.color === "success" ? "success" : statusCfg.color === "warning" ? "warning" : "error"}
        showIcon
        icon={<Heart size={18} />}
        message={
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <span>
              System Status: <strong>{statusCfg.label}</strong>
              {health && (
                <span style={{ marginLeft: 16, color: "#64748b" }}>
                  Uptime: {formatUptime(health.uptime_seconds)}
                </span>
              )}
            </span>
            <Space>
              <Button
                icon={<RefreshCw size={14} />}
                onClick={fetchData}
                size="small"
              >
                Refresh
              </Button>
              <Button
                danger
                icon={<RotateCcw size={14} />}
                onClick={handleRestart}
                loading={restarting}
                size="small"
              >
                Restart
              </Button>
            </Space>
          </div>
        }
        style={{ marginBottom: 24 }}
      />

      {/* Subsystem cards */}
      {health && (
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 16,
            marginBottom: 24,
          }}
        >
          {Object.entries(health.subsystems).map(
            ([name, sub]: [string, SubsystemStatus]) => {
              const cfg = SUB_STATUS_CONFIG[sub.status] || SUB_STATUS_CONFIG.error;
              return (
                <Card
                  key={name}
                  size="small"
                  style={{ minWidth: 200, flex: "1 1 200px", maxWidth: 300 }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      marginBottom: 8,
                    }}
                  >
                    <strong>{name.toUpperCase()}</strong>
                    <Tag
                      color={cfg.color}
                      icon={cfg.icon}
                      style={{ margin: 0, display: "inline-flex", alignItems: "center", gap: 4 }}
                    >
                      {sub.status}
                    </Tag>
                  </div>
                  <div style={{ color: "#475569", fontSize: 13 }}>
                    {typeof sub.detail === "string"
                      ? sub.detail
                      : typeof sub.detail === "object" && sub.detail !== null
                        ? Object.entries(sub.detail).map(([k, v]) => (
                            <span key={k} style={{ marginRight: 12 }}>
                              <strong>{k}:</strong>{" "}
                              {Array.isArray(v) ? v.join(", ") : String(v)}
                            </span>
                          ))
                        : JSON.stringify(sub.detail)}
                  </div>
                  {sub.count != null && (
                    <div style={{ color: "#64748b", fontSize: 12, marginTop: 4 }}>
                      Count: {sub.count}
                    </div>
                  )}
                </Card>
              );
            }
          )}
        </div>
      )}

      {/* Error log table */}
      <Card title="Recent Errors" size="small">
        <Table
          dataSource={[...errors].sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())}
          columns={columns}
          rowKey={(record, index) => `${record.timestamp}-${index}`}
          size="small"
          pagination={{ pageSize: 20, size: "small" }}
          expandable={{
            expandedRowRender: (record: ErrorEntry) => (
              <pre
                style={{
                  margin: 0,
                  padding: 12,
                  background: "#f8fafc",
                  borderRadius: 4,
                  fontSize: 12,
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-all",
                  maxHeight: 400,
                  overflow: "auto",
                }}
              >
                {record.traceback || "No traceback available"}
              </pre>
            ),
            rowExpandable: (record: ErrorEntry) => !!record.traceback,
          }}
        />
      </Card>
    </div>
  );
}
