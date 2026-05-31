import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const read = (path) => readFileSync(resolve(root, path), "utf8");

const providerMeta = read("src/shared/providerMeta.ts");
assert.match(providerMeta, /ADCLAW_AI_PROVIDER_ID\s*=\s*"adclaw-host-ai"/);
assert.match(providerMeta, /\[ADCLAW_AI_PROVIDER_ID\]\s*:\s*0/);

const providerApi = read("src/api/modules/provider.ts");
assert.match(providerApi, /getProviderUsage/);
assert.match(
  providerApi,
  /\/models\/\$\{encodeURIComponent\(providerId\)\}\/usage/,
);

const providerTypes = read("src/api/types/provider.ts");
assert.match(providerTypes, /ProviderUsageInfo/);
assert.match(providerTypes, /messages_remaining/);

const modelsSection = read(
  "src/pages/Settings/Models/components/sections/ModelsSection.tsx",
);
assert.match(modelsSection, /ADCLAW_AI_PROVIDER_ID/);
assert.match(modelsSection, /getProviderUsage/);
assert.match(modelsSection, /models\.adclawAiMessagesRemaining/);
assert.match(modelsSection, /selectedProviderId === ADCLAW_AI_PROVIDER_ID/);

console.log("ok - AdClaw AI Models UI source contract verified");
