import { describe, expect, it } from "vitest";
import type { AuthState } from "@/lib/api";
import { routeFor } from "@/lib/auth";

const session = (role: "admin" | "user", kind: "normal" | "restricted" = "normal"): AuthState => ({
  user: {
    id: 1, email: "a@example.com", name: "A", role, active: true, must_change_password: kind === "restricted",
    temp_password_expires_at: null, created_at: null, updated_at: null,
  },
  csrf_token: "x",
  session: { kind, expires_at: "2099-01-01T00:00:00Z", idle_timeout_minutes: 30, reauth_until: null },
});

describe("routeFor (adónde va cada ruta según la sesión)", () => {
  it("sin sesión: todo al login, con ?next= salvo en la portada", () => {
    expect(routeFor("/", null)).toBe("/login");
    expect(routeFor("/jobs/3", null)).toBe("/login?next=%2Fjobs%2F3");
    expect(routeFor("/login", null)).toBeNull();
  });

  it("sesión restringida: solo el cambio de contraseña", () => {
    expect(routeFor("/", session("user", "restricted"))).toBe("/change-password");
    expect(routeFor("/admin/users", session("admin", "restricted"))).toBe("/change-password");
    expect(routeFor("/change-password", session("user", "restricted"))).toBeNull();
  });

  it("user: fuera de /admin; el login lleva a la portada", () => {
    expect(routeFor("/admin/settings", session("user"))).toBe("/");
    expect(routeFor("/admin/jobs/3", session("user"))).toBe("/");
    expect(routeFor("/jobs/3", session("user"))).toBeNull();
    expect(routeFor("/login", session("user"))).toBe("/");
  });

  it("admin: puede abrir administración", () => {
    expect(routeFor("/admin/users", session("admin"))).toBeNull();
    expect(routeFor("/change-password", session("admin"))).toBeNull();
  });
});
