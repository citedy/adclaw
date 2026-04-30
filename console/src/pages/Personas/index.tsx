import { useState } from "react";
import { Button, Dropdown } from "@agentscope-ai/design";
import { PlusOutlined, DownOutlined } from "@ant-design/icons";
import type { Persona } from "../../api/types";
import { PersonaCard, PersonaDrawer } from "./components";
import { usePersonas } from "./usePersonas";
import { useTranslation } from "react-i18next";
import styles from "./index.module.less";

function PersonasPage() {
  const { t } = useTranslation();
  const {
    personas,
    templates,
    loading,
    createPersona,
    updatePersona,
    deletePersona,
    createFromTemplate,
  } = usePersonas();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editingPersona, setEditingPersona] = useState<Persona | null>(null);
  const [hoverKey, setHoverKey] = useState<string | null>(null);

  const handleCreate = () => {
    setEditingPersona(null);
    setDrawerOpen(true);
  };

  const handleEdit = (persona: Persona) => {
    setEditingPersona(persona);
    setDrawerOpen(true);
  };

  const handleDelete = async (persona: Persona, e?: React.MouseEvent) => {
    e?.stopPropagation();
    await deletePersona(persona);
  };

  const handleDrawerClose = () => {
    setDrawerOpen(false);
    setEditingPersona(null);
  };

  const handleSubmit = async (values: Partial<Persona>) => {
    let success: boolean;
    if (editingPersona) {
      success = await updatePersona(editingPersona.id, values);
    } else {
      success = await createPersona(values);
    }
    if (success) {
      setDrawerOpen(false);
      setEditingPersona(null);
    }
  };

  const templateMenuItems = templates.map((tmpl) => ({
    key: tmpl.id,
    label: tmpl.name,
  }));

  const handleTemplateClick = async ({ key }: { key: string }) => {
    await createFromTemplate(key);
  };

  return (
    <div className={styles.personasPage}>
      <div className={styles.header}>
        <div className={styles.headerInfo}>
          <h1 className={styles.title}>{t("personas.title")}</h1>
          <p className={styles.description}>{t("personas.description")}</p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {templates.length > 0 && (
            <Dropdown
              menu={{ items: templateMenuItems, onClick: handleTemplateClick }}
            >
              <Button>
                {t("personas.fromTemplate")} <DownOutlined />
              </Button>
            </Dropdown>
          )}
          <Button type="primary" onClick={handleCreate} icon={<PlusOutlined />}>
            {t("personas.createAgent")}
          </Button>
        </div>
      </div>

      {loading ? (
        <div className={styles.loading}>
          <span className={styles.loadingText}>{t("common.loading")}</span>
        </div>
      ) : personas.length === 0 ? (
        <div className={styles.emptyState}>{t("personas.emptyState")}</div>
      ) : (
        <div className={styles.personasGrid}>
          {personas
            .slice()
            .sort((a, b) => {
              if (a.is_coordinator && !b.is_coordinator) return -1;
              if (!a.is_coordinator && b.is_coordinator) return 1;
              return a.name.localeCompare(b.name);
            })
            .map((persona) => (
              <PersonaCard
                key={persona.id}
                persona={persona}
                isHover={hoverKey === persona.id}
                onClick={() => handleEdit(persona)}
                onMouseEnter={() => setHoverKey(persona.id)}
                onMouseLeave={() => setHoverKey(null)}
                onDelete={(e) => handleDelete(persona, e)}
              />
            ))}
        </div>
      )}

      <PersonaDrawer
        open={drawerOpen}
        editingPersona={editingPersona}
        onClose={handleDrawerClose}
        onSubmit={handleSubmit}
      />
    </div>
  );
}

export default PersonasPage;
