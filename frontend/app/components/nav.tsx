"use client";

/* Barra lateral (handoff nav-2): secciones plegables con título pequeño y enlaces de 32 px con icono + texto. */
import { useEffect, useState, type ComponentType, type SVGProps } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { getSettings, methodLabel, SETTINGS_EVENT } from "@/lib/api";
import { IconBook, IconChevron, IconCloud, IconFlask, IconHistory, IconLayers, IconSettings, IconText, IconUpload } from "./art";

type Item = { href: string; label: string; short: string; Icon: ComponentType<SVGProps<SVGSVGElement>>; match: (p: string) => boolean };

const SECTIONS: { id: string; title: string; items: Item[] }[] = [
  {
    id: "translate",
    title: "Traducir",
    items: [
      { href: "/", label: "Subir un libro", short: "Inicio", Icon: IconUpload, match: (p) => p === "/" || p.startsWith("/jobs") },
    ],
  },
  {
    id: "admin",
    title: "Administración",
    items: [
      { href: "/admin", label: "Libros", short: "Libros", Icon: IconLayers,
        match: (p) => p === "/admin" || p.startsWith("/admin/jobs") },
      { href: "/admin/prompts", label: "Prompts", short: "Prompts", Icon: IconText,
        match: (p) => p.startsWith("/admin/prompts") },
      { href: "/admin/playground", label: "Playground", short: "Probar", Icon: IconFlask,
        match: (p) => p.startsWith("/admin/playground") && !p.startsWith("/admin/playground/history") },
      { href: "/admin/playground/history", label: "Historial", short: "Historial", Icon: IconHistory,
        match: (p) => p.startsWith("/admin/playground/history") },
      { href: "/admin/settings", label: "Configuración", short: "Ajustes", Icon: IconSettings,
        match: (p) => p.startsWith("/admin/settings") || p.startsWith("/settings") },
    ],
  },
];

function NavLink({ item, on }: { item: Item; on: boolean }) {
  const { href, label, short, Icon } = item;
  return (
    <Link href={href} className="sidenav-link" data-selected={on} aria-current={on ? "page" : undefined}>
      <span className="sidenav-icon"><Icon width={16} height={16} /></span>
      <span className="sidenav-text">{label}</span>
      <span className="sidenav-short" aria-hidden="true">{short}</span>
    </Link>
  );
}

export function SideNav() {
  const pathname = usePathname() ?? "/";
  const [open, setOpen] = useState<Record<string, boolean>>({ translate: true, admin: true });
  const [method, setMethod] = useState<{ label: string; provider: string } | null>(null);

  useEffect(() => {
    const load = () =>
      getSettings()
        .then((s) => setMethod({ label: methodLabel(s), provider: s.provider }))
        .catch(() => setMethod(null));
    load();
    window.addEventListener(SETTINGS_EVENT, load);
    return () => window.removeEventListener(SETTINGS_EVENT, load);
  }, []);

  return (
    <nav className="sidenav" aria-label="Secciones">
      <Link href="/" className="brand sidenav-brand" aria-label="AstroBooks, inicio">
        <IconBook width={22} height={22} />
        <span>AstroBooks</span>
      </Link>
      <div className="sidenav-body">
        {SECTIONS.map((sec) => {
          const expanded = open[sec.id] !== false;
          return (
            <section key={sec.id} className="sidenav-section" aria-labelledby={`nav-${sec.id}`}>
              <div className="sidenav-heading">
                <button
                  id={`nav-${sec.id}`}
                  type="button"
                  aria-expanded={expanded}
                  aria-controls={`nav-${sec.id}-list`}
                  onClick={() => setOpen((o) => ({ ...o, [sec.id]: !expanded }))}
                >
                  <IconChevron width={12} height={12} className={expanded ? "" : "closed"} />
                  {sec.title}
                </button>
              </div>
              <div id={`nav-${sec.id}-list`} className="sidenav-list" hidden={!expanded}>
                {sec.items.map((item) => <NavLink key={item.href} item={item} on={item.match(pathname)} />)}
              </div>
            </section>
          );
        })}
      </div>
      <Link href="/admin/settings" className="sidenav-foot" title="Método de traducción activo">
        <span className="sidenav-icon"><IconCloud width={16} height={16} /></span>
        <span className="sidenav-text">
          <span className="sidenav-caption">Método activo</span>
          {method?.label ?? "Sin conexión con el servidor"}
        </span>
      </Link>
    </nav>
  );
}
