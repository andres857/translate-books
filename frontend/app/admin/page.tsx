import { redirect } from "next/navigation";

// la lista de libros vive ahora en el inicio ("/"); esta ruta se mantiene para enlaces antiguos
export default function AdminPage() {
  redirect("/");
}
