import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

// pruebas unitarias de funciones puras (lib/); el smoke test de navegador va con Playwright (tests/e2e)
export default defineConfig({
  resolve: { alias: { "@": fileURLToPath(new URL("./", import.meta.url)) } },
  test: { include: ["tests/unit/**/*.test.ts"], environment: "node" },
});
