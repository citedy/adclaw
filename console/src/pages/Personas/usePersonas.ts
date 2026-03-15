import { useState, useEffect } from "react";
import { message, Modal } from "@agentscope-ai/design";
import api from "../../api";
import type { Persona, PersonaTemplate } from "../../api/types";

export function usePersonas() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [templates, setTemplates] = useState<PersonaTemplate[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchPersonas = async () => {
    setLoading(true);
    try {
      const data = await api.listPersonas();
      if (data) {
        setPersonas(data);
      }
    } catch (error) {
      console.error("Failed to load personas", error);
      message.error("Failed to load personas");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let mounted = true;

    const load = async () => {
      const [personasData, templatesData] = await Promise.allSettled([
        api.listPersonas(),
        api.listPersonaTemplates(),
      ]);

      if (!mounted) return;

      if (personasData.status === "fulfilled" && personasData.value) {
        setPersonas(personasData.value);
      }
      if (templatesData.status === "fulfilled" && templatesData.value) {
        setTemplates(templatesData.value);
      }
      setLoading(false);
    };

    setLoading(true);
    load();

    return () => {
      mounted = false;
    };
  }, []);

  const createPersona = async (persona: Partial<Persona>) => {
    try {
      await api.createPersona(persona);
      message.success("Persona created successfully");
      await fetchPersonas();
      return true;
    } catch (error) {
      console.error("Failed to create persona", error);
      message.error("Failed to create persona");
      return false;
    }
  };

  const updatePersona = async (id: string, persona: Partial<Persona>) => {
    try {
      await api.updatePersona(id, persona);
      message.success("Persona updated successfully");
      await fetchPersonas();
      return true;
    } catch (error) {
      console.error("Failed to update persona", error);
      message.error("Failed to update persona");
      return false;
    }
  };

  const deletePersona = async (persona: Persona) => {
    const confirmed = await new Promise<boolean>((resolve) => {
      Modal.confirm({
        title: "Confirm Delete",
        content: `Are you sure you want to delete persona "${persona.name}"? This action cannot be undone.`,
        okText: "Delete",
        okType: "danger",
        cancelText: "Cancel",
        onOk: () => resolve(true),
        onCancel: () => resolve(false),
      });
    });

    if (!confirmed) return false;

    try {
      const result = await api.deletePersona(persona.id);
      if (result.deleted) {
        message.success("Persona deleted successfully");
        await fetchPersonas();
        return true;
      } else {
        message.error("Failed to delete persona");
        return false;
      }
    } catch (error) {
      console.error("Failed to delete persona", error);
      message.error("Failed to delete persona");
      return false;
    }
  };

  const createFromTemplate = async (templateId: string) => {
    try {
      await api.createPersonaFromTemplate(templateId);
      message.success("Persona created from template");
      await fetchPersonas();
      return true;
    } catch (error) {
      console.error("Failed to create from template", error);
      message.error("Failed to create from template");
      return false;
    }
  };

  return {
    personas,
    templates,
    loading,
    createPersona,
    updatePersona,
    deletePersona,
    createFromTemplate,
  };
}
