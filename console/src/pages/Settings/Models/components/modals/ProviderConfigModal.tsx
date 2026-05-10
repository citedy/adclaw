import { useState, useEffect, useMemo } from "react";
import {
  Form,
  Input,
  Modal,
  message,
  Button,
  Tag,
} from "@agentscope-ai/design";
import { ApiOutlined } from "@ant-design/icons";
import type {
  ActiveModelsInfo,
  ProviderConfigRequest,
  ProviderInfo,
} from "../../../../../api/types";
import api from "../../../../../api";
import { useTranslation } from "react-i18next";
import {
  XIAOMI_PROVIDER_ID,
  XIAOMI_TOKEN_PLAN_URL,
} from "../../../../../shared/providerMeta";
import styles from "../../index.module.less";

interface ProviderConfigModalProps {
  provider: ProviderInfo;
  activeModels: ActiveModelsInfo | null;
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
}

export function ProviderConfigModal({
  provider,
  activeModels,
  open,
  onClose,
  onSaved,
}: ProviderConfigModalProps) {
  const { t } = useTranslation();
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [formDirty, setFormDirty] = useState(false);
  const [form] = Form.useForm<ProviderConfigRequest>();
  const canEditBaseUrl =
    provider.needs_base_url ||
    provider.id === "ollama" ||
    provider.id === XIAOMI_PROVIDER_ID;
  const showXiaomiPlanCta = provider.id === XIAOMI_PROVIDER_ID;

  const apiKeyExtra = useMemo(() => {
    if (provider.current_api_key) {
      return t("models.currentKey", { key: provider.current_api_key });
    }
    if (provider.api_key_prefix) {
      return t("models.startsWith", { prefix: provider.api_key_prefix });
    }
    return t("models.optionalSelfHosted");
  }, [provider.current_api_key, provider.api_key_prefix, t]);

  const apiKeyPlaceholder = useMemo(() => {
    if (provider.current_api_key) {
      return t("models.leaveBlankKeep");
    }
    if (provider.api_key_prefix) {
      return t("models.enterApiKey", { prefix: provider.api_key_prefix });
    }
    return t("models.enterApiKeyOptional");
  }, [provider.current_api_key, provider.api_key_prefix, t]);

  // Sync form when modal opens or provider data changes
  useEffect(() => {
    if (open) {
      form.setFieldsValue({
        api_key: undefined,
        base_url: provider.current_base_url || undefined,
      });
      setFormDirty(false);
    }
  }, [provider, form, open]);

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);

      // Validate connection before saving
      // For local providers, we might skip this or just check if models exist (which the backend does)
      const result = await api.testProviderConnection(provider.id, {
        api_key: values.api_key,
        base_url: values.base_url,
      });

      if (!result.success) {
        message.error(result.message || t("models.testConnectionFailed"));
        return;
      }

      await api.configureProvider(provider.id, values);
      await onSaved();
      setFormDirty(false);
      onClose();
      message.success(t("models.configurationSaved", { name: provider.name }));
    } catch (error) {
      if (error && typeof error === "object" && "errorFields" in error) return;
      const errMsg =
        error instanceof Error ? error.message : t("models.failedToSaveConfig");
      message.error(errMsg);
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    try {
      const values = await form.validateFields();
      const result = await api.testProviderConnection(provider.id, {
        api_key: values.api_key,
        base_url: values.base_url,
      });
      if (result.success) {
        message.success(result.message || t("models.testConnectionSuccess"));
      } else {
        message.warning(result.message || t("models.testConnectionFailed"));
      }
    } catch (error) {
      if (error && typeof error === "object" && "errorFields" in error) return;
      const errMsg =
        error instanceof Error
          ? error.message
          : t("models.testConnectionError");
      message.error(errMsg);
    } finally {
      setTesting(false);
    }
  };

  const isActiveLlmProvider =
    activeModels?.active_llm?.provider_id === provider.id;

  const handleRevoke = () => {
    const confirmContent = isActiveLlmProvider
      ? t("models.revokeConfirmContent", { name: provider.name })
      : t("models.revokeConfirmSimple", { name: provider.name });

    Modal.confirm({
      title: t("models.revokeAuthorization"),
      content: confirmContent,
      okText: t("models.revokeAuthorization"),
      okButtonProps: { danger: true },
      cancelText: t("models.cancel"),
      onOk: async () => {
        try {
          await api.configureProvider(provider.id, { api_key: "" });
          await onSaved();
          onClose();
          if (isActiveLlmProvider) {
            message.success(
              t("models.authorizationRevoked", { name: provider.name }),
            );
          } else {
            message.success(
              t("models.authorizationRevokedSimple", { name: provider.name }),
            );
          }
        } catch (error) {
          const errMsg =
            error instanceof Error ? error.message : t("models.failedToRevoke");
          message.error(errMsg);
        }
      },
    });
  };

  return (
    <Modal
      title={t("models.configureProvider", { name: provider.name })}
      open={open}
      onCancel={onClose}
      footer={
        <div className={styles.modalFooter}>
          <div className={styles.modalFooterLeft}>
            {provider.current_api_key && provider.id !== "ollama" && (
              <Button danger size="small" onClick={handleRevoke}>
                {t("models.revokeAuthorization")}
              </Button>
            )}
            <Button
              size="small"
              icon={<ApiOutlined />}
              onClick={handleTest}
              loading={testing}
            >
              {t("models.testConnection")}
            </Button>
            {showXiaomiPlanCta && (
              <Button
                size="small"
                onClick={() =>
                  window.open(
                    XIAOMI_TOKEN_PLAN_URL,
                    "_blank",
                    "noopener,noreferrer",
                  )
                }
              >
                Get Token Plan 6$/mo
              </Button>
            )}
          </div>
          <div className={styles.modalFooterRight}>
            <Button onClick={onClose}>{t("models.cancel")}</Button>
            <Button
              type="primary"
              loading={saving}
              disabled={!formDirty}
              onClick={handleSubmit}
            >
              {t("models.save")}
            </Button>
          </div>
        </div>
      }
      destroyOnHidden
    >
      {provider.models.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <div
            style={{
              marginBottom: 8,
              fontSize: 14,
              fontWeight: 600,
              color: "#30335a",
            }}
          >
            Available models
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {provider.models.map((model) => (
              <Tag key={model.id} color="blue">
                {model.name}
              </Tag>
            ))}
          </div>
        </div>
      )}
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          base_url: provider.current_base_url || undefined,
        }}
        onValuesChange={() => setFormDirty(true)}
      >
        {/* Base URL */}
        <Form.Item
          name="base_url"
          label="Base URL"
          rules={
            canEditBaseUrl
              ? [
                  ...(provider.needs_base_url
                    ? [
                        {
                          required: true,
                          message: t("models.pleaseEnterBaseURL"),
                        },
                      ]
                    : []),
                  { type: "url", message: t("models.pleaseEnterValidURL") },
                ]
              : []
          }
          extra={
            canEditBaseUrl
              ? provider.id === "azure-openai"
                ? t("models.azureEndpointHint")
                : t("models.openAIEndpoint")
              : undefined
          }
        >
          <Input
            placeholder={
              canEditBaseUrl
                ? provider.id === "azure-openai"
                  ? "https://<resource>.openai.azure.com/openai/v1"
                  : "http://localhost:11434/v1"
                : ""
            }
            disabled={!canEditBaseUrl}
          />
        </Form.Item>

        {/* API Key */}
        <Form.Item
          name="api_key"
          label="API Key"
          rules={[
            {
              validator: (_, value) => {
                if (
                  value &&
                  provider.api_key_prefix &&
                  !value.startsWith(provider.api_key_prefix)
                ) {
                  return Promise.reject(
                    new Error(
                      t("models.apiKeyShouldStart", {
                        prefix: provider.api_key_prefix,
                      }),
                    ),
                  );
                }
                return Promise.resolve();
              },
            },
          ]}
          extra={apiKeyExtra}
        >
          <Input.Password placeholder={apiKeyPlaceholder} />
        </Form.Item>
      </Form>
    </Modal>
  );
}
