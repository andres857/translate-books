/* Login y cuentas. */
import { apiFetch, jsonBody, parse } from "./http";

export type Role = "admin" | "user";

export interface AuthUser {
  id: number;
  email: string;
  name: string;
  role: Role;
  active: boolean;
  must_change_password: boolean;
  temp_password_expires_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface AuthState {
  user: AuthUser;
  csrf_token: string;
  session: {
    kind: "normal" | "restricted"; // restricted: solo puede cambiar la contraseña temporal
    expires_at: string;
    idle_timeout_minutes: number;
    reauth_until: string | null;
  };
}


/** Sesión actual, o null si no hay (sin avisar a AUTH_EVENT: es la propia consulta del proveedor). */
export async function getMe(): Promise<AuthState | null> {
  const res = await apiFetch("/api/auth/me", { cache: "no-store" });
  if (res.status === 401) return null;
  return parse(res);
}

export async function login(email: string, password: string): Promise<AuthState> {
  return parse(await apiFetch("/api/auth/login", jsonBody("POST", { email, password })));
}

export async function logout(): Promise<void> {
  await parse(await apiFetch("/api/auth/logout", { method: "POST" }));
}

export async function changePassword(current_password: string, new_password: string): Promise<AuthState> {
  return parse(await apiFetch("/api/auth/change-password", jsonBody("POST", { current_password, new_password })));
}

export async function reauthenticate(password: string): Promise<AuthState> {
  return parse(await apiFetch("/api/auth/reauthenticate", jsonBody("POST", { password })));
}

export interface UserPage { items: AuthUser[]; total: number; page: number; page_size: number }
export interface TempPassword { user: AuthUser; temporary_password: string }

export async function listUsers(page = 1, pageSize = 50): Promise<UserPage> {
  return parse(await apiFetch(`/api/users?page=${page}&page_size=${pageSize}`, { cache: "no-store" }));
}

export async function createUser(body: { email: string; name: string; role: Role }): Promise<TempPassword> {
  return parse(await apiFetch("/api/users", jsonBody("POST", body)));
}

export async function updateUser(id: number, patch: { name?: string; role?: Role; active?: boolean }): Promise<AuthUser> {
  return parse(await apiFetch(`/api/users/${id}`, jsonBody("PATCH", patch)));
}

export async function resetUserPassword(id: number): Promise<TempPassword> {
  return parse(await apiFetch(`/api/users/${id}/reset-password`, { method: "POST" }));
}
