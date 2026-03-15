export interface PersonaCron {
  enabled: boolean;
  schedule: string;
  prompt: string;
  output: "chat" | "file" | "both";
}

export interface Persona {
  id: string;
  name: string;
  soul_md: string;
  model_provider: string;
  model_name: string;
  skills: string[];
  mcp_clients: string[];
  is_coordinator: boolean;
  cron: PersonaCron | null;
}

export interface PersonaTemplate {
  id: string;
  name: string;
  soul_md: string;
  skills: string[];
  mcp_clients: string[];
}
