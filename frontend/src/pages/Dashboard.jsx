import React, { useState, useEffect } from 'react';
import { isSupabaseConfigured, supabase } from '../lib/supabase';
import { KpiCard, StatusBadge } from '../components/DashboardBase';
import { FileCheck, Clock, AlertCircle, Inbox, RefreshCw, ListOrdered } from 'lucide-react';
import {
  getFacturas,
  getFacturasStats,
  getProcesoStatus,
  isApiConfigured,
  triggerProcesoManual,
} from '../lib/api';
import { useToast } from '../components/ToastProvider';

const REALTIME_ENABLED = import.meta.env.VITE_ENABLE_SUPABASE_REALTIME === 'true';

export default function Dashboard() {
  const toast = useToast();
  const [stats, setStats] = useState({ hoy: 0, causadas: 0, pendientes: 0, errores: 0 });
  const [recent, setRecent] = useState([]);
  const [loading, setLoading] = useState(false);
  const [lastSync, setLastSync] = useState(null);
  const [error, setError] = useState(null);

  const fetchStats = async () => {
    if (!isApiConfigured) {
      setError('VITE_API_URL no está configurado.');
      return;
    }
    const response = await getFacturasStats();
    setStats(response.data || { hoy: 0, causadas: 0, pendientes: 0, errores: 0 });
  };

  const fetchRecent = async () => {
    if (!isApiConfigured) {
      setError('VITE_API_URL no está configurado.');
      return;
    }
    const response = await getFacturas({ page: 1, page_size: 10 });
    setRecent(response.data.data || []);
  };

  const fetchStatus = async () => {
    if (!isApiConfigured) return;
    const response = await getProcesoStatus();
    setLastSync(response.data?.last_execution || null);
  };

  const triggerProcess = async () => {
    setLoading(true);
    try {
      setError(null);
      await triggerProcesoManual();
      await fetchStats();
      await fetchRecent();
      await fetchStatus();
      toast.success('Sincronización completada. Dashboard actualizado.');
    } catch {
      setError('No se pudo sincronizar con el backend.');
      toast.error('Falló la sincronización manual de emails.');
    }
    setLoading(false);
  };

  useEffect(() => {
    const load = async () => {
      try {
        setError(null);
        await fetchStats();
        await fetchRecent();
        await fetchStatus();
      } catch {
        setError('No se pudo cargar el dashboard.');
        toast.error('No se pudo cargar el panel principal.');
      }
    };

    load();

    if (!REALTIME_ENABLED || !isSupabaseConfigured || !supabase) return undefined;

    const channel = supabase
      .channel('facturas-changes')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'facturas' }, () => {
        fetchStats();
        fetchRecent();
      })
      .subscribe();

    return () => { supabase.removeChannel(channel); };
  }, []);

  return (
    <div>
      {/* ── Page heading ───────────────────────────────── */}
      <div className="page-heading">
        <div>
          <h1 className="page-heading-title">Resumen General</h1>
          <p className="page-heading-sub">
            Monitoreo de causación en tiempo real
            {lastSync && (
              <span className="text-muted" style={{ marginLeft: '0.5rem' }}>
                · Última sincronización: {new Date(lastSync).toLocaleString('es-CO')}
              </span>
            )}
          </p>
        </div>
        <button
          onClick={triggerProcess}
          disabled={loading}
          className="btn-primary"
          id="btn-sync-emails"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          {loading ? 'Procesando…' : 'Sincronizar Emails'}
        </button>
      </div>

      {/* ── Error alert ────────────────────────────────── */}
      {error && (
        <div className="ui-alert" role="alert">
          {error}
        </div>
      )}

      {/* ── KPI Cards – 4 col grid ─────────────────────── */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
          gap: '1.5rem',
          marginBottom: '1.5rem',
        }}
      >
        <KpiCard label="Facturas Hoy"  value={stats.hoy}       icon={Inbox}        color="blue-500"   />
        <KpiCard label="Causadas"       value={stats.causadas}  icon={FileCheck}    color="green-500"  />
        <KpiCard label="Pendientes"     value={stats.pendientes} icon={Clock}       color="yellow-500" />
        <KpiCard label="Errores"        value={stats.errores}   icon={AlertCircle}  color="red-500"    />
      </div>

      {/* ── Últimas Facturas card ──────────────────────── */}
      <div className="sb-card">
        {/* Card header */}
        <div className="sb-card-header">
          <h2
            className="sb-card-header-title"
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
          >
            <ListOrdered size={16} />
            Últimas Facturas
          </h2>
          <span className="text-muted text-sm">Actividad reciente</span>
        </div>

        {/* Table */}
        <div className="table-responsive">
          <table className="table-admin" aria-label="Últimas facturas">
            <thead>
              <tr>
                <th>Factura</th>
                <th>Proveedor</th>
                <th className="d-none-mobile">NIT</th>
                <th>Total a pagar</th>
                <th>Estado</th>
                <th className="d-none-mobile">Fecha</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((f) => (
                <tr key={f.id} className="text-sm">
                  <td className="fw-bold">{f.numero_factura}</td>
                  <td>{f.nombre_proveedor}</td>
                  <td className="d-none-mobile text-muted">{f.nit_proveedor || '—'}</td>
                  <td className="fw-bold">${parseFloat(f.total_neto || f.total || 0).toLocaleString('es-CO')}</td>
                  <td><StatusBadge status={f.estado} /></td>
                  <td className="d-none-mobile text-muted">
                    {new Date(f.created_at).toLocaleDateString('es-CO', {
                      day: '2-digit', month: 'short', year: 'numeric',
                    })}
                  </td>
                </tr>
              ))}

              {recent.length === 0 && (
                <tr>
                  <td colSpan={6}>
                    <div className="table-empty">
                      <div className="table-empty-icon">📋</div>
                      <p className="fw-bold">No hay facturas recientes</p>
                      <p className="text-sm text-muted mt-1">
                        Usa "Sincronizar Emails" para procesar nuevas facturas.
                      </p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Card footer – row count */}
        <div className="table-footer">
          <span>
            Mostrando <strong>{recent.length}</strong>{' '}
            {recent.length === 1 ? 'registro' : 'registros'}
          </span>
        </div>
      </div>
    </div>
  );
}
