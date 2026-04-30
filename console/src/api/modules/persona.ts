import { request } from "../request";
import type { Persona, PersonaTemplate } from "../types";

export const personaApi = {
  listPersonas: () => request<Persona[]>("/agents/personas"),

  getPersona: (id: string) =>
    request<Persona>(`/agents/personas/${encodeURIComponent(id)}`),

  createPersona: (persona: Partial<Persona>) =>
    request<Persona>("/agents/personas", {
      method: "POST",
      body: JSON.stringify(persona),
    }),

  updatePersona: (id: string, persona: Partial<Persona>) =>
    request<Persona>(`/agents/personas/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: JSON.stringify(persona),
    }),

  deletePersona: (id: string) =>
    request<{ deleted: boolean }>(
      `/agents/personas/${encodeURIComponent(id)}`,
      {
        method: "DELETE",
      },
    ),

  listPersonaTemplates: () =>
    request<PersonaTemplate[]>("/agents/personas/templates"),

  createPersonaFromTemplate: (templateId: string) =>
    request<Persona>(
      `/agents/personas/templates/${encodeURIComponent(templateId)}`,
      {
        method: "POST",
      },
    ),
};
