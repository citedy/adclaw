import { Layout } from "antd";
import { useEffect } from "react";
import { Routes, Route, useLocation, useNavigate } from "react-router-dom";
import Sidebar from "../Sidebar";
import ConsoleCronBubble from "../../components/ConsoleCronBubble";
import Chat from "../../pages/Chat";
import ChannelsPage from "../../pages/Control/Channels";
import SessionsPage from "../../pages/Control/Sessions";
import CronJobsPage from "../../pages/Control/CronJobs";
import HeartbeatPage from "../../pages/Control/Heartbeat";
import AgentConfigPage from "../../pages/Agent/Config";
import SkillsPage from "../../pages/Agent/Skills";
import WorkspacePage from "../../pages/Agent/Workspace";
import MCPPage from "../../pages/Agent/MCP";
import ModelsPage from "../../pages/Settings/Models";
import EnvironmentsPage from "../../pages/Settings/Environments";
import DiagnosticsPage from "../../pages/Control/Diagnostics";
import PersonasPage from "../../pages/Personas";
import DashboardPage from "../../pages/Dashboard";
import WelcomePage from "../../pages/Welcome";

const { Content } = Layout;

const pathToKey: Record<string, string> = {
  "/welcome": "welcome",
  "/dashboard": "dashboard",
  "/chat": "chat",
  "/channels": "channels",
  "/sessions": "sessions",
  "/cron-jobs": "cron-jobs",
  "/heartbeat": "heartbeat",
  "/skills": "skills",
  "/mcp": "mcp",
  "/workspace": "workspace",
  "/personas": "personas",
  "/agents": "agents",
  "/models": "models",
  "/environments": "environments",
  "/agent-config": "agent-config",
  "/diagnostics": "diagnostics",
};

export default function MainLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const currentPath = location.pathname;
  const selectedKey = pathToKey[currentPath] || "chat";

  useEffect(() => {
    if (currentPath === "/") {
      const welcomeSeen = localStorage.getItem("adclaw_welcome_seen");
      navigate(welcomeSeen ? "/chat" : "/welcome", { replace: true });
    }
  }, [currentPath, navigate]);

  const isWelcomePage = currentPath === "/welcome";
  const isChatPage = currentPath === "/chat" || currentPath === "/";

  if (isWelcomePage) {
    return (
      <Routes>
        <Route path="/welcome" element={<WelcomePage />} />
      </Routes>
    );
  }

  return (
    <Layout style={{ height: "100vh" }}>
      <Sidebar selectedKey={selectedKey} />
      <Layout>
        <Content className="page-container">
          <ConsoleCronBubble />
          <div
            className={`page-content${isChatPage ? " page-content-chat" : ""}`}
          >
            <Routes>
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/chat" element={<Chat />} />
              <Route path="/channels" element={<ChannelsPage />} />
              <Route path="/sessions" element={<SessionsPage />} />
              <Route path="/cron-jobs" element={<CronJobsPage />} />
              <Route path="/heartbeat" element={<HeartbeatPage />} />
              <Route path="/skills" element={<SkillsPage />} />
              <Route path="/mcp" element={<MCPPage />} />
              <Route path="/workspace" element={<WorkspacePage />} />
              <Route path="/models" element={<ModelsPage />} />
              <Route path="/environments" element={<EnvironmentsPage />} />
              <Route path="/personas" element={<PersonasPage />} />
              <Route path="/agent-config" element={<AgentConfigPage />} />
              <Route path="/diagnostics" element={<DiagnosticsPage />} />
              <Route path="/" element={<Chat />} />
            </Routes>
          </div>
        </Content>
      </Layout>
    </Layout>
  );
}
