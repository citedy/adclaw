export const XIAOMI_PROVIDER_ID = "xiaomi-codingplan";
export const XIAOMI_PROVIDER_NAME = "Xiaomi MiMo Token Plan";
export const XIAOMI_TOKEN_PLAN_URL =
  "https://platform.xiaomimimo.com/token-plan";
export const XIAOMI_PARTNER_BADGE = "Partner";

const PROVIDER_PRIORITY: Record<string, number> = {
  [XIAOMI_PROVIDER_ID]: 0,
  "aliyun-intl": 10,
  zai: 20,
  openrouter: 30,
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
