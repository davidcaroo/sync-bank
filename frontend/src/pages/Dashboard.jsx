import React, { useState, useEffect } from 'react';
import { KpiCard, StatusBadge } from '../components/DashboardBase';
import {
  IconFileCheck as FileCheck,
  IconClock as Clock,
  IconAlertCircle as AlertCircle,
  IconInbox as Inbox,
  IconRefresh as RefreshCw,
  IconFileText as ListOrdered,
  IconArchive
} from '../components/icons/Icons';
import {
  getFacturas,
  getFacturasStats,
  getProcesoStatus,
  isApiConfigured,
  triggerProcesoManual,
} from '../lib/api';
import { useToast } from '../components/ToastProvider';

export default function Dashboard() {
  const toast = useToast();
  const [stats, setStats] = useState({ hoy: 0, causadas: 0, pendientes: 0, errores: 0 });
  const [recent, setRecent] = useState([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const [loading, setLoading] = useState(false);
  const [lastSync, setLastSync] = useState(null);
  const [lastSyncSummary, setLastSyncSummary] = useState(null);
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
    setLastSyncSummary(response.data?.summary || null);
  };

  const triggerProcess = async () => {
    setLoading(true);
    try {
      setError(null);
      const response = await triggerProcesoManual();
      await fetchStats();
      await fetchRecent();
      await fetchStatus();

      const result = response?.data || {};
      const summary = result.summary || {};
      setLastSyncSummary(summary);
      const created = Number(summary.created || 0);
      const duplicates = Number(summary.duplicates || 0);
      const invalid = Number(summary.invalid || 0);
      const errors = Number(summary.errors || 0);
      const xmlExtracted = Number(summary.xml_extracted || 0);

      if (result.status === 'partial' || errors > 0) {
        toast.warning(
          `Sincronización parcial: ${created} creadas, ${duplicates} duplicadas, ${invalid} inválidas, ${errors} errores.`
        );
      } else if (created === 0 && duplicates === 0 && xmlExtracted === 0) {
        toast.info('Sincronización completada sin XML nuevos procesables.');
      } else {
        toast.success(
          `Sincronización completada: ${created} creadas, ${duplicates} duplicadas, ${invalid} inválidas.`
        );
      }
    } catch {
      setError('No se pudo sincronizar con el backend.');
      toast.error('Falló la sincronización manual de emails.');
    }
    setLoading(false);
  };

  const load = async () => {
    try {
      setError(null);
      await Promise.all([fetchStats(), fetchRecent(), fetchStatus()]);
    } catch {
      setError('No se pudo cargar el dashboard.');
      toast.error('No se pudo cargar el panel principal.');
    } finally {
      setInitialLoading(false);
    }
  };

  useEffect(() => {
    load();
    // ponytail: initial dashboard load is intentionally mount-only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="page-shell dashboard-page">
      {/* ── Page heading ───────────────────────────────── */}
      <div className="page-heading">
        <div>
          <h1 className="page-heading-title">Resumen general</h1>
          <p className="page-heading-sub">
            Visibilidad inmediata sobre recepción, revisión y causación.
            {lastSync && (
              <span className="text-muted" style={{ marginLeft: '0.5rem' }}>
                · Última sincronización: {new Date(lastSync).toLocaleString('es-CO', { timeZone: 'America/Bogota' })}
              </span>
            )}
          </p>
        </div>
        <button
          onClick={triggerProcess}
          disabled={loading}
          className="btn-primary"
          id="btn-sync-emails"
          style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
        >
          <RefreshCw 
            size={16} 
            style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} 
          />
          {loading ? 'Sincronizando…' : 'Sincronizar correos'}
        </button>
      </div>

      {/* ── Error alert ────────────────────────────────── */}
      {error && (
        <div className="ui-alert" role="alert">
          <div><strong>No pudimos actualizar el panel.</strong><span>{error}</span></div>
          <button type="button" className="btn-secondary btn-sm" onClick={load}>Reintentar</button>
        </div>
      )}

      {/* ── KPI Cards – 4 col grid ─────────────────────── */}
      <div className="dashboard-kpi-grid">
        <KpiCard label="Recibidas hoy"  value={stats.hoy}       icon={Inbox}        color="blue-500" loading={initialLoading} />
        <KpiCard label="Causadas"       value={stats.causadas}  icon={FileCheck}    color="green-500" loading={initialLoading} />
        <KpiCard label="Por revisar"    value={stats.pendientes} icon={Clock}       color="yellow-500" loading={initialLoading} />
        <KpiCard label="Con error"      value={stats.errores}   icon={AlertCircle}  color="red-500" loading={initialLoading} />
      </div>

      {/* ── Resultado última sincronización ─────────────────── */}
      {lastSyncSummary && (
        <div className="sb-card" style={{ marginBottom: '1.5rem' }}>
          <div className="sb-card-header">
            <h2 className="sb-card-header-title">Resultado última sincronización</h2>
            <span className="text-muted text-sm">Detalle de válidas, duplicadas e inválidas</span>
          </div>

          <div className="sb-card-body" style={{ display: 'grid', gap: '1rem' }}>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(170px, 1fr))',
                gap: '0.75rem',
              }}
            >
              <div className="status-badge badge-info">Emails: {Number(lastSyncSummary.messages_found || 0)}</div>
              <div className="status-badge badge-info">XML extraídos: {Number(lastSyncSummary.xml_extracted || 0)}</div>
              <div className="status-badge badge-success">Creadas: {Number(lastSyncSummary.created || 0)}</div>
              <div className="status-badge badge-muted">Duplicadas: {Number(lastSyncSummary.duplicates || 0)}</div>
              <div className="status-badge badge-warning">Inválidas: {Number(lastSyncSummary.invalid || 0)}</div>
              <div className="status-badge badge-danger">Errores: {Number(lastSyncSummary.errors || 0)}</div>
            </div>

            {Array.isArray(lastSyncSummary.invalid_details) && lastSyncSummary.invalid_details.length > 0 && (
              <div>
                <div className="text-sm fw-bold" style={{ marginBottom: '0.5rem' }}>
                  Documentos inválidos y causa
                </div>
                <div className="table-responsive" style={{ border: '1px solid var(--border)', borderRadius: '0.375rem' }}>
                  <table className="table-admin" aria-label="Detalle de inválidos de sincronización">
                    <thead>
                      <tr>
                        <th>Archivo</th>
                        <th>Entrada</th>
                        <th>Causa</th>
                        <th className="d-none-mobile">Asunto</th>
                      </tr>
                    </thead>
                    <tbody>
                      {lastSyncSummary.invalid_details.slice(0, 20).map((item, idx) => (
                        <tr key={`invalid-${idx}`}>
                          <td className="text-sm">{item.file_name || '—'}</td>
                          <td className="text-sm">{item.entry_name || '—'}</td>
                          <td className="text-sm text-muted">{item.reason || 'Sin detalle'}</td>
                          <td className="text-sm d-none-mobile">{item.asunto || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Últimas Facturas card ──────────────────────── */}
      <div className="sb-card activity-card">
        {/* Card header */}
        <div className="sb-card-header">
          <h2
            className="sb-card-header-title"
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
          >
            <ListOrdered size={16} />
            Facturas recientes
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
              {initialLoading && Array.from({ length: 5 }).map((_, index) => (
                <tr key={`skeleton-${index}`} aria-hidden="true">
                  <td><span className="skeleton skeleton-line skeleton-line-short" /></td>
                  <td><span className="skeleton skeleton-line" /></td>
                  <td className="d-none-mobile"><span className="skeleton skeleton-line" /></td>
                  <td><span className="skeleton skeleton-line skeleton-line-short" /></td>
                  <td><span className="skeleton skeleton-chip" /></td>
                  <td className="d-none-mobile"><span className="skeleton skeleton-line" /></td>
                </tr>
              ))}
              {!initialLoading && recent.map((f) => (
                <tr key={f.id} className="text-sm">
                  <td className="fw-bold">{f.numero_factura}</td>
                  <td>{f.nombre_proveedor}</td>
                  <td className="d-none-mobile text-muted">{f.nit_proveedor || '—'}</td>
                  <td className="fw-bold">${parseFloat(f.total_neto || f.total || 0).toLocaleString('es-CO')}</td>
                  <td><StatusBadge status={f.estado} /></td>
                  <td className="d-none-mobile text-muted">
                    {new Date(f.created_at).toLocaleDateString('es-CO', {
                      day: '2-digit', month: 'short', year: 'numeric',
                      timeZone: 'America/Bogota',
                    })}
                  </td>
                </tr>
              ))}

              {!initialLoading && recent.length === 0 && (
                <tr>
                  <td colSpan={6}>
                    <div className="table-empty">
                      <div className="table-empty-icon" style={{ opacity: 0.2 }}>
                        <IconArchive size={48} />
                      </div>
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
