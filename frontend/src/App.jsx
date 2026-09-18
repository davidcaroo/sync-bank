import React, { useEffect, useState } from 'react'
import { Sidebar, Topbar } from './components/DashboardBase'
import Dashboard from './pages/Dashboard'
import Facturas from './pages/Facturas'
import Configuracion from './pages/Configuracion'
import Logs from './pages/Logs'
import Contactos from './pages/Contactos'
import { useTheme } from './hooks/useTheme'
import { ToastProvider } from './components/ToastProvider'

export default function App() {
  const [activeTab, setTab] = useState('dashboard')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem('syncbank-sidebar-collapsed') === 'true')
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 1024)
  const userName = 'Auxiliar Contable'
  const { theme, toggleTheme } = useTheme()

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 1024)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  const toggleSidebarCollapsed = () => {
    setSidebarCollapsed((prev) => {
      const next = !prev
      localStorage.setItem('syncbank-sidebar-collapsed', String(next))
      return next
    })
  }

  const toggleSidebar = () => {
    if (isMobile) {
      setSidebarOpen((prev) => !prev)
    } else {
      toggleSidebarCollapsed()
    }
  }

  const sidebarExpanded = isMobile ? sidebarOpen : !sidebarCollapsed
  const sidebarMenuLabel = isMobile
    ? (sidebarOpen ? 'Cerrar menú lateral' : 'Abrir menú lateral')
    : (sidebarCollapsed ? 'Expandir menú lateral' : 'Contraer menú lateral')

  const handleLogout = async () => {
    await fetch('/logout', { method: 'POST' })
    window.location.assign('/login')
  }

  return (
    <ToastProvider>
      <div className="app-layout min-h-screen">
        <Sidebar
          activeTab={activeTab}
          setTab={setTab}
          isOpen={sidebarOpen}
          collapsed={sidebarCollapsed}
          onClose={() => setSidebarOpen(false)}
        />

        <div className="app-main">
          <Topbar
            activeTab={activeTab}
            onMenu={toggleSidebar}
            menuExpanded={sidebarExpanded}
            menuLabel={sidebarMenuLabel}
            theme={theme}
            onToggleTheme={toggleTheme}
            userName={userName}
            onLogout={handleLogout}
          />

          <main className="app-content" id="main-content">
            {activeTab === 'dashboard' && <Dashboard />}
            {activeTab === 'facturas' && <Facturas />}
            {activeTab === 'contactos' && <Contactos />}
            {activeTab === 'configuracion' && <Configuracion />}
            {activeTab === 'logs' && <Logs />}
          </main>
        </div>
      </div>
    </ToastProvider>
  )
}
