// src/components/icons/Icons.jsx
// Íconos SVG inline — línea visual unificada Sync-bank

const Icon = ({ size = 20, color = 'currentColor', style = {}, ...props }) => ({
  width: size, height: size, stroke: color,
  fill: 'none', strokeWidth: 1.8,
  strokeLinecap: 'round', strokeLinejoin: 'round',
  style, ...props
})

// ── Estados y feedback ────────────────────────────────
export const IconLoading = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
  </svg>
)

export const IconClock = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <circle cx="12" cy="12" r="10"/>
    <path d="M12 6v6l4 2"/>
  </svg>
)

export const IconCheck = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <path d="M20 6L9 17l-5-5"/>
  </svg>
)

export const IconCheckCircle = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
    <path d="M22 4L12 14.01l-3-3"/>
  </svg>
)

export const IconAlertCircle = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <circle cx="12" cy="12" r="10"/>
    <line x1="12" y1="8" x2="12" y2="12"/>
    <line x1="12" y1="16" x2="12.01" y2="16"/>
  </svg>
)

export const IconXCircle = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <circle cx="12" cy="12" r="10"/>
    <path d="M15 9l-6 6M9 9l6 6"/>
  </svg>
)

export const IconX = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <path d="M18 6L6 18M6 6l12 12"/>
  </svg>
)

// ── Archivos y carga ──────────────────────────────────
export const IconUpload = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
    <polyline points="17 8 12 3 7 8"/>
    <line x1="12" y1="3" x2="12" y2="15"/>
  </svg>
)

export const IconFolder = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
  </svg>
)

export const IconFile = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
    <polyline points="14 2 14 8 20 8"/>
  </svg>
)

export const IconFileText = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
    <polyline points="14 2 14 8 20 8"/>
    <line x1="16" y1="13" x2="8" y2="13"/>
    <line x1="16" y1="17" x2="8" y2="17"/>
    <polyline points="10 9 9 9 8 9"/>
  </svg>
)

export const IconArchive = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <polyline points="21 8 21 21 3 21 3 8"/>
    <rect x="1" y="3" width="22" height="5"/>
    <line x1="10" y1="12" x2="14" y2="12"/>
  </svg>
)

// ── Navegación y UI ───────────────────────────────────
export const IconSearch = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <circle cx="11" cy="11" r="8"/>
    <path d="M21 21l-4.35-4.35"/>
  </svg>
)

export const IconFilter = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
  </svg>
)

export const IconRefresh = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <polyline points="23 4 23 10 17 10"/>
    <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
  </svg>
)

export const IconHistory = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <path d="M3 3v5h5"/>
    <path d="M3.05 13a9 9 0 1 0 3-6.7L3 8"/>
    <path d="M12 7v5l3 2"/>
  </svg>
)

export const IconMoonStar = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <path d="M21 12.79A9 9 0 1 1 11.21 3a7 7 0 0 0 9.79 9.79z"/>
    <path d="M18.5 4.5l.5 1.5 1.5.5-1.5.5-.5 1.5-.5-1.5-1.5-.5 1.5-.5z"/>
  </svg>
)

export const IconChevronLeft = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <polyline points="15 18 9 12 15 6"/>
  </svg>
)

export const IconChevronRight = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <polyline points="9 18 15 12 9 6"/>
  </svg>
)

export const IconPlus = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <line x1="12" y1="5" x2="12" y2="19"/>
    <line x1="5" y1="12" x2="19" y2="12"/>
  </svg>
)

export const IconEdit = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
  </svg>
)

export const IconTrash = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <polyline points="3 6 5 6 21 6"/>
    <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
    <path d="M10 11v6M14 11v6"/>
    <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
  </svg>
)

export const IconSave = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>
    <polyline points="17 21 17 13 7 13 7 21"/>
    <polyline points="7 3 7 8 15 8"/>
  </svg>
)

// ── Dashboard / Negocio ───────────────────────────────
export const IconInbox = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/>
    <path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>
  </svg>
)

export const IconFileCheck = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
    <polyline points="14 2 14 8 20 8"/>
    <path d="M9 15l2 2 4-4"/>
  </svg>
)

export const IconUsers = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
    <circle cx="9" cy="7" r="4"/>
    <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
    <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
  </svg>
)

export const IconUserCheck = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
    <circle cx="8.5" cy="7" r="4"/>
    <path d="M17 11l2 2 4-4"/>
  </svg>
)

export const IconUserMinus = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
    <circle cx="8.5" cy="7" r="4"/>
    <path d="M16 11h6"/>
  </svg>
)

export const IconDollarSign = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <line x1="12" y1="1" x2="12" y2="23"/>
    <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
  </svg>
)

export const IconBell = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
    <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
  </svg>
)

export const IconSettings = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <circle cx="12" cy="12" r="3"/>
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
  </svg>
)

export const IconLogOut = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
    <polyline points="16 17 21 12 16 7"/>
    <line x1="21" y1="12" x2="9" y2="12"/>
  </svg>
)

export const IconMap = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/>
    <line x1="8" y1="2" x2="8" y2="18"/>
    <line x1="16" y1="6" x2="16" y2="22"/>
  </svg>
)

export const IconActivity = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
  </svg>
)

export const IconCopy = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
  </svg>
)

export const IconEye = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
    <circle cx="12" cy="12" r="3"/>
  </svg>
)

export const IconBrain = ({ size, color, style }) => (
  <svg {...Icon({ size, color, style })} viewBox="0 0 24 24">
    <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.46 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-1.14"/>
    <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.46 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-1.14"/>
  </svg>
)
