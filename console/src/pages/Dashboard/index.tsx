import { useEffect, useState } from "react";
import { Button } from "@agentscope-ai/design";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { personaApi } from "../../api/modules/persona";
import { request } from "../../api/request";
import type { Persona } from "../../api/types";
import type { CronJobSpecOutput } from "../../api/types";
import styles from "./index.module.less";

interface SessionInfo {
  id: string;
  session_id: string;
  user_id: string;
  channel: string;
  created_at: string | null;
  updated_at: string | null;
  meta?: Record<string, unknown>;
}

const ROLE_COLORS: Record<string, string> = {
  coordinator: "#94a3b8",
  researcher: "#3b82f6",
  "content-writer": "#a855f7",
  seo: "#06b6d4",
  ads: "#f59e0b",
  social: "#ec4899",
};

const DEFAULT_COLOR = "#94a3b8";

function extractRole(soulMd: string): string {
  if (!soulMd) return "";
  const firstLine = soulMd.split("\n")[0] || "";
  // Strip markdown heading markers
  return firstLine.replace(/^#+\s*/, "").trim();
}

function getRoleColor(persona: Persona): string {
  if (persona.is_coordinator) return ROLE_COLORS.coordinator;
  const name = persona.name.toLowerCase();
  const soul = (persona.soul_md || "").toLowerCase();
  for (const [key, color] of Object.entries(ROLE_COLORS)) {
    if (name.includes(key) || soul.includes(key)) {
      return color;
    }
  }
  return DEFAULT_COLOR;
}

function isPersonaActive(persona: Persona, sessions: SessionInfo[]): boolean {
  const fiveMinutesAgo = Date.now() - 5 * 60 * 1000;
  return sessions.some((session) => {
    const matchesPersona =
      session.session_id?.includes(persona.id) ||
      session.session_id?.includes(persona.name) ||
      session.meta?.persona_id === persona.id;
    if (!matchesPersona) return false;
    const updatedAt = session.updated_at
      ? new Date(session.updated_at).getTime()
      : 0;
    return updatedAt > fiveMinutesAgo;
  });
}

function getPersonaCronJobs(
  persona: Persona,
  cronJobs: CronJobSpecOutput[],
): CronJobSpecOutput[] {
  return cronJobs.filter((job) => {
    const sessionId = job.dispatch?.target?.session_id || "";
    const channel = job.dispatch?.channel || "";
    return (
      sessionId.includes(persona.id) ||
      sessionId.includes(persona.name) ||
      channel.includes(persona.id) ||
      channel.includes(persona.name)
    );
  });
}

interface PersonaDashboardCardProps {
  persona: Persona;
  sessions: SessionInfo[];
  cronJobs: CronJobSpecOutput[];
}

function PersonaDashboardCard({
  persona,
  sessions,
  cronJobs,
}: PersonaDashboardCardProps) {
  const navigate = useNavigate();
  const role = extractRole(persona.soul_md);
  const dotColor = getRoleColor(persona);
  const active = isPersonaActive(persona, sessions);
  const personaCrons = getPersonaCronJobs(persona, cronJobs);

  const modelLabel =
    persona.model_provider && persona.model_name
      ? `${persona.model_provider} / ${persona.model_name}`
      : "Default";

  return (
    <div className={styles.card}>
      <div className={styles.cardHeader}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span
              style={{
                display: "inline-block",
                width: 10,
                height: 10,
                borderRadius: "50%",
                background: dotColor,
                flexShrink: 0,
              }}
            />
            <span className={styles.personaName}>{persona.name}</span>
          </div>
          {role && <div className={styles.personaRole}>{role}</div>}
        </div>
        <span
          className={styles.statusBadge}
          style={{
            background: active
              ? "rgba(34,197,94,0.12)"
              : "rgba(148,163,184,0.12)",
            color: active ? "#16a34a" : "#64748b",
          }}
        >
          <span
            style={{
              display: "inline-block",
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: active ? "#22c55e" : "#94a3b8",
            }}
          />
          {active ? "Active" : "Idle"}
        </span>
      </div>

      <div className={styles.statsRow}>
        <span>
          <strong>Model:</strong> {modelLabel}
        </span>
      </div>
      <div className={styles.statsRow}>
        <span>
          <strong>Skills:</strong> {persona.skills.length}
        </span>
        <span>
          <strong>MCP:</strong> {persona.mcp_clients.length}
        </span>
      </div>

      {personaCrons.length > 0 && (
        <div className={styles.cronList}>
          <strong>Scheduled jobs:</strong>
          {personaCrons.map((job) => (
            <div key={job.id} className={styles.cronItem}>
              <span
                style={{
                  display: "inline-block",
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  background: job.enabled ? "#22c55e" : "#94a3b8",
                  flexShrink: 0,
                }}
              />
              <span style={{ fontFamily: "monospace", fontSize: 11 }}>
                {job.schedule?.cron}
              </span>
              {job.text && (
                <span
                  style={{
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    maxWidth: 160,
                  }}
                >
                  — {job.text}
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      <div className={styles.actions}>
        <Button size="small" type="primary" onClick={() => navigate("/chat")}>
          Chat
        </Button>
      </div>
    </div>
  );
}

function DashboardPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [cronJobs, setCronJobs] = useState<CronJobSpecOutput[]>([]);
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAll = async () => {
      setLoading(true);
      try {
        const [personasData, cronData, sessionsData] = await Promise.allSettled(
          [
            personaApi.listPersonas(),
            request<CronJobSpecOutput[]>("/cron/jobs"),
            request<SessionInfo[]>("/chats"),
          ],
        );

        if (personasData.status === "fulfilled") {
          const val = personasData.value;
          const arr = Array.isArray(val) ? val : [];
          setPersonas(
            arr.slice().sort((a, b) => {
              if (a.is_coordinator && !b.is_coordinator) return -1;
              if (!a.is_coordinator && b.is_coordinator) return 1;
              return a.name.localeCompare(b.name);
            }),
          );
        }
        if (cronData.status === "fulfilled") {
          const val = cronData.value;
          setCronJobs(Array.isArray(val) ? val : []);
        }
        if (sessionsData.status === "fulfilled") {
          const val = sessionsData.value;
          setSessions(Array.isArray(val) ? val : []);
        }
      } finally {
        setLoading(false);
      }
    };

    fetchAll();
  }, []);

  return (
    <div className={styles.page}>
      <div>
        <h1 className={styles.title}>Dashboard</h1>
        <p className={styles.description}>Monitor your agent team activity</p>
      </div>

      {loading ? (
        <div
          style={{
            textAlign: "center",
            padding: "60px 0",
            color: "var(--citedy-slate-500)",
            fontSize: 14,
          }}
        >
          {t("common.loading")}
        </div>
      ) : personas.length === 0 ? (
        <div className={styles.emptyStateCard}>
          <div className={styles.emptyEyebrow}>Getting started</div>
          <h2 className={styles.emptyTitle}>Create your first persona</h2>
          <p className={styles.emptyText}>
            Personas are your free virtual office of AI specialists. Start by
            activating one of the 5 built-in personas we already provide, then
            add as many custom personas as your workflow needs.
          </p>
          <div className={styles.emptyActions}>
            <Button type="primary" onClick={() => navigate("/personas")}>
              Open Personas
            </Button>
          </div>
          <p className={styles.emptyHint}>
            Once your first persona is ready, it will appear here for quick
            monitoring and chat access.
          </p>
        </div>
      ) : (
        <div className={styles.grid}>
          {personas.map((persona) => (
            <PersonaDashboardCard
              key={persona.id}
              persona={persona}
              sessions={sessions}
              cronJobs={cronJobs}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default DashboardPage;
