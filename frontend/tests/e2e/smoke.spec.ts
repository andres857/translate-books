import { expect, test } from "@playwright/test";

/* Recorrido mínimo de un usuario: login → subir un PDF → progreso → logout.
   El PDF es una página en blanco: no tiene texto, así que no se llama al modelo de traducción (sin coste). */

const email = process.env.E2E_USER_EMAIL;
const password = process.env.E2E_USER_PASSWORD;

// PDF de una página vacía; el backend lo valida con PyMuPDF
function blankPdf(): Buffer {
  const objs = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 400] >>",
  ];
  let body = "%PDF-1.4\n";
  const offsets: number[] = [];
  objs.forEach((o, i) => {
    offsets.push(body.length);
    body += `${i + 1} 0 obj\n${o}\nendobj\n`;
  });
  const xref = body.length;
  body += `xref\n0 ${objs.length + 1}\n0000000000 65535 f \n`;
  body += offsets.map((n) => `${String(n).padStart(10, "0")} 00000 n \n`).join("");
  body += `trailer\n<< /Size ${objs.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(body, "latin1");
}

test.skip(!email || !password, "define E2E_USER_EMAIL y E2E_USER_PASSWORD");

test("login, subir un libro, ver el progreso y cerrar sesión", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel("Correo").fill(email!);
  await page.getByLabel("Contraseña").fill(password!);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("heading", { name: "Libros", level: 1 })).toBeVisible();

  const open = page.getByRole("button", { name: "Subir un libro" });
  if (await open.isVisible()) await open.click();
  await page.locator('input[type="file"]').setInputFiles({ name: "e2e-blanco.pdf", mimeType: "application/pdf", buffer: blankPdf() });
  await page.getByLabel("Confirmo que tengo derechos para traducir y usar este libro.").check();
  await page.getByRole("button", { name: /Traducir libro/ }).click();

  await expect(page).toHaveURL(/\/jobs\/\d+$/, { timeout: 60_000 });
  await expect(page.getByRole("heading", { name: "Etapas" })).toBeVisible();
  await expect(page.getByText("e2e-blanco")).toBeVisible();

  await page.getByRole("button", { name: "Cerrar sesión" }).click();
  await expect(page).toHaveURL(/\/login/);
});
