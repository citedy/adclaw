import { Layout, Menu, Button, type MenuProps } from "antd";
import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import api from "../api";
import { request } from "../api/request";
import {
  MessageSquare,
  Radio,
  Zap,
  MessageCircle,
  Wifi,
  UsersRound,
  CalendarClock,
  Activity,
  Sparkles,
  Briefcase,
  Cpu,
  Box,
  Globe,
  Settings,
  Plug,
  PanelLeftClose,
  PanelLeftOpen,
  Wallet,
  ExternalLink,
  HeartPulse,
  Users,
  LayoutDashboard,
} from "lucide-react";

const { Sider } = Layout;

const keyToPath: Record<string, string> = {
  dashboard: "/dashboard",
  chat: "/chat",
  channels: "/channels",
  sessions: "/sessions",
  "cron-jobs": "/cron-jobs",
  heartbeat: "/heartbeat",
  skills: "/skills",
  mcp: "/mcp",
  workspace: "/workspace",
  personas: "/personas",
  models: "/models",
  environments: "/environments",
  "agent-config": "/agent-config",
  diagnostics: "/diagnostics",
};

interface SidebarProps {
  selectedKey: string;
}

export default function Sidebar({ selectedKey }: SidebarProps) {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [collapsed, setCollapsed] = useState(false);
  const [openKeys, setOpenKeys] = useState<string[]>([
    "chat-group",
    "control-group",
    "agent-group",
    "settings-group",
  ]);
  const [version, setVersion] = useState<string>("");
  const [citedyBalance, setCitedyBalance] = useState<{
    configured: boolean;
    credits?: number;
    billing_url?: string;
  } | null>(null);

  useEffect(() => {
    api
      .getVersion()
      .then((res) => setVersion(res?.version ?? ""))
      .catch(() => {});
    // Fetch Citedy status
    request<any>("/citedy/status")
      .then((res) => {
        setCitedyBalance({
          configured: res.configured,
          credits: res.balance?.credits,
          billing_url: res.billing_url,
        });
      })
      .catch(() => {});
  }, []);

  const menuItems: MenuProps["items"] = [
    {
      key: "chat-group",
      label: t("nav.chat"),
      icon: <MessageSquare size={16} />,
      children: [
        {
          key: "dashboard",
          label: "Dashboard",
          icon: <LayoutDashboard size={16} />,
        },
        {
          key: "chat",
          label: t("nav.chat"),
          icon: <MessageCircle size={16} />,
        },
      ],
    },
    {
      key: "control-group",
      label: t("nav.control"),
      icon: <Radio size={16} />,
      children: [
        {
          key: "channels",
          label: t("nav.channels"),
          icon: <Wifi size={16} />,
        },
        {
          key: "sessions",
          label: t("nav.sessions"),
          icon: <UsersRound size={16} />,
        },
        {
          key: "cron-jobs",
          label: t("nav.cronJobs"),
          icon: <CalendarClock size={16} />,
        },
        {
          key: "heartbeat",
          label: t("nav.heartbeat"),
          icon: <Activity size={16} />,
        },
        {
          key: "diagnostics",
          label: "Diagnostics",
          icon: <HeartPulse size={16} />,
        },
      ],
    },
    {
      key: "agent-group",
      label: t("nav.agent"),
      icon: <Zap size={16} />,
      children: [
        {
          key: "workspace",
          label: t("nav.workspace"),
          icon: <Briefcase size={16} />,
        },
        {
          key: "skills",
          label: t("nav.skills"),
          icon: <Sparkles size={16} />,
        },
        {
          key: "mcp",
          label: t("nav.mcp"),
          icon: <Plug size={16} />,
        },
        {
          key: "personas",
          label: t("nav.personas"),
          icon: <Users size={16} />,
        },
        {
          key: "agent-config",
          label: t("nav.agentConfig"),
          icon: <Settings size={16} />,
        },
      ],
    },
    {
      key: "settings-group",
      label: t("nav.settings"),
      icon: <Cpu size={16} />,
      children: [
        {
          key: "models",
          label: t("nav.models"),
          icon: <Box size={16} />,
        },
        {
          key: "environments",
          label: t("nav.environments"),
          icon: <Globe size={16} />,
        },
      ],
    },
  ];

  return (
    <Sider
      collapsed={collapsed}
      onCollapse={(value) => setCollapsed(value)}
      width={260}
      style={{
        overflow: "auto",
        height: "100vh",
      }}
    >
      <div
        style={{
          height: 64,
          display: "flex",
          alignItems: "center",
          padding: "0 16px",
          gap: 12,
        }}
      >
        {!collapsed && (
          <>
            <img
              src="/logo.png"
              alt="AdClaw"
              style={{ height: 22, width: "auto" }}
            />
            {version && (
              <span
                style={{
                  fontSize: 11,
                  color: "#94a3b8",
                  fontWeight: 400,
                  lineHeight: 1,
                }}
              >
                v{version}
              </span>
            )}
          </>
        )}
        <Button
          type="text"
          icon={
            collapsed ? (
              <PanelLeftOpen size={20} />
            ) : (
              <PanelLeftClose size={20} />
            )
          }
          onClick={() => setCollapsed(!collapsed)}
          style={{
            margin: "auto",
            color: "#0f172a",
          }}
        />
      </div>
      <Menu
        mode="inline"
        selectedKeys={[selectedKey]}
        openKeys={openKeys}
        onOpenChange={(keys) => setOpenKeys(keys as string[])}
        onClick={(info: { key: string | number }) => {
          const key = String(info.key);
          const path = keyToPath[key];
          if (path) {
            navigate(path);
          }
        }}
        items={menuItems}
        style={collapsed ? { width: "100%" } : undefined}
      />
      {!collapsed && citedyBalance?.configured && (
        <div
          style={{
            padding: "12px 16px",
            borderTop: "1px solid rgba(226, 232, 240, 0.6)",
            fontSize: 12,
            color: "#475569",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <Wallet size={14} />
              {citedyBalance.credits != null
                ? `${citedyBalance.credits} credits`
                : "Citedy"}
            </span>
            <Button
              type="link"
              size="small"
              style={{ padding: 0, fontSize: 12 }}
              icon={<ExternalLink size={12} />}
              onClick={() =>
                window.open(
                  citedyBalance.billing_url ||
                    "https://www.citedy.com/dashboard/billing",
                  "_blank",
                )
              }
            >
              Top Up
            </Button>
          </div>
        </div>
      )}
    </Sider>
  );
}
