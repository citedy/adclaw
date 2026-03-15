import { request } from "../request";
import type { EnvVar } from "../types";

export interface EnvKeyRef {
  key: string;
  plugin: string;
  description: string;
  configured: boolean;
}

export const envApi = {
  listEnvs: () => request<EnvVar[]>("/envs"),

  /** Batch save – full replacement of all env vars. */
  saveEnvs: (envs: Record<string, string>) =>
    request<EnvVar[]>("/envs", {
      method: "PUT",
      body: JSON.stringify(envs),
    }),

  deleteEnv: (key: string) =>
    request<EnvVar[]>(`/envs/${encodeURIComponent(key)}`, {
      method: "DELETE",
    }),

  /** List all known API keys with plugin info and configured status. */
  listKeyRefs: () => request<EnvKeyRef[]>("/envs/keys"),

  /** Bulk import from .env text. */
  bulkImport: (text: string, merge = true) =>
    request<EnvVar[]>("/envs/bulk-import", {
      method: "POST",
      body: JSON.stringify({ text, merge }),
    }),
};
