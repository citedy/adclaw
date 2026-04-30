import { Tooltip } from "@agentscope-ai/design";
import type { SkillSecurity } from "../../../../api/types";

const statusIcon = (status: string) => {
  switch (status) {
    case "pass":
      return "\u2705";
    case "fail":
      return "\u274C";
    default:
      return "\u23F3";
  }
};

const scoreColor = (score: number) => {
  if (score >= 80) return "#22c55e";
  if (score >= 50) return "#f59e0b";
  return "#dc2626";
};

interface Props {
  security?: SkillSecurity;
}

export function SecurityBadges({ security }: Props) {
  if (!security) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          fontSize: 12,
          color: "#cbd5e1",
          marginTop: 8,
        }}
      >
        <span>Not scanned</span>
      </div>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        fontSize: 12,
        marginTop: 8,
      }}
    >
      <Tooltip title={`Pattern scan: ${security.pattern_scan}`}>
        <span style={{ cursor: "default" }}>
          {"\uD83D\uDEE1\uFE0F"}
          {statusIcon(security.pattern_scan)}
        </span>
      </Tooltip>
      <Tooltip title={`LLM audit: ${security.llm_audit}`}>
        <span style={{ cursor: "default" }}>
          {"\uD83E\uDD16"}
          {statusIcon(security.llm_audit)}
        </span>
      </Tooltip>
      {security.auto_healed && (
        <Tooltip title="Auto-healed by LLM">
          <span style={{ cursor: "default" }}>{"\uD83D\uDD27"}</span>
        </Tooltip>
      )}
      <span
        style={{
          fontWeight: 600,
          color: scoreColor(security.score),
          marginLeft: "auto",
        }}
      >
        {security.score}/100
      </span>
    </div>
  );
}
