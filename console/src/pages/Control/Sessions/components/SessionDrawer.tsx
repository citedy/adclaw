import { Drawer, Form, Input, Button } from "@agentscope-ai/design";
import { useTranslation } from "react-i18next";
import type { FormInstance } from "antd";
import type { Session } from "./constants";

interface SessionDrawerProps {
  open: boolean;
  editingSession: Session | null;
  form: FormInstance<Session>;
  onClose: () => void;
  onSubmit: (values: Session) => void;
}

export function SessionDrawer({
  open,
  editingSession,
  form,
  onClose,
  onSubmit,
}: SessionDrawerProps) {
  const { t } = useTranslation();

  return (
    <Drawer
      width={600}
      placement="right"
      title={t("sessions.editSession")}
      open={open}
      onClose={onClose}
      destroyOnClose
    >
      <Form form={form} layout="vertical" onFinish={onSubmit}>
        <Form.Item
          name="name"
          label="name"
          rules={[{ required: false, message: "Please input name" }]}
        >
          <Input placeholder="Session name" />
        </Form.Item>

        {editingSession && (
          <>
            <Form.Item label="id">
              <Input value={editingSession.id} disabled />
            </Form.Item>

            <Form.Item label="session_id">
              <Input value={editingSession.session_id} disabled />
            </Form.Item>

            <Form.Item label="user_id">
              <Input value={editingSession.user_id} disabled />
            </Form.Item>

            <Form.Item label="channel">
              <Input value={editingSession.channel} disabled />
            </Form.Item>
          </>
        )}

        <Form.Item>
          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              gap: 8,
              marginTop: 16,
            }}
          >
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button type="primary" htmlType="submit">
              {t("common.save")}
            </Button>
          </div>
        </Form.Item>
      </Form>
    </Drawer>
  );
}
