import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiFetch } from "@/lib/api";

describe("apiFetch ante un fallo de red", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("lanza ApiError con estado 0 y el mensaje en español", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const err = await apiFetch("/api/jobs").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(0);
    expect(err.code).toBe("NETWORK");
    expect(err.message).toMatch(/^No hay conexión con el servidor/);
  });

  it("deja pasar una cancelación (AbortError)", async () => {
    const abort = Object.assign(new Error("aborted"), { name: "AbortError" });
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(abort));
    await expect(apiFetch("/api/jobs")).rejects.toBe(abort);
  });

  it("envía el encabezado de la aplicación y la cookie", async () => {
    const f = vi.fn().mockResolvedValue(new Response("{}"));
    vi.stubGlobal("fetch", f);
    await apiFetch("/api/jobs");
    const [, init] = f.mock.calls[0];
    expect(new Headers(init.headers).get("X-Requested-With")).toBe("traductor");
    expect(init.credentials).toBe("same-origin");
  });
});
