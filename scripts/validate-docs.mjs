import { readFile, readdir } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import SwaggerParser from "@apidevtools/swagger-parser";
import { compile } from "@mdx-js/mdx";
const root = fileURLToPath(new URL("../", import.meta.url));
await SwaggerParser.validate(resolve(root, "openapi/reclip-v1.json"));
let count = 0;
async function check(dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    if (entry.name.startsWith(".") || entry.name === "node_modules") continue;
    const path = resolve(dir, entry.name);
    if (entry.isDirectory()) await check(path);
    else if (path.endsWith(".mdx")) {
      await compile(await readFile(path, "utf8"));
      count++;
    }
  }
}
await check(root);
console.log(`OpenAPI valid; compiled ${count} MDX pages.`);
