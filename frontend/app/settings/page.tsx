import { redirect } from "next/navigation";

// La configuración vive ahora en Administración › Configuración
export default function SettingsRedirect() {
  redirect("/admin/settings");
}
