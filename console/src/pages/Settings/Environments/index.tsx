import { useState, useCallback, useMemo, useEffect } from "react";
import { Button, Modal, message } from "@agentscope-ai/design";
import { useTranslation } from "react-i18next";

import api from "../../../api";
import type { EnvKeyRef } from "../../../api/modules/env";
import { useEnvVars } from "./useEnvVars";
import {
  PageHeader,
  EmptyState,
  AddButton,
  Toolbar,
  EnvRow,
  type Row,
} from "./components";
import styles from "./index.module.less";

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

/** Reindex selected set after a splice at `idx`. */
function shiftIndices(prev: Set<number>, removedIdx: number): Set<number> {
  const next = new Set<number>();
  prev.forEach((i) => {
    if (i < removedIdx) next.add(i);
    else if (i > removedIdx) next.add(i - 1);
  });
  return next;
}

/* ------------------------------------------------------------------ */
/* Main Page                                                           */
/* ------------------------------------------------------------------ */

function EnvironmentsPage() {
  const { t } = useTranslation();
  const { envVars, loading, error, fetchAll } = useEnvVars();
  const [rows, setRows] = useState<Row[] | null>(null);
  const [saving, setSaving] = useState(false);
  const [keyErrors, setKeyErrors] = useState<Record<number, string>>({});
  const [selected, setSelected] = useState<Set<number>>(new Set());

  /* ---- key reference ---- */
  const [keyRefs, setKeyRefs] = useState<EnvKeyRef[]>([]);
  const [bulkText, setBulkText] = useState("");
  const [importing, setImporting] = useState(false);

  useEffect(() => {
    api.listKeyRefs().then(setKeyRefs).catch(() => {});
  }, [envVars]);

  const bulkLineCount = useMemo(() => {
    if (!bulkText.trim()) return 0;
    return bulkText
      .split("\n")
      .filter((l: string) => {
        const s = l.trim();
        return s && !s.startsWith("#") && s.includes("=");
      }).length;
  }, [bulkText]);

  const handleBulkImport = useCallback(async () => {
    if (!bulkText.trim()) return;
    setImporting(true);
    try {
      await api.bulkImport(bulkText, true);
      message.success(`Imported ${bulkLineCount} variables`);
      setBulkText("");
      setRows(null);
      fetchAll();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Import failed";
      message.error(msg);
    } finally {
      setImporting(false);
    }
  }, [bulkText, bulkLineCount, fetchAll]);

  /* ---- derived state ---- */

  const workingRows: Row[] = useMemo(
    () => rows ?? envVars.map((e) => ({ key: e.key, value: e.value })),
    [rows, envVars],
  );

  const dirty = rows !== null;
  const someSelected = selected.size > 0;
  const allSelected =
    workingRows.length > 0 && workingRows.every((_, i) => selected.has(i));

  /* ---- ensure we have a mutable local copy ---- */

  const ensureLocal = useCallback((): Row[] => {
    if (rows) return [...rows];
    return envVars.map((e) => ({ key: e.key, value: e.value }));
  }, [rows, envVars]);

  /* ---- selection ---- */

  const toggleSelect = useCallback((idx: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  }, []);

  const toggleSelectAll = useCallback(() => {
    if (allSelected) {
      setSelected(new Set());
    } else {
      setSelected(new Set(workingRows.map((_, i) => i)));
    }
  }, [allSelected, workingRows]);

  /* ---- row mutations ---- */

  const updateRow = useCallback(
    (idx: number, field: "key" | "value", val: string) => {
      const next = ensureLocal();
      next[idx] = { ...next[idx], [field]: val };
      setRows(next);
      if (field === "key") {
        setKeyErrors((prev) => {
          const copy = { ...prev };
          delete copy[idx];
          return copy;
        });
      }
    },
    [ensureLocal],
  );

  const addRow = useCallback(() => {
    const next = ensureLocal();
    next.push({ key: "", value: "", isNew: true });
    setRows(next);
  }, [ensureLocal]);

  const insertRowAfter = useCallback(
    (idx: number) => {
      const next = ensureLocal();
      next.splice(idx + 1, 0, { key: "", value: "", isNew: true });
      setRows(next);
      setSelected((prev) => {
        const rebuilt = new Set<number>();
        prev.forEach((i) => rebuilt.add(i <= idx ? i : i + 1));
        return rebuilt;
      });
    },
    [ensureLocal],
  );

  const removeRow = useCallback(
    (idx: number) => {
      const row = workingRows[idx];
      const doRemove = () => {
        const next = ensureLocal();
        next.splice(idx, 1);
        setRows(next.length === 0 && envVars.length === 0 ? null : next);
        setSelected((prev) => shiftIndices(prev, idx));
      };

      if (row.isNew) {
        doRemove();
        return;
      }

      Modal.confirm({
        title: t("environments.deleteVariable"),
        content: t("environments.deleteConfirm", { name: row.key }),
        okText: t("common.delete"),
        okButtonProps: { danger: true },
        cancelText: t("common.cancel"),
        onOk: doRemove,
      });
    },
    [workingRows, ensureLocal, envVars.length],
  );

  const removeSelected = useCallback(() => {
    if (selected.size === 0) return;
    const indices = Array.from(selected).sort((a, b) => a - b);
    const names = indices.map((i) => workingRows[i]?.key).filter(Boolean);
    const hasPersistedRows = indices.some((i) => !workingRows[i]?.isNew);

    const doRemove = () => {
      const next = ensureLocal().filter((_, i) => !selected.has(i));
      setRows(next.length === 0 && envVars.length === 0 ? null : next);
      setSelected(new Set());
    };

    if (!hasPersistedRows) {
      doRemove();
      return;
    }

    const label =
      names.length <= 3
        ? names.map((n) => `"${n}"`).join(", ")
        : `${names.length} variables`;

    Modal.confirm({
      title: t("environments.deleteSelected"),
      content: t("environments.deleteSelectedConfirm", { label }),
      okText: t("common.delete"),
      okButtonProps: { danger: true },
      cancelText: t("common.cancel"),
      onOk: doRemove,
    });
  }, [selected, workingRows, ensureLocal, envVars.length]);

  /* ---- validate & save ---- */

  const validate = useCallback((): boolean => {
    const errors: Record<number, string> = {};
    const seen = new Set<string>();
    for (let i = 0; i < workingRows.length; i++) {
      const k = workingRows[i].key.trim();
      if (!k) {
        errors[i] = t("environments.keyRequired");
      } else if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(k)) {
        errors[i] = t("environments.invalidKeyFormat");
      } else if (seen.has(k)) {
        errors[i] = t("environments.duplicateKey");
      }
      seen.add(k);
    }
    setKeyErrors(errors);
    return Object.keys(errors).length === 0;
  }, [workingRows]);

  const handleSave = useCallback(async () => {
    if (!validate()) return;
    const dict: Record<string, string> = {};
    for (const r of workingRows) {
      dict[r.key.trim()] = r.value;
    }
    setSaving(true);
    try {
      await api.saveEnvs(dict);
      message.success(t("environments.saveSuccess"));
      setRows(null);
      setKeyErrors({});
      setSelected(new Set());
      fetchAll();
    } catch (err) {
      const errMsg =
        err instanceof Error ? err.message : t("environments.saveFailed");
      message.error(errMsg);
    } finally {
      setSaving(false);
    }
  }, [validate, workingRows, fetchAll]);

  const handleReset = useCallback(() => {
    setRows(null);
    setKeyErrors({});
    setSelected(new Set());
  }, []);

  /* ---- render ---- */

  return (
    <div className={styles.page}>
      {/* ---- Page header ---- */}
      <PageHeader />

      {/* ---- Content ---- */}
      {loading ? (
        <div className={styles.centerState}>
          <span className={styles.stateText}>{t("environments.loading")}</span>
        </div>
      ) : error ? (
        <div className={styles.centerState}>
          <span className={styles.stateTextError}>{error}</span>
          <Button size="small" onClick={fetchAll} style={{ marginTop: 12 }}>
            {t("environments.retry")}
          </Button>
        </div>
      ) : (
        <div className={styles.tableCard}>
          {/* ---- Toolbar ---- */}
          <Toolbar
            workingRowsLength={workingRows.length}
            allSelected={allSelected}
            someSelected={someSelected}
            selectedSize={selected.size}
            dirty={dirty}
            saving={saving}
            indeterminate={someSelected && !allSelected}
            onToggleSelectAll={toggleSelectAll}
            onRemoveSelected={removeSelected}
            onReset={handleReset}
            onSave={handleSave}
          />

          {/* ---- Rows ---- */}
          <div className={styles.rowList}>
            {workingRows.map((row, idx) => (
              <EnvRow
                key={idx}
                row={row}
                idx={idx}
                checked={selected.has(idx)}
                error={keyErrors[idx]}
                onToggle={toggleSelect}
                onChange={updateRow}
                onInsert={insertRowAfter}
                onRemove={removeRow}
              />
            ))}

            {workingRows.length === 0 && <EmptyState />}
          </div>

          {/* ---- Add button ---- */}
          <AddButton onClick={addRow} />
        </div>
      )}

      {/* ---- Bulk Import ---- */}
      <div className={styles.bulkSection}>
        <div className={styles.refTitle}>Bulk Import</div>
        <div className={styles.refDesc}>
          Paste your .env file contents below. Supports KEY=VALUE, KEY="VALUE",
          export KEY=VALUE, and # comments.
        </div>
        <textarea
          className={styles.bulkTextarea}
          value={bulkText}
          onChange={(e) => setBulkText(e.target.value)}
          placeholder={
            "# Paste your .env file here\nTAVILY_API_KEY=tvly-...\nCITEDY_API_KEY=citedy_...\nGOOGLE_ADS_DEVELOPER_TOKEN=...\nSENDGRID_API_KEY=SG...."
          }
        />
        <div className={styles.bulkActions}>
          <Button
            type="primary"
            size="small"
            loading={importing}
            disabled={bulkLineCount === 0}
            onClick={handleBulkImport}
          >
            Import & Merge
          </Button>
          {bulkLineCount > 0 && (
            <span className={styles.bulkCount}>
              {bulkLineCount} variable{bulkLineCount !== 1 ? "s" : ""} found
            </span>
          )}
        </div>
      </div>

      {/* ---- API Keys Reference ---- */}
      {keyRefs.length > 0 && (
        <div className={styles.refSection}>
          <div className={styles.refTitle}>API Keys Reference</div>
          <div className={styles.refDesc}>
            All API keys used by built-in plugins. Green = configured, orange =
            not set.
          </div>
          <table className={styles.refTable}>
            <thead>
              <tr>
                <th>Status</th>
                <th>Key</th>
                <th>Plugin</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              {keyRefs.map((ref) => (
                <tr key={ref.key}>
                  <td>
                    <span
                      className={`${styles.refBadge} ${
                        ref.configured
                          ? styles.refBadgeOk
                          : styles.refBadgeMissing
                      }`}
                    >
                      {ref.configured ? "OK" : "Missing"}
                    </span>
                  </td>
                  <td>{ref.key}</td>
                  <td style={{ fontFamily: "inherit" }}>{ref.plugin}</td>
                  <td style={{ fontFamily: "inherit", color: "#475569" }}>
                    {ref.description}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default EnvironmentsPage;
