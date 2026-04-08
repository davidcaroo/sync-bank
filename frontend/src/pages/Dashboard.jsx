import React, { useState, useEffect } from 'react';
import { isSupabaseConfigured, supabase } from '../lib/supabase';
import { KpiCard, StatusBadge } from '../components/DashboardBase';
import { FileCheck, Clock, AlertCircle, Inbox, RefreshCw, ChartSpline } from 'lucide-react';
import {
  getFacturas,
  getFacturasStats,
  getProcesoStatus,
  isApiConfigured,
  triggerProcesoManual,
} from '../lib/api';
import { useToast } from '../components/ToastProvider';

const REALTIME_ENABLED = import.meta.env.VITE_ENABLE_SUPABASE_REALTIME === 'true'

export default function Dashboard() {
  const toast = useToast()
  const [stats, setStats] = useState({ hoy: 0, causadas: 0, pendientes: 0, errores: 0 });
  const [recent, setRecent] = useState([]);
  const [loading, setLoading] = useState(false);
  const [lastSync, setLastSync] = useState(null);
  const [error, setError] = useState(null);

  const fetchStats = async () => {
    if (!isApiConfigured) {
      setError('VITE_API_URL no esta configurado.')
      return
    }

    const response = await getFacturasStats();
    setStats(response.data || { hoy: 0, causadas: 0, pendientes: 0, errores: 0 });
  };

  const fetchRecent = async () => {
    if (!isApiConfigured) {
      setError('VITE_API_URL no esta configurado.')
      return
    }

    const response = await getFacturas({ page: 1, page_size: 10 });
    setRecent(response.data.data || []);
  };

  const fetchStatus = async () => {
    if (!isApiConfigured) {
      return
    }

    const response = await getProcesoStatus();
    setLastSync(response.data?.last_execution || null);
  };

  const triggerProcess = async () => {
    setLoading(true);
    try {
      setError(null)
      await triggerProcesoManual();
      await fetchStats();
      await fetchRecent();
      await fetchStatus();
      toast.success('Sincronizacion completada. Dashboard actualizado.')
    } catch (err) {
      setError('No se pudo sincronizar con el backend.')
      toast.error('Fallo la sincronizacion manual de emails.')
    }
    setLoading(false);
  };

  useEffect(() => {
    const load = async () => {
      try {
        setError(null)
        await fetchStats();
        await fetchRecent();
        await fetchStatus();
      } catch (err) {
        setError('No se pudo cargar el dashboard.')
        toast.error('No se pudo cargar el panel principal.')
      }
    }

    load();

    if (!REALTIME_ENABLED || !isSupabaseConfigured || !supabase) {
      return undefined
    }

    // Realtime subscription
    const channel = supabase
      .channel('facturas-changes')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'facturas' }, () => {
        fetchStats();
        fetchRecent();
      })
      .subscribe();

    return () => { supabase.removeChannel(channel) };
  }, []);

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex flex-wrap justify-between items-end gap-4">
        <div>
          <h2 className="text-3xl font-bold">Resumen General</h2>
          <p className="text-gray-400 mt-1">Monitoreo de causación en tiempo real.</p>
          <p className="text-xs text-gray-500 mt-1">
            Ultima sincronizacion: {lastSync ? new Date(lastSync).toLocaleString() : 'Sin registro'}
          </p>
        </div>
        <button 
          onClick={triggerProcess}
          disabled={loading}
          className="btn-primary flex items-center space-x-2"
        >
          <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
          <span>{loading ? 'Procesando...' : 'Sincronizar Emails'}</span>
        </button>
      </div>

      {error && (
        <div className="ui-alert text-sm">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <KpiCard label="Facturas Hoy" value={stats.hoy} icon={Inbox} color="blue-500" />
        <KpiCard label="Causadas" value={stats.causadas} icon={FileCheck} color="green-500" />
        <KpiCard label="Pendientes" value={stats.pendientes} icon={Clock} color="yellow-500" />
        <KpiCard label="Errores" value={stats.errores} icon={AlertCircle} color="red-500" />
      </div>

      <div className="panel-card overflow-hidden">
        <div className="panel-header">
          <div className="flex items-center gap-2">
            <ChartSpline size={16} />
            <h3>Últimas Facturas</h3>
          </div>
          <p>Actividad reciente</p>
        </div>
        <div className="overflow-x-auto">
          <table className="table-admin">
            <thead>
              <tr>
                <th>Factura</th>
                <th>Proveedor</th>
                <th>Total</th>
                <th>Estado</th>
                <th>Fecha</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((f) => (
                <tr key={f.id} className="table-row-hover text-sm">
                  <td className="font-semibold">{f.numero_factura}</td>
                  <td>{f.nombre_proveedor}</td>
                  <td>${parseFloat(f.total).toLocaleString()}</td>
                  <td>
                    <StatusBadge status={f.estado} />
                  </td>
                  <td>
                    {new Date(f.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
              {recent.length === 0 && (
                <tr>
                  <td className="text-sm" colSpan={5}>
                    No hay facturas recientes.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
