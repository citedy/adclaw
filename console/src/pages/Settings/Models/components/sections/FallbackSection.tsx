import { useCallback, useEffect, useState } from "react";
import {
  Button,
  Switch,
  InputNumber,
  Select,
  message,
} from "@agentscope-ai/design";
import {
  DeleteOutlined,
  PlusOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import api from "../../../../../api";
import type {
  FallbackConfig,
  FallbackSlot,
  ProviderInfo,
  ModelInfo,
} from "../../../../../api/types";
import styles from "../../index.module.less";

interface Props {
  providers: ProviderInfo[];
}

export function FallbackSection({ providers }: Props) {
  const { t } = useTranslation();
  const [config, setConfig] = useState<FallbackConfig>({
    enabled: false,
    timeout_seconds: 30,
    chain: [],
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  const fetchConfig = useCallback(async () => {
    try {
      const data = await api.getFallbackConfig();
      setConfig(data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (!msg.includes("404")) {
        console.error("Failed to load fallback config:", err);
        message.warning(
          "Could not load fallback configuration. Using defaults.",
        );
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  // Only show providers that have API key configured
  const configuredProviders = providers.filter(
    (p) => !p.is_local && p.current_api_key,
  );

  const getModelsForProvider = (providerId: string): ModelInfo[] => {
    const p = providers.find((pr) => pr.id === providerId);
    return p ? [...p.models, ...p.extra_models] : [];
  };

  const handleToggle = (enabled: boolean) => {
    setConfig((prev) => ({ ...prev, enabled }));
    setDirty(true);
  };

  const handleTimeoutChange = (val: number | null) => {
    if (val && val >= 5 && val <= 300) {
      setConfig((prev) => ({ ...prev, timeout_seconds: val }));
      setDirty(true);
    }
  };

  const handleAddSlot = () => {
    if (configuredProviders.length === 0) return;
    const first = configuredProviders[0];
    const models = getModelsForProvider(first.id);
    setConfig((prev) => ({
      ...prev,
      chain: [
        ...prev.chain,
        {
          provider_id: first.id,
          model: models.length > 0 ? models[0].id : "",
        },
      ],
    }));
    setDirty(true);
  };

  const handleRemoveSlot = (index: number) => {
    setConfig((prev) => ({
      ...prev,
      chain: prev.chain.filter((_, i) => i !== index),
    }));
    setDirty(true);
  };

  const handleSlotChange = (
    index: number,
    field: keyof FallbackSlot,
    value: string,
  ) => {
    setConfig((prev) => {
      const chain = [...prev.chain];
      chain[index] = { ...chain[index], [field]: value };
      // Reset model when provider changes
      if (field === "provider_id") {
        const models = getModelsForProvider(value);
        chain[index].model = models.length > 0 ? models[0].id : "";
      }
      return { ...prev, chain };
    });
    setDirty(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const data = await api.setFallbackConfig(config);
      setConfig(data);
      setDirty(false);
      message.success(t("models.fallback.saved", "Fallback config saved"));
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Failed to save fallback config";
      message.error(msg);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return null;

  return (
    <div className={styles.slotSection} style={{ marginTop: 24 }}>
      <div className={styles.slotHeader}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <ThunderboltOutlined style={{ fontSize: 18 }} />
          <span className={styles.slotTitle}>
            {t("models.fallback.title", "Auto-Fallback")}
          </span>
        </div>
        <Switch
          checked={config.enabled}
          onChange={handleToggle}
          checkedChildren="ON"
          unCheckedChildren="OFF"
        />
      </div>

      {config.enabled && (
        <>
          <div style={{ marginBottom: 20 }}>
            <span
              className={styles.slotLabel}
              style={{ marginBottom: 8, display: "block" }}
            >
              {t("models.fallback.timeout", "LLM Timeout (seconds)")}
            </span>
            <InputNumber
              min={5}
              max={300}
              value={config.timeout_seconds}
              onChange={handleTimeoutChange}
              style={{ width: 120 }}
            />
            <span
              style={{
                marginLeft: 8,
                fontSize: 12,
                color: "var(--citedy-slate-400)",
              }}
            >
              {t(
                "models.fallback.timeoutHint",
                "If primary model doesn't respond within this time, try next in chain",
              )}
            </span>
          </div>

          <div style={{ marginBottom: 16 }}>
            <span
              className={styles.slotLabel}
              style={{ marginBottom: 12, display: "block" }}
            >
              {t("models.fallback.chain", "Fallback Chain")}
            </span>

            {config.chain.map((slot, index) => {
              const models = getModelsForProvider(slot.provider_id);
              return (
                <div
                  key={index}
                  style={{
                    display: "flex",
                    gap: 12,
                    alignItems: "center",
                    marginBottom: 10,
                    padding: "8px 12px",
                    background: "var(--citedy-slate-50)",
                    borderRadius: 8,
                    border: "1px solid rgba(226, 232, 240, 0.4)",
                  }}
                >
                  <span
                    style={{
                      fontSize: 12,
                      color: "var(--citedy-slate-400)",
                      fontWeight: 600,
                      minWidth: 20,
                    }}
                  >
                    #{index + 1}
                  </span>
                  <Select
                    value={slot.provider_id}
                    onChange={(val: string) =>
                      handleSlotChange(index, "provider_id", val)
                    }
                    style={{ flex: 1, minWidth: 160 }}
                    options={configuredProviders.map((p) => ({
                      label: p.name,
                      value: p.id,
                    }))}
                  />
                  <Select
                    value={slot.model}
                    onChange={(val: string) =>
                      handleSlotChange(index, "model", val)
                    }
                    style={{ flex: 2, minWidth: 200 }}
                    options={models.map((m) => ({
                      label: m.name || m.id,
                      value: m.id,
                    }))}
                  />
                  <Button
                    type="text"
                    danger
                    icon={<DeleteOutlined />}
                    onClick={() => handleRemoveSlot(index)}
                  />
                </div>
              );
            })}

            <Button
              type="dashed"
              icon={<PlusOutlined />}
              onClick={handleAddSlot}
              disabled={configuredProviders.length === 0}
              style={{ marginTop: 4 }}
              block
            >
              {t("models.fallback.addSlot", "Add fallback model")}
            </Button>
          </div>

          {dirty && (
            <div className={styles.slotActions}>
              <div style={{ display: "flex", gap: 8 }}>
                <Button
                  onClick={() => {
                    fetchConfig();
                    setDirty(false);
                  }}
                >
                  {t("common.cancel", "Cancel")}
                </Button>
                <Button type="primary" loading={saving} onClick={handleSave}>
                  {t("common.save", "Save")}
                </Button>
              </div>
            </div>
          )}
        </>
      )}

      {!config.enabled && (
        <p
          style={{
            color: "var(--citedy-slate-400)",
            fontSize: 13,
            margin: 0,
          }}
        >
          {t(
            "models.fallback.disabledHint",
            "When enabled, if the primary model fails (timeout, rate limit, auth error), AdClaw will automatically try fallback models from the chain.",
          )}
        </p>
      )}
    </div>
  );
}
