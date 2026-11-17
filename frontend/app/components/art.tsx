/* Iconos de trazo en SVG (sin dependencias ni imágenes externas). Heredan el color del texto. */
import type { SVGProps } from "react";

type P = SVGProps<SVGSVGElement>;

const icon = (p: P) => ({
  width: 20, height: 20, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor",
  strokeWidth: 2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true, ...p,
});

export const IconHome = (p: P) => (
  <svg {...icon(p)}><path d="M3 11 12 4l9 7" /><path d="M5 10v10h5v-6h4v6h5V10" /></svg>
);
export const IconChevron = (p: P) => <svg {...icon(p)}><path d="m6 9 6 6 6-6" /></svg>;
export const IconArrowLeft = (p: P) => <svg {...icon(p)}><path d="M19 12H5M11 6l-6 6 6 6" /></svg>;
export const IconArrowRight = (p: P) => <svg {...icon(p)}><path d="M5 12h14M13 6l6 6-6 6" /></svg>;
export const IconZoom = (p: P) => <svg {...icon(p)}><circle cx="11" cy="11" r="6" /><path d="m20 20-4.5-4.5M11 8v6M8 11h6" /></svg>;
export const IconX = (p: P) => <svg {...icon(p)}><path d="M6 6l12 12M18 6 6 18" /></svg>;
export const IconCheck = (p: P) => <svg {...icon(p)}><path d="m5 12.5 4.5 4.5L19 7.5" /></svg>;
export const IconDownload = (p: P) => <svg {...icon(p)}><path d="M12 4v11M7 10l5 5 5-5M5 20h14" /></svg>;
export const IconUpload = (p: P) => <svg {...icon(p)}><path d="M12 16V5M7 10l5-5 5 5M5 20h14" /></svg>;
export const IconRefresh = (p: P) => <svg {...icon(p)}><path d="M20 11a8 8 0 1 0-2.3 5.7M20 5v6h-6" /></svg>;
export const IconInfo = (p: P) => (
  <svg {...icon(p)}><circle cx="12" cy="12" r="9" /><path d="M12 11v6M12 7.5h.01" /></svg>
);
export const IconLayers = (p: P) => (
  <svg {...icon(p)}><path d="m12 3 9 5-9 5-9-5 9-5Z" /><path d="m3 12.5 9 5 9-5" /><path d="m3 17 9 5 9-5" /></svg>
);
export const IconWand = (p: P) => (
  <svg {...icon(p)}>
    <path d="M4 20 15 9" /><path d="m13.5 7.5 3 3" />
    <path d="M18 2.5v3M16.5 4h3M20.5 9v2M19.5 10h2M9 2.5v2M8 3.5h2" />
  </svg>
);
export const IconWarn = (p: P) => (
  <svg {...icon(p)}><path d="M12 3 2 20h20L12 3Z" /><path d="M12 10v4M12 17h.01" /></svg>
);
export const IconHistory = (p: P) => (
  <svg {...icon(p)}><path d="M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5M12 7v5l3 2" /></svg>
);
export const IconHourglass = (p: P) => (
  <svg {...icon(p)}><path d="M6 3h12M6 21h12M7 3v3.5c0 2 5 3.5 5 5.5s-5 3.5-5 5.5V21M17 3v3.5c0 2-5 3.5-5 5.5s5 3.5 5 5.5V21" /></svg>
);
export const IconSettings = (p: P) => (
  <svg {...icon(p)}>
    <circle cx="12" cy="12" r="3" />
    <path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1" />
  </svg>
);
export const IconBook = (p: P) => (
  <svg {...icon(p)}><path d="M12 6c-2-1.5-4.5-2-8-2v14c3.500 0 6 .5 8 2 2-1.500 4.500-2 8-2V4c-3.500 0-6 .5-8 2Z" /><path d="M12 6v14" /></svg>
);
export const IconColumns = (p: P) => (
  <svg {...icon(p)}><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M12 4v16" /></svg>
);
export const IconPlus = (p: P) => <svg {...icon(p)}><path d="M12 5v14M5 12h14" /></svg>;
export const IconMinus = (p: P) => <svg {...icon(p)}><path d="M5 12h14" /></svg>;
export const IconTrash = (p: P) => (
  <svg {...icon(p)}><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v5M14 11v5" /></svg>
);
export const IconKey = (p: P) => (
  <svg {...icon(p)}><circle cx="8" cy="15" r="4" /><path d="m11 12 9-9M17 6l3 3M14 9l2 2" /></svg>
);
export const IconCloud = (p: P) => (
  <svg {...icon(p)}><path d="M7 18h10a4 4 0 0 0 .5-8A6 6 0 0 0 6 9.5 4.300 4.300 0 0 0 7 18Z" /></svg>
);
export const IconText = (p: P) => (
  <svg {...icon(p)}><path d="M5 5h14M5 10h14M5 15h9M5 20h6" /></svg>
);
export const IconFlask = (p: P) => (
  <svg {...icon(p)}><path d="M9 3h6M10 3v6L4.5 19a1.500 1.500 0 0 0 1.300 2h12.400a1.500 1.500 0 0 0 1.300-2L14 9V3" /><path d="M7 15h10" /></svg>
);
export const IconCopy = (p: P) => (
  <svg {...icon(p)}><rect x="8" y="8" width="12" height="12" rx="2" /><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3" /></svg>
);
export const IconUsers = (p: P) => (
  <svg {...icon(p)}><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20a6.5 6.5 0 0 1 13 0" /><path d="M16 4.5a3.5 3.5 0 0 1 0 7M18 14a6.5 6.5 0 0 1 3.5 6" /></svg>
);
export const IconLogout = (p: P) => (
  <svg {...icon(p)}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><path d="m16 17 5-5-5-5M21 12H9" /></svg>
);
