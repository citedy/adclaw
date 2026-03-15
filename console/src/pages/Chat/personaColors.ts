import type { Persona } from "../../api/types/persona";

export const PERSONA_COLORS: Record<string, string> = {
  coordinator: "#64748b",
  researcher: "#3b82f6",
  "content-writer": "#8b5cf6",
  "seo-specialist": "#06b6d4",
  seo: "#06b6d4",
  "ads-manager": "#f59e0b",
  ads: "#f59e0b",
  "social-media": "#ec4899",
  social: "#ec4899",
};

export function getPersonaColor(persona: Persona): string {
  if (persona.is_coordinator) return PERSONA_COLORS.coordinator;
  const id = persona.id.toLowerCase();
  for (const key of Object.keys(PERSONA_COLORS)) {
    if (id.includes(key)) return PERSONA_COLORS[key];
  }
  return "#64748b";
}
