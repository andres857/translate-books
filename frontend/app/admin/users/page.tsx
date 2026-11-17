import type { UserPage } from "@/lib/api";
import { serverFetch } from "@/lib/server/session";
import { UsersView } from "./users-view";

// Server Component: la lista llega con el HTML; la vista (cliente) se encarga de altas y cambios
export default async function UsersPage() {
  const list = await serverFetch<UserPage>("/api/users?page=1&page_size=200");
  return <UsersView initial={list?.items ?? null} />;
}
