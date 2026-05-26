import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const consoleRoot = join(__dirname, "..");
const repoRoot = join(consoleRoot, "..");
const bad = "-cyc<lic-special-2";
const good = "-cyclic-special-2";

const targets = [
  join(consoleRoot, "node_modules/mermaid/dist/mermaid.js"),
  join(
    consoleRoot,
    "node_modules/mermaid/dist/chunks/mermaid.esm/dagre-QRXUHWQO.mjs",
  ),
  join(
    consoleRoot,
    "node_modules/mermaid/dist/chunks/mermaid.esm/dagre-ZXKKJJHT.mjs",
  ),
];

if (process.argv.includes("--built")) {
  const assetsDir = join(repoRoot, "src/adclaw/console/assets");
  if (existsSync(assetsDir)) {
    for (const fileName of readdirSync(assetsDir)) {
      if (fileName.startsWith("dagre-") && fileName.endsWith(".js")) {
        targets.push(join(assetsDir, fileName));
      }
    }
  }
}

let patched = 0;

for (const target of targets) {
  if (!existsSync(target)) continue;

  const before = readFileSync(target, "utf8");
  if (!before.includes(bad)) continue;

  writeFileSync(target, before.replaceAll(bad, good));
  patched += 1;
}

if (patched > 0) {
  console.log(`[patch-mermaid-dagre] patched ${patched} file(s)`);
}
