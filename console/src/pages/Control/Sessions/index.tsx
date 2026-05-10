import { useEffect, useState } from "react";
import {
  Card,
  Form,
  Modal,
  Table,
  message,
  Button,
} from "@agentscope-ai/design";
import { useTranslation } from "react-i18next";
import {
  createColumns,
  FilterBar,
  SessionDrawer,
  type Session,
} from "./components";
import { useSessions } from "./useSessions";
import api from "../../../api";
import styles from "./index.module.less";

function SessionsEmptyState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className={styles.emptyState}>
      <div className={styles.emptyStateCore}>
        <div className={styles.emptyStateIcon} />
        <h3 className={styles.emptyStateTitle}>{title}</h3>
        <p className={styles.emptyStateDescription}>{description}</p>
      </div>
    </div>
  );
}

function SessionsPage() {
  const { t } = useTranslation();
  const {
    sessions,
    loading,
    updateSession,
    deleteSession,
    batchDeleteSessions,
  } = useSessions();
  const [filteredSessions, setFilteredSessions] = useState<Session[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editingSession, setEditingSession] = useState<Session | null>(null);
  const [form] = Form.useForm<Session>();

  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);

  // Filter states
  const [filterUserId, setFilterUserId] = useState<string>("");
  const [filterChannel, setFilterChannel] = useState<string>("");
  const [availableChannels, setAvailableChannels] = useState<string[]>([]);
  const hasSessions = sessions.length > 0;
  const showTable = loading || hasSessions;

  useEffect(() => {
    const fetchChannelTypes = async () => {
      try {
        const types = await api.listChannelTypes();
        setAvailableChannels(types);
      } catch (error) {
        console.error("❌ Failed to load channel types:", error);
      }
    };
    fetchChannelTypes();
  }, []);

  // Filter effect
  useEffect(() => {
    let filtered: Session[] = sessions;

    if (filterUserId) {
      filtered = filtered.filter(
        (session: Session) =>
          session.user_id?.toLowerCase().includes(filterUserId.toLowerCase()),
      );
    }

    if (filterChannel) {
      filtered = filtered.filter(
        (session: Session) => session.channel === filterChannel,
      );
    }

    setFilteredSessions(filtered);
  }, [sessions, filterUserId, filterChannel]);

  const handleEdit = (session: Session) => {
    setEditingSession(session);
    form.setFieldsValue(session as any);
    setDrawerOpen(true);
  };

  const handleDelete = (sessionId: string) => {
    Modal.confirm({
      title: t("sessions.confirmDelete"),
      content: t("sessions.deleteConfirm"),
      okText: t("cronJobs.deleteText"),
      okType: "primary",
      cancelText: t("cronJobs.cancelText"),
      onOk: async () => {
        await deleteSession(sessionId);
      },
    });
  };

  const handleBatchDelete = () => {
    if (selectedRowKeys.length === 0) {
      message.warning(t("sessions.batchDeleteConfirm", { count: 0 }));
      return;
    }

    Modal.confirm({
      title: t("sessions.confirmDelete"),
      content: t("sessions.batchDeleteConfirm", {
        count: selectedRowKeys.length,
      }),
      okText: t("cronJobs.deleteText"),
      okType: "danger",
      cancelText: t("cronJobs.cancelText"),
      onOk: async () => {
        const success = await batchDeleteSessions(selectedRowKeys as string[]);
        if (success) {
          setSelectedRowKeys([]);
        }
      },
    });
  };

  const handleDrawerClose = () => {
    setDrawerOpen(false);
    setEditingSession(null);
  };

  const handleSubmit = async (values: Session) => {
    if (editingSession) {
      const updated = {
        ...editingSession,
        name: values.name,
      };
      const success = await updateSession(editingSession.id, updated);
      if (success) {
        setDrawerOpen(false);
      }
    }
  };

  const columns = createColumns({
    onEdit: handleEdit,
    onDelete: handleDelete,
    t,
  });

  const rowSelection = {
    selectedRowKeys,
    onChange: (newSelectedRowKeys: React.Key[]) => {
      setSelectedRowKeys(newSelectedRowKeys);
    },
  };

  return (
    <div className={styles.sessionsPage}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>{t("sessions.title")}</h1>
          <p className={styles.description}>{t("sessions.description")}</p>
        </div>
      </div>

      <div className={styles.toolbar}>
        <FilterBar
          filterUserId={filterUserId}
          filterChannel={filterChannel}
          uniqueChannels={availableChannels}
          onUserIdChange={setFilterUserId}
          onChannelChange={setFilterChannel}
        />
        <div className={styles.toolbarMeta}>
          <div className={styles.countChip}>
            {t("sessions.totalItems", { count: filteredSessions.length })}
          </div>
          {selectedRowKeys.length > 0 && (
            <Button type="primary" danger onClick={handleBatchDelete}>
              {t("sessions.batchDeleteButton")} ({selectedRowKeys.length})
            </Button>
          )}
        </div>
      </div>

      <Card className={styles.tableCard} bodyStyle={{ padding: 0 }}>
        <div className={styles.surfaceHead}>
          <div className={styles.surfaceTitle}>
            <strong>{t("sessions.sessionListTitle")}</strong>
            <span>{t("sessions.sessionListSubtitle")}</span>
          </div>
        </div>
        {showTable ? (
          <Table
            className={styles.sessionsTable}
            columns={columns}
            dataSource={filteredSessions}
            loading={loading}
            rowKey="id"
            rowSelection={rowSelection}
            rowClassName={(record) =>
              selectedRowKeys.includes(record.id) ? styles.selectedRow : ""
            }
            scroll={{ x: 1500 }}
            pagination={{
              pageSize: 10,
              showTotal: (total) => t("sessions.totalItems", { count: total }),
            }}
          />
        ) : (
          <div className={styles.emptyStatePanel}>
            <SessionsEmptyState
              title={t("sessions.emptyTitle")}
              description={t("sessions.emptyDescription")}
            />
          </div>
        )}
      </Card>

      <SessionDrawer
        open={drawerOpen}
        editingSession={editingSession}
        form={form}
        onClose={handleDrawerClose}
        onSubmit={handleSubmit}
      />
    </div>
  );
}

export default SessionsPage;
