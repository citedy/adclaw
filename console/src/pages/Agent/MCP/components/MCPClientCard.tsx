import { Card, Button, Modal, Tooltip, Input } from "@agentscope-ai/design";
import { DeleteOutlined } from "@ant-design/icons";
import { Server, Plug } from "lucide-react";
import type { MCPClientInfo } from "../../../../api/types";
import { useTranslation } from "react-i18next";
import { useState } from "react";
import styles from "../index.module.less";

interface MCPClientCardProps {
  client: MCPClientInfo;
  onToggle: (client: MCPClientInfo, e: React.MouseEvent) => void;
  onDelete: (client: MCPClientInfo, e: React.MouseEvent) => void;
  onUpdate: (key: string, updates: any) => Promise<boolean>;
  isHovered: boolean;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}

export function MCPClientCard({
  client,
  onToggle,
  onDelete,
  onUpdate,
  isHovered,
  onMouseEnter,
  onMouseLeave,
}: MCPClientCardProps) {
  const { t } = useTranslation();
  const [jsonModalOpen, setJsonModalOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [editedJson, setEditedJson] = useState("");
  const [editedDescription, setEditedDescription] = useState("");
  const [isEditing, setIsEditing] = useState(false);

  // Determine if MCP client is remote or local based on command
  const isRemote =
    client.transport === "streamable_http" || client.transport === "sse";
  const clientType = isRemote ? "Remote" : "Local";

  const handleToggleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onToggle(client, e);
  };

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setDeleteModalOpen(true);
  };

  const confirmDelete = () => {
    setDeleteModalOpen(false);
    onDelete(client, null as any);
  };

  const handleCardClick = () => {
    const { description, ...rest } = client;
    const jsonStr = JSON.stringify(rest, null, 2);
    setEditedJson(jsonStr);
    setEditedDescription(description || "");
    setIsEditing(false);
    setJsonModalOpen(true);
  };

  const handleSaveJson = async () => {
    try {
      const parsed = JSON.parse(editedJson);
      const { key, ...updates } = parsed;
      updates.description = editedDescription;

      const success = await onUpdate(client.key, updates);
      if (success) {
        setJsonModalOpen(false);
        setIsEditing(false);
      }
    } catch (error) {
      alert("Invalid JSON format");
    }
  };

  const { description: _desc, ...clientWithoutDesc } = client;
  const clientJson = JSON.stringify(clientWithoutDesc, null, 2);

  return (
    <>
      <Card
        hoverable
        onClick={handleCardClick}
        onMouseEnter={onMouseEnter}
        onMouseLeave={onMouseLeave}
        className={`${styles.mcpCard} ${
          client.enabled ? styles.enabledCard : ""
        } ${isHovered ? styles.hover : styles.normal}`}
      >
        <div className={styles.cardHeader}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span className={styles.fileIcon}>
              <Server style={{ color: "#3b82f6", fontSize: 20 }} />
            </span>
            <Tooltip title={client.name}>
              <h3 className={styles.mcpTitle}>{client.name}</h3>
            </Tooltip>
            <span
              className={`${styles.typeBadge} ${
                isRemote ? styles.remote : styles.local
              }`}
            >
              {clientType}
            </span>
          </div>
          <div className={styles.statusContainer}>
            <span
              className={`${styles.statusDot} ${
                client.enabled ? styles.enabled : styles.disabled
              }`}
            />
            <span
              className={`${styles.statusText} ${
                client.enabled ? styles.enabled : styles.disabled
              }`}
            >
              {client.enabled ? t("common.enabled") : t("common.disabled")}
            </span>
          </div>
        </div>

        <div className={styles.description}>
          {client.description || "\u00A0"}
        </div>

        <div className={styles.cardFooter}>
          <Button
            type="link"
            size="small"
            onClick={handleToggleClick}
            className={styles.actionButton}
          >
            {client.enabled ? t("common.disable") : t("common.enable")}
          </Button>

          <Button
            type="text"
            size="small"
            danger
            icon={<DeleteOutlined />}
            className={styles.deleteButton}
            onClick={handleDeleteClick}
            disabled={client.enabled}
          />
        </div>

        {/* Decorative icon */}
        <Plug
          style={{
            position: "absolute",
            bottom: -16,
            right: -16,
            width: 128,
            height: 128,
            opacity: 0.03,
            pointerEvents: "none",
            color: "#06b6d4",
          }}
        />
      </Card>

      <Modal
        title={t("common.confirm")}
        open={deleteModalOpen}
        onOk={confirmDelete}
        onCancel={() => setDeleteModalOpen(false)}
        okText={t("common.confirm")}
        cancelText={t("common.cancel")}
        okButtonProps={{ danger: true }}
      >
        <p>{t("mcp.deleteConfirm")}</p>
      </Modal>

      <Modal
        title={`${client.name} - Configuration`}
        open={jsonModalOpen}
        onCancel={() => setJsonModalOpen(false)}
        footer={
          <div style={{ textAlign: "right" }}>
            <Button
              onClick={() => setJsonModalOpen(false)}
              style={{ marginRight: 8 }}
            >
              {t("common.cancel")}
            </Button>
            {isEditing ? (
              <Button type="primary" onClick={handleSaveJson}>
                {t("common.save")}
              </Button>
            ) : (
              <Button type="primary" onClick={() => setIsEditing(true)}>
                {t("common.edit")}
              </Button>
            )}
          </div>
        }
        width={700}
      >
        <div style={{ marginBottom: 12 }}>
          <label style={{ display: "block", marginBottom: 4, fontWeight: 500 }}>
            Description
          </label>
          <Input.TextArea
            value={editedDescription}
            onChange={(e) => setEditedDescription(e.target.value)}
            disabled={!isEditing}
            rows={2}
            placeholder="Short description of this MCP client..."
          />
        </div>
        {isEditing ? (
          <textarea
            value={editedJson}
            onChange={(e) => setEditedJson(e.target.value)}
            className={styles.editJsonTextArea}
          />
        ) : (
          <pre className={styles.preformattedText}>{clientJson}</pre>
        )}
      </Modal>
    </>
  );
}
