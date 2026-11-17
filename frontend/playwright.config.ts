import { defineConfig } from "@playwright/test";

/* Smoke test contra la app desplegada (docker compose). Credenciales por entorno, nunca en el repo:
     E2E_USER_EMAIL / E2E_USER_PASSWORD   cuenta con rol user y contraseña ya cambiada
   Opcional: E2E_BASE_URL (http://localhost:3100) y E2E_CHANNEL (chrome = Chrome del sistema). */
export default defineConfig({
  testDir: "tests/e2e",
  timeout: 120_000,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3100",
    channel: process.env.E2E_CHANNEL ?? "chrome",
    trace: "retain-on-failure",
  },
});
