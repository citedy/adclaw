import { Card, Button, Tag } from "@agentscope-ai/design";
import { DeleteOutlined, EditOutlined } from "@ant-design/icons";
import { Brain } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { Persona } from "../../../api/types";
import styles from "../index.module.less";

interface PersonaCardProps {
  persona: Persona;
  isHover: boolean;
  onClick: () => void;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
  onDelete: (e: React.MouseEvent) => void;
}

export function PersonaCard({
  persona,
  isHover,
  onClick,
  onMouseEnter,
  onMouseLeave,
  onDelete,
}: PersonaCardProps) {
  const { t } = useTranslation();

  const soulPreview = persona.soul_md
    ? persona.soul_md.split("\n").slice(0, 2).join("\n")
    : "";

  const modelLabel =
    persona.model_provider && persona.model_name
      ? `${persona.model_provider}/${persona.model_name}`
      : t("personas.defaultModel");

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onDelete(e);
  };

  return (
    <Card
      hoverable
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      className={`${styles.personaCard} ${isHover ? styles.hover : styles.normal}`}
    >
      <div className={styles.cardBody}>
        <div className={styles.cardHeader}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <h3 className={styles.personaTitle}>{persona.name}</h3>
            {persona.is_coordinator && (
              <Tag color="purple">{t("personas.coordinator")}</Tag>
            )}
          </div>
        </div>

        {soulPreview && (
          <div className={styles.soulPreview}>
            <code>{soulPreview}</code>
          </div>
        )}

        <div className={styles.badges}>
          <Tag color="blue">{modelLabel}</Tag>
          <Tag>{persona.skills.length} {t("personas.skills")}</Tag>
          <Tag>{persona.mcp_clients.length} MCP</Tag>
          {persona.cron && (
            <Tag color={persona.cron.enabled ? "green" : "default"}>
              {persona.cron.enabled ? t("personas.cronOn") : t("personas.cronOff")}
            </Tag>
          )}
        </div>

        {persona.cron?.enabled && persona.cron.schedule && (
          <div
            style={{
              marginTop: 8,
              padding: "6px 10px",
              borderRadius: 8,
              background: "rgba(248,250,252,0.8)",
              border: "1px solid rgba(226,232,240,0.4)",
              fontSize: 12,
              color: "var(--citedy-slate-600)",
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <span style={{ fontSize: 14 }}>⏰</span>
            <code style={{ fontSize: 11, color: "var(--citedy-slate-500)" }}>
              {persona.cron.schedule}
            </code>
            {persona.cron.prompt && (
              <span
                style={{
                  marginLeft: 4,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  flex: 1,
                }}
              >
                — {persona.cron.prompt.slice(0, 60)}
                {persona.cron.prompt.length > 60 ? "…" : ""}
              </span>
            )}
          </div>
        )}
      </div>

      <div className={styles.cardFooter}>
        <Button
          type="link"
          size="small"
          icon={<EditOutlined />}
          onClick={(e) => {
            e.stopPropagation();
            onClick();
          }}
          className={styles.actionButton}
        >
          {t("personas.edit")}
        </Button>
        <Button
          type="text"
          size="small"
          danger
          icon={<DeleteOutlined />}
          className={styles.deleteButton}
          onClick={handleDeleteClick}
          aria-label={`Delete persona ${persona.name}`}
        />
      </div>

      {/* Decorative icon */}
      <Brain
        style={{
          position: "absolute",
          bottom: -16,
          right: -16,
          width: 128,
          height: 128,
          opacity: 0.03,
          pointerEvents: "none",
          color: "#8b5cf6",
        }}
      />
    </Card>
  );
}
