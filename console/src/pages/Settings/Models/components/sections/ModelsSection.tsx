import { useState, useEffect, useMemo } from "react";
import { SaveOutlined } from "@ant-design/icons";
import { Select, Button, message } from "@agentscope-ai/design";
import type { ModelSlotRequest } from "../../../../../api/types";
import api from "../../../../../api";
import { useTranslation } from "react-i18next";
import { ADCLAW_AI_PROVIDER_ID } from "../../../../../shared/providerMeta";
import styles from "../../index.module.less";
import { OpenRouterRouting } from "./OpenRouterRouting";

interface ModelsSectionProps {
  providers: Array<{
    id: string;
    name: string;
    models?: Array<{ id: string; name: string }>;
    extra_models?: Array<{ id: string; name: string }>;
    current_base_url?: string;
    current_api_key?: string;
    is_custom: boolean;
    is_local?: boolean;
  }>;
  activeModels: {
    active_llm?: {
      provider_id?: string;
      model?: string;
    };
  } | null;
  onSaved: () => void;
}

export function ModelsSection({
  providers,
  activeModels,
  onSaved,
}: ModelsSectionProps) {
  const { t } = useTranslation();
  const [saving, setSaving] = useState(false);
  const [selectedProviderId, setSelectedProviderId] = useState<
    string | undefined
  >(undefined);
  const [selectedModel, setSelectedModel] = useState<string | undefined>(
    undefined,
  );
  const [dirty, setDirty] = useState(false);
  const [adclawAiUsage, setAdclawAiUsage] = useState<{
    messages_limit?: number | null;
    messages_used?: number | null;
    messages_remaining?: number | null;
  } | null>(null);
  const [adclawAiUsageLoading, setAdclawAiUsageLoading] = useState(false);
  const [adclawAiUsageError, setAdclawAiUsageError] = useState<string | null>(
    null,
  );

  const currentSlot = activeModels?.active_llm;

  const eligible = useMemo(
    () =>
      providers.filter((p) => {
        // Ollama: need base_url AND models (to connect to daemon)
        if (p.id === "ollama") {
          return !!p.current_base_url && (p.models?.length ?? 0) > 0;
        }
        // Local providers (llama.cpp, mlx): need models only
        if (p.is_local) {
          return (p.models?.length ?? 0) > 0;
        }
        // Custom providers: need base_url AND models
        if (p.is_custom) {
          return !!p.current_base_url && (p.models?.length ?? 0) > 0;
        }
        // Built-in remote providers (modelscope, dashscope, etc.): need API key
        return !!p.current_api_key;
      }),
    [providers],
  );

  useEffect(() => {
    if (currentSlot) {
      setSelectedProviderId(currentSlot.provider_id || undefined);
      setSelectedModel(currentSlot.model || undefined);
    }
    setDirty(false);
  }, [currentSlot?.provider_id, currentSlot?.model]);

  const chosenProvider = providers.find((p) => p.id === selectedProviderId);
  const modelOptions = chosenProvider?.models ?? [];
  const hasModels = modelOptions.length > 0;

  useEffect(() => {
    if (selectedProviderId !== ADCLAW_AI_PROVIDER_ID) {
      setAdclawAiUsage(null);
      setAdclawAiUsageError(null);
      setAdclawAiUsageLoading(false);
      return;
    }

    let cancelled = false;
    setAdclawAiUsageLoading(true);
    setAdclawAiUsageError(null);

    api
      .getProviderUsage(ADCLAW_AI_PROVIDER_ID)
      .then((usage) => {
        if (cancelled) return;
        setAdclawAiUsage(usage);
      })
      .catch(() => {
        if (cancelled) return;
        setAdclawAiUsage(null);
        setAdclawAiUsageError(t("models.adclawAiUsageUnavailable"));
      })
      .finally(() => {
        if (!cancelled) setAdclawAiUsageLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedProviderId, t]);

  const handleProviderChange = (pid: string) => {
    setSelectedProviderId(pid);
    setSelectedModel(undefined);
    setDirty(true);
  };

  const handleModelChange = (model: string) => {
    setSelectedModel(model);
    setDirty(true);
  };

  const handleSave = async () => {
    if (!selectedProviderId || !selectedModel) return;

    const body: ModelSlotRequest = {
      provider_id: selectedProviderId,
      model: selectedModel,
    };

    setSaving(true);
    try {
      await api.setActiveLlm(body);
      message.success(t("models.llmModelUpdated"));
      setDirty(false);
      onSaved();
    } catch (error) {
      const errMsg =
        error instanceof Error ? error.message : t("models.failedToSave");
      message.error(errMsg);
    } finally {
      setSaving(false);
    }
  };

  const isActive =
    currentSlot &&
    currentSlot.provider_id === selectedProviderId &&
    currentSlot.model === selectedModel;
  const canSave = dirty && !!selectedProviderId && !!selectedModel;
  const adclawAiUsageForDisplay =
    selectedProviderId === ADCLAW_AI_PROVIDER_ID &&
    adclawAiUsage != null &&
    typeof adclawAiUsage?.messages_remaining === "number" &&
    typeof adclawAiUsage?.messages_limit === "number"
      ? adclawAiUsage
      : null;

  return (
    <div className={styles.slotSection}>
      <div className={styles.slotHeader}>
        <h3 className={styles.slotTitle}>{t("models.llmConfiguration")}</h3>
        {currentSlot?.provider_id && currentSlot?.model && (
          <span className={styles.slotCurrent}>
            {t("models.active", {
              provider: currentSlot.provider_id,
              model: currentSlot.model,
            })}
          </span>
        )}
      </div>

      <div className={styles.slotForm}>
        <div className={styles.slotField}>
          <label className={styles.slotLabel}>{t("models.provider")}</label>
          <Select
            style={{ width: "100%" }}
            placeholder={t("models.selectProvider")}
            value={selectedProviderId}
            onChange={handleProviderChange}
            listHeight={300}
            options={eligible.map((p) => ({
              value: p.id,
              label: p.name,
            }))}
          />
        </div>

        <div className={styles.slotField}>
          <label className={styles.slotLabel}>{t("models.model")}</label>
          {selectedProviderId === "openrouter" ? (
            <OpenRouterRouting
              models={modelOptions}
              value={selectedModel}
              onChange={handleModelChange}
            />
          ) : (
            <Select
              style={{ width: "100%" }}
              placeholder={
                hasModels ? t("models.selectModel") : t("models.addModelFirst")
              }
              disabled={!hasModels}
              showSearch
              optionFilterProp="label"
              value={selectedModel}
              onChange={handleModelChange}
              options={modelOptions.map((m) => ({
                value: m.id,
                label: `${m.name} (${m.id})`,
              }))}
            />
          )}
          {selectedProviderId === ADCLAW_AI_PROVIDER_ID && (
            <div className={styles.adclawAiUsageHint}>
              {adclawAiUsageLoading
                ? t("models.adclawAiUsageLoading")
                : adclawAiUsageForDisplay
                ? t("models.adclawAiMessagesRemaining", {
                    remaining: adclawAiUsageForDisplay.messages_remaining,
                    limit: adclawAiUsageForDisplay.messages_limit,
                  })
                : adclawAiUsageError || t("models.adclawAiUsageUnavailable")}
            </div>
          )}
        </div>

        <div
          className={styles.slotField}
          style={{ flex: "0 0 auto", minWidth: "120px" }}
        >
          <label className={styles.slotLabel} style={{ visibility: "hidden" }}>
            {t("models.actions")}
          </label>
          <Button
            type="primary"
            loading={saving}
            disabled={!canSave}
            onClick={handleSave}
            block
            icon={<SaveOutlined />}
          >
            {isActive ? t("models.saved") : t("models.save")}
          </Button>
        </div>
      </div>
    </div>
  );
}
