import React, { useEffect, useState } from 'react'
import { Sidebar, Topbar } from './components/DashboardBase'
import Dashboard from './pages/Dashboard'
import Facturas from './pages/Facturas'
import Configuracion from './pages/Configuracion'
import Logs from './pages/Logs'
import Contactos from './pages/Contactos'
import { useTheme } from './hooks/useTheme'
import { ToastProvider } from './components/ToastProvider'
import { getSupabaseUserName, supabase } from './lib/supabase'

export default function App() {
  const [activeTab, setTab] = useState('dashboard')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem('syncbank-sidebar-collapsed') === 'true')
  const [userName, setUserName] = useState('Auxiliar Contable')
  const { theme, toggleTheme } = useTheme()

  useEffect(() => {
    let mounted = true

    const loadUserName = async () => {
      const resolvedName = await getSupabaseUserName()
      if (mounted) {
        setUserName(resolvedName)
      }
    }

    loadUserName()

    return () => {
      mounted = false
    }
  }, [])

  const toggleSidebarCollapsed = () => {
    setSidebarCollapsed((prev) => {
      const next = !prev
      localStorage.setItem('syncbank-sidebar-collapsed', String(next))
      return next
    })
  }

  const handleLogout = async () => {
    if (supabase) {
      await supabase.auth.signOut()
    }
    setTab('dashboard')
  }

  return (
    <ToastProvider>
      <div className="app-layout min-h-screen">
        <Sidebar
          activeTab={activeTab}
          setTab={setTab}
          isOpen={sidebarOpen}
          collapsed={sidebarCollapsed}
          onToggleCollapse={toggleSidebarCollapsed}
          onClose={() => setSidebarOpen(false)}
        />

        <div className="app-main">
          <Topbar
            activeTab={activeTab}
            onMenu={() => setSidebarOpen(true)}
            theme={theme}
            onToggleTheme={toggleTheme}
            userName={userName}
            onLogout={handleLogout}
          />

          <main className="app-content">
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
