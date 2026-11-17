import type { TranslationSettings } from "@/lib/api";
import { serverFetch } from "@/lib/server/session";
import { SettingsForm } from "./settings-form";

// Server Component: los ajustes llegan con el HTML; el formulario (cliente) solo se encarga de editarlos
export default async function AdminSettingsPage() {
  const settings = await serverFetch<TranslationSettings>("/api/settings");
  return <SettingsForm initial={settings ?? null} />;
}
