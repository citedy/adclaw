import { request } from "../request";

export interface SubsystemStatus {
  status: "ok" | "warning" | "error";
  detail: unknown;
  count?: number;
}

export interface HealthResponse {
  status: "healthy" | "degraded" | "unhealthy";
  uptime_seconds: number;
  subsystems: Record<string, SubsystemStatus>;
}

export interface ErrorEntry {
  timestamp: string;
  level: string;
  message: string;
  traceback: string;
}

export interface ErrorsResponse {
  errors: ErrorEntry[];
  log_path: string;
  total: number;
}

export const diagnosticsApi = {
  getHealth: () => request<HealthResponse>("/diagnostics/health"),
  getErrors: (limit = 50) =>
    request<ErrorsResponse>(`/diagnostics/errors?limit=${limit}`),
  restart: () =>
    request<{ restarted: boolean; error?: string }>("/diagnostics/restart", {
      method: "POST",
    }),
};
