import React from 'react';
import {
  LayoutDashboard,
  FileText,
  Settings,
  History,
  Users,
  Menu,
  MoonStar,
  Sun,
  BellRing,
  PanelLeftClose,
  PanelLeftOpen,
  ChevronDown,
  LogOut,
} from 'lucide-react';

const icons = { LayoutDashboard, FileText, Settings, History, Users };

/* ================================================================
   SIDEBAR
   ================================================================ */
export const Sidebar = ({ activeTab, setTab, isOpen, collapsed, onToggleCollapse, onClose }) => {
  const menuItems = [
    { id: 'dashboard',     label: 'Dashboard',  icon: 'LayoutDashboard' },
    { id: 'facturas',      label: 'Facturas',   icon: 'FileText' },
    { id: 'contactos',     label: 'Contactos',  icon: 'Users' },
    { id: 'configuracion', label: 'Cuentas',    icon: 'Settings' },
    { id: 'logs',          label: 'Auditoría',  icon: 'History' },
  ];

  return (
    <>
      {/* Mobile overlay */}
      <div
        className={`app-overlay${isOpen ? ' show' : ''}`}
        onClick={onClose}
        aria-hidden="true"
      />

      <aside className={`app-sidebar${isOpen ? ' show' : ''}${collapsed ? ' collapsed' : ''}`}>
        {/* Brand */}
        <div className="sidebar-brand-wrap">
          <h1 className="sidebar-brand-title">
            {collapsed ? 'SB' : 'Sync-bank'}
          </h1>
          <p className="sidebar-brand-subtitle">Automation Finance Suite</p>
        </div>

        {/* Nav links */}
        <nav>
          {menuItems.map((item) => {
            const Icon = icons[item.icon];
            return (
              <button
                key={item.id}
                onClick={() => { setTab(item.id); onClose?.(); }}
                className={`sidebar-item${activeTab === item.id ? ' active' : ''}`}
                title={item.label}
                aria-current={activeTab === item.id ? 'page' : undefined}
              >
                <Icon size={18} style={{ flexShrink: 0 }} />
                <span className="sidebar-label">{item.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Collapse toggle – desktop only */}
        <div className="hidden lg:block">
          <button
            className="sidebar-toggle-btn"
            onClick={onToggleCollapse}
            title={collapsed ? 'Expandir sidebar' : 'Contraer sidebar'}
          >
            {collapsed ? <PanelLeftOpen size={15} /> : <PanelLeftClose size={15} />}
            <span className="sidebar-label">{collapsed ? 'Expandir' : 'Contraer'}</span>
          </button>
        </div>
      </aside>
    </>
  );
};

/* ================================================================
   TOPBAR
   ================================================================ */
export const Topbar = ({ activeTab, onMenu, theme, onToggleTheme, userName, onLogout }) => {
  const [menuOpen, setMenuOpen] = React.useState(false);

  const tabLabel = {
    dashboard:     'Dashboard Ejecutivo',
    facturas:      'Control de Facturas',
    contactos:     'Contactos Alegra',
    configuracion: 'Mapa de Cuentas',
    logs:          'Centro de Auditoría',
  };

  const initials = (userName || 'SB')
    .trim()
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join('') || 'SB';

  const handleLogout = async () => {
    setMenuOpen(false);
    await onLogout?.();
  };

  return (
    <header className="app-topbar">
      {/* Left – hamburger + page title */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        <button
          className="icon-btn lg:hidden"
          onClick={onMenu}
          aria-label="Abrir menú lateral"
          style={{ display: 'flex' }}
        >
          <Menu size={18} />
        </button>

        <div className="hidden lg:block topbar-divider" />

        <div>
          <p className="topbar-page-label">Panel</p>
          <h2 className="topbar-page-title">{tabLabel[activeTab]}</h2>
        </div>
      </div>

      {/* Right – actions + user */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <button className="icon-btn" type="button" aria-label="Notificaciones">
          <BellRing size={16} />
        </button>

        <button
          className="icon-btn"
          type="button"
          onClick={onToggleTheme}
          aria-label="Cambiar tema"
        >
          {theme === 'dark' ? <Sun size={16} /> : <MoonStar size={16} />}
        </button>

        <div className="topbar-divider" />

        {/* User dropdown */}
        <div
          className="user-menu"
          onMouseEnter={() => setMenuOpen(true)}
          onMouseLeave={() => setMenuOpen(false)}
        >
          <button
            type="button"
            className="user-chip user-chip-btn"
            aria-expanded={menuOpen}
            aria-haspopup="menu"
            aria-label="Menú de usuario"
            onClick={() => setMenuOpen((p) => !p)}
          >
            <div className="user-avatar">{initials}</div>
            <span className="hidden md:inline" style={{ fontWeight: 700 }}>{userName}</span>
            <ChevronDown
              size={13}
              className={`hidden md:block`}
              style={{ transition: 'transform 180ms', transform: menuOpen ? 'rotate(180deg)' : 'rotate(0deg)' }}
            />
          </button>

          <div
            className={`user-dropdown${menuOpen ? ' show' : ''}`}
            role="menu"
            aria-label="Opciones de usuario"
          >
            <button
              type="button"
              className="user-dropdown-item"
              role="menuitem"
              onClick={handleLogout}
            >
              <LogOut size={14} />
              Cerrar sesión
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};

/* ================================================================
   KPI CARD – SB Admin 2 border-left pattern
   icon goes on the RIGHT, label on top-left
   ================================================================ */
const kpiVariants = {
  'blue-500':   { mod: 'kpi-primary', },
  'green-500':  { mod: 'kpi-success', },
  'yellow-500': { mod: 'kpi-warning', },
  'red-500':    { mod: 'kpi-danger',  },
  'info':       { mod: 'kpi-info',    },
  'brand':      { mod: 'kpi-primary', },
};

export const KpiCard = ({ label, value, icon: Icon, color = 'brand' }) => {
  const variant = kpiVariants[color] || kpiVariants.brand;

  return (
    <article className={`kpi-card ${variant.mod}`}>
      <div className="kpi-body">
        <p className="kpi-label">{label}</p>
        <p className="kpi-value">{value}</p>
      </div>
      <div className="kpi-icon-wrap" aria-hidden="true">
        <Icon size={38} strokeWidth={1.4} />
      </div>
    </article>
  );
};

/* ================================================================
   STATUS BADGE – semantic colours
   ================================================================ */
const badgeClass = {
  pendiente:          'badge-warning',
  pendiente_revision: 'badge-warning',
  procesado:          'badge-success',
  causado:            'badge-success',
  error:              'badge-danger',
  duplicado:          'badge-muted',
};

const badgeLabel = {
  pendiente:          'Pendiente',
  pendiente_revision: 'En revisión',
  procesado:          'Causado',
  causado:            'Causado',
  error:              'Error',
  duplicado:          'Duplicado',
};

export const StatusBadge = ({ status }) => {
  const cls   = badgeClass[status]  || 'badge-muted';
  const label = badgeLabel[status]  || status;

  return (
    <span className={`status-badge ${cls}`} title={status}>
      {label}
    </span>
  );
};
