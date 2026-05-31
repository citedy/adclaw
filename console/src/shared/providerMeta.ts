export const ADCLAW_AI_PROVIDER_ID = "adclaw-host-ai";
export const XIAOMI_PROVIDER_ID = "xiaomi-codingplan";
export const XIAOMI_PROVIDER_NAME = "Xiaomi";
export const XIAOMI_TOKEN_PLAN_URL =
  "https://platform.xiaomimimo.com/token-plan";
export const XIAOMI_PARTNER_BADGE = "Partner";

const PROVIDER_PRIORITY: Record<string, number> = {
  [ADCLAW_AI_PROVIDER_ID]: 0,
  [XIAOMI_PROVIDER_ID]: 10,
  "aliyun-intl": 20,
  zai: 30,
  openrouter: 40,
};

export function sortProviders<T extends { id: string; name: string }>(
  providers: T[],
): T[] {
  return [...providers].sort((left, right) => {
    const leftPriority = PROVIDER_PRIORITY[left.id] ?? 999;
    const rightPriority = PROVIDER_PRIORITY[right.id] ?? 999;
    if (leftPriority !== rightPriority) {
      return leftPriority - rightPriority;
    }
    return left.name.localeCompare(right.name);
  });
}
