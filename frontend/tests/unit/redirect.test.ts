import { describe, expect, it } from "vitest";
import { safeNext } from "@/lib/redirect";

describe("safeNext (destino tras el login)", () => {
  it.each([
    ["/\\evil.example"], // el navegador trata \ como /
    ["//evil.example"],
    ["https://evil.example"],
    ["/\t/evil.example"], // el navegador descarta tabuladores: acabaría en //evil.example
    ["/\n/evil.example"],
    ["javascript:alert(1)"],
    ["evil.example"],
    [""],
    [null],
    [undefined],
  ])("rechaza %j → /", (next) => {
    expect(safeNext(next)).toBe("/");
  });

  it("conserva rutas internas con consulta y ancla", () => {
    expect(safeNext("/jobs/3")).toBe("/jobs/3");
    expect(safeNext("/admin/jobs/3?tab=x")).toBe("/admin/jobs/3?tab=x");
    expect(safeNext("/admin/jobs/3?tab=x#p4")).toBe("/admin/jobs/3?tab=x#p4");
  });

  it("deja codificado lo que ya viene codificado (no es otro origen)", () => {
    expect(safeNext("/%5Cevil.example")).toBe("/%5Cevil.example");
    expect(safeNext("/%2F%2Fevil.example")).toBe("/%2F%2Fevil.example");
  });

  it("no vuelve al login (sin bucle de redirección)", () => {
    expect(safeNext("/login")).toBe("/");
    expect(safeNext("/login?next=/x")).toBe("/");
  });
});
