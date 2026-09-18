import React from 'react';
import {
  IconInbox as LayoutDashboard,
  IconFileText as FileText,
  IconSettings as Settings,
  IconHistory as History,
  IconUsers as Users,
  IconMenu as Menu,
  IconRefresh as Sun,
  IconBell as BellRing,
  IconChevronRight as ChevronDown,
  IconMoonStar as MoonStar,
  IconLogOut as LogOut
} from './icons/Icons';

import logoIcon from '../assets/icono-blanco.png';

const icons = { LayoutDashboard, FileText, Settings, History, Users };

/* ================================================================
   SIDEBAR
   ================================================================ */
export const Sidebar = ({ activeTab, setTab, isOpen, collapsed, onClose }) => {
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
        <div className="sidebar-brand-wrap" style={collapsed ? { minWidth: 'auto', padding: '1rem 0' } : { padding: '1.25rem 1rem' }}>
          {collapsed ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' }}>
              <img 
                src={logoIcon} 
                alt="Logo" 
                style={{ width: '30px', height: '30px', objectFit: 'contain', display: 'block' }} 
              />
              <span style={{ fontSize: '0.62rem', fontWeight: 900, color: 'white', textTransform: 'uppercase', letterSpacing: '0.01em', textAlign: 'center' }}>
                Sync-bank
              </span>
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', width: '100%' }}>
              <img 
                src={logoIcon} 
                alt="Logo" 
                style={{ width: '32px', height: '32px', objectFit: 'contain', flexShrink: 0 }} 
              />
              <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
                <h1 className="sidebar-brand-title">SyncBank</h1>
                <p className="sidebar-brand-subtitle">Operación financiera</p>
              </div>
            </div>
          )}
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
      </aside>
    </>
  );
};

/* ================================================================
   TOPBAR
   ================================================================ */
export const Topbar = ({ activeTab, onMenu, menuExpanded, menuLabel, theme, onToggleTheme, userName, onLogout }) => {
  const [menuOpen, setMenuOpen] = React.useState(false);
  const [notificationsOpen, setNotificationsOpen] = React.useState(false);
  const userMenuRef = React.useRef(null);

  React.useEffect(() => {
    if (!menuOpen) return;
    const handleClickOutside = (event) => {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [menuOpen]);

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
          className="icon-btn"
          onClick={onMenu}
          aria-label={menuLabel || 'Abrir o cerrar menú lateral'}
          aria-expanded={menuExpanded}
        >
          <Menu size={18} />
        </button>

        <div>
          <h2 className="topbar-page-title">{tabLabel[activeTab]}</h2>
          <p className="topbar-page-context">Gestión y seguimiento en tiempo real</p>
        </div>
      </div>

      {/* Right – actions + user */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <div className="notification-menu">
          <button
            className="icon-btn"
            type="button"
            aria-label="Notificaciones"
            aria-expanded={notificationsOpen}
            onClick={() => setNotificationsOpen((value) => !value)}
          >
            <BellRing size={17} />
          </button>
          <div className={`notification-popover${notificationsOpen ? ' show' : ''}`}>
            <div className="notification-popover-head">
              <strong>Notificaciones</strong>
              <span>0 pendientes</span>
            </div>
            <div className="notification-empty">
              <BellRing size={22} />
              <p>Todo está al día</p>
              <span>Las novedades de sincronización aparecerán aquí.</span>
            </div>
          </div>
        </div>

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
        <div className="user-menu" ref={userMenuRef}>
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

export const KpiCard = ({ label, value, icon, color = 'brand', loading = false }) => {
  const variant = kpiVariants[color] || kpiVariants.brand;
  const KpiIcon = icon;

  return (
    <article className={`kpi-card ${variant.mod}`}>
      <div className="kpi-body">
        <p className="kpi-label">{label}</p>
        <p className="kpi-value">
          {loading ? <span className="skeleton skeleton-number" aria-label="Cargando" /> : value}
        </p>
      </div>
      <div className="kpi-icon-wrap" aria-hidden="true">
        <KpiIcon size={38} strokeWidth={1.4} />
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
