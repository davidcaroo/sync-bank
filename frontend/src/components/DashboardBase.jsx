import React from 'react';
import { LayoutDashboard, FileText, Settings, History, Menu, MoonStar, Sun, BellRing, PanelLeftClose, PanelLeftOpen, ChevronDown, LogOut } from 'lucide-react';

const icons = {
  LayoutDashboard,
  FileText,
  Settings,
  History
};

export const Sidebar = ({ activeTab, setTab, isOpen, collapsed, onToggleCollapse, onClose }) => {
  const menuItems = [
    { id: 'dashboard', label: 'Dashboard', icon: 'LayoutDashboard' },
    { id: 'facturas', label: 'Facturas', icon: 'FileText' },
    { id: 'configuracion', label: 'Cuentas', icon: 'Settings' },
    { id: 'logs', label: 'Auditoría', icon: 'History' },
  ];

  return (
    <>
      <div className={`app-overlay ${isOpen ? 'show' : ''}`} onClick={onClose} />
      <aside className={`app-sidebar ${isOpen ? 'show' : ''} ${collapsed ? 'collapsed' : ''}`}>
      <div className="p-6 sidebar-brand-wrap">
        <h1 className="text-2xl font-black tracking-tight text-white sidebar-brand-title">
          Sync-bank
        </h1>
        <p className="text-xs text-slate-200/70 mt-1 sidebar-brand-subtitle">Automation Finance Suite</p>
      </div>
      <nav className="flex-1 px-4 space-y-2">
        {menuItems.map((item) => {
          const Icon = icons[item.icon];
          return (
            <button
              key={item.id}
              onClick={() => {
                setTab(item.id)
                onClose?.()
              }}
              className={`w-full sidebar-item flex items-center space-x-3 px-4 py-3 rounded-xl transition-all duration-300 ${
                activeTab === item.id
                  ? 'bg-white/18 text-white shadow-[0_10px_28px_rgba(0,0,0,0.2)]'
                  : 'text-white/75 hover:bg-white/14 hover:text-white'
              }`}
              title={item.label}
            >
              <Icon size={20} />
              <span className="font-medium sidebar-label">{item.label}</span>
            </button>
          );
        })}
      </nav>
      <div className="px-4 pb-4 hidden lg:block">
        <button className="sidebar-toggle-btn" onClick={onToggleCollapse} title={collapsed ? 'Expandir sidebar' : 'Contraer sidebar'}>
          {collapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
          <span className="sidebar-label">{collapsed ? 'Expandir' : 'Contraer'}</span>
        </button>
      </div>
      </aside>
    </>
  );
};

export const Topbar = ({ activeTab, onMenu, theme, onToggleTheme, userName, onLogout }) => {
  const [menuOpen, setMenuOpen] = React.useState(false)

  const tabLabel = {
    dashboard: 'Dashboard Ejecutivo',
    facturas: 'Control de Facturas',
    configuracion: 'Mapa de Cuentas',
    logs: 'Centro de Auditoria',
  }

  const initials = (userName || 'SB')
    .trim()
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('') || 'SB'

  const handleLogout = async () => {
    setMenuOpen(false)
    await onLogout?.()
  }

  return (
    <header className="app-topbar">
      <div className="flex items-center gap-3">
        <button className="icon-btn lg:hidden" onClick={onMenu} aria-label="Abrir menu lateral">
          <Menu size={18} />
        </button>
        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-[var(--muted)]">Panel</p>
          <h1 className="text-xl font-extrabold text-[var(--text)]">{tabLabel[activeTab]}</h1>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button className="icon-btn" type="button" aria-label="Ver notificaciones">
          <BellRing size={16} />
        </button>
        <button className="icon-btn" type="button" onClick={onToggleTheme} aria-label="Cambiar tema claro u oscuro">
          {theme === 'dark' ? <Sun size={16} /> : <MoonStar size={16} />}
        </button>
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
            aria-label="Abrir menu de usuario"
            onClick={() => setMenuOpen((prev) => !prev)}
          >
            <div className="user-avatar">{initials}</div>
            <span className="hidden md:inline">{userName}</span>
            <ChevronDown size={14} className={`hidden md:inline transition-transform ${menuOpen ? 'rotate-180' : ''}`} />
          </button>

          <div className={`user-dropdown ${menuOpen ? 'show' : ''}`} role="menu" aria-label="Opciones de usuario">
            <button type="button" className="user-dropdown-item" role="menuitem" onClick={handleLogout}>
              <LogOut size={14} />
              Salir
            </button>
          </div>
        </div>
      </div>
    </header>
  )
}

export const KpiCard = ({ label, value, icon: Icon, color = 'brand' }) => {
  const colorMap = {
    'blue-500': 'bg-blue-500/15 text-blue-500',
    'green-500': 'bg-green-500/15 text-green-500',
    'yellow-500': 'bg-yellow-500/15 text-yellow-500',
    'red-500': 'bg-red-500/15 text-red-500',
    brand: 'bg-blue-500/15 text-blue-500',
  }

  const iconClasses = colorMap[color] || colorMap.brand

  return (
    <article className="kpi-card">
      <div className={`kpi-icon ${iconClasses}`}>
        <Icon size={24} />
      </div>
      <div>
        <p className="text-sm text-[var(--muted)] font-medium">{label}</p>
        <p className="text-3xl font-black text-[var(--text)]">{value}</p>
      </div>
    </article>
  )
};

export const StatusBadge = ({ status }) => {
  const styles = {
    pendiente: 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20',
    procesado: 'bg-green-500/10 text-green-500 border-green-500/20',
    error: 'bg-red-500/10 text-red-500 border-red-500/20',
    duplicado: 'bg-gray-500/10 text-gray-400 border-gray-500/20',
  };

  return (
    <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${styles[status] || styles.duplicado}`}>
      {status.toUpperCase()}
    </span>
  );
};
