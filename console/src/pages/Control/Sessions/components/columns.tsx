import { Button, Tag } from "@agentscope-ai/design";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";
import type { ColumnsType } from "antd/es/table";
import { CHANNEL_COLORS, formatTime, type Session } from "./constants";

interface ColumnHandlers {
  onEdit: (session: Session) => void;
  onDelete: (sessionId: string) => void;
  t: TFunction;
}

export const createColumns = (
  handlers: ColumnHandlers,
): ColumnsType<Session> => {
  const { t } = useTranslation();

  return [
    {
      title: "ID",
      dataIndex: "id",
      key: "id",
      width: 280,
      fixed: "left",
      ellipsis: true,
      render: (id: string) => (
        <span style={{ fontFamily: "monospace", fontSize: 12 }}>{id}</span>
      ),
    },
    {
      title: "Name",
      dataIndex: "name",
      key: "name",
      width: 200,
    },
    {
      title: "SessionID",
      dataIndex: "session_id",
      key: "session_id",
      width: 180,
    },
    {
      title: "UserID",
      dataIndex: "user_id",
      key: "user_id",
      width: 150,
    },
    {
      title: "Channel",
      dataIndex: "channel",
      key: "channel",
      width: 120,
      render: (channel: string) => (
        <Tag color={CHANNEL_COLORS[channel] || "default"}>{channel}</Tag>
      ),
    },
    {
      title: "CreatedAt",
      dataIndex: "created_at",
      key: "created_at",
      width: 180,
      render: (timestamp: string | number | null) => formatTime(timestamp),
      sorter: (a: Session, b: Session) => {
        const timeA = a.created_at ? new Date(a.created_at).getTime() : 0;
        const timeB = b.created_at ? new Date(b.created_at).getTime() : 0;
        return timeA - timeB;
      },
      defaultSortOrder: "descend",
    },
    {
      title: "UpdatedAt",
      dataIndex: "updated_at",
      key: "updated_at",
      width: 180,
      render: (timestamp: string | number | null) => formatTime(timestamp),
      sorter: (a: Session, b: Session) => {
        const timeA = a.updated_at ? new Date(a.updated_at).getTime() : 0;
        const timeB = b.updated_at ? new Date(b.updated_at).getTime() : 0;
        return timeA - timeB;
      },
    },
    {
      title: "Action",
      key: "action",
      width: 180,
      fixed: "right",
      render: (_: unknown, record: Session) => (
        <div style={{ display: "flex", gap: 8 }}>
          <Button
            type="link"
            size="small"
            onClick={() => handlers.onEdit(record)}
          >
            {t("common.edit")}
          </Button>
          <Button
            type="link"
            size="small"
            danger
            onClick={() => handlers.onDelete(record.id)}
          >
            {t("common.delete")}
          </Button>
        </div>
      ),
    },
  ];
};
