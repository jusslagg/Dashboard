'use client';

import { useEffect, useMemo, useState } from 'react';
import Filters from '@/components/Filters';
import { formatMoney, formatMonth, formatNumber, formatPercent, getJson } from '@/lib/api';

export default function DashboardPage() {
  const [filters, setFilters] = useState({});
  const [data, setData] = useState({ kpis: null, resumen: [], clientes: [], alertas: [] });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setError('');
    Promise.all([
      getJson('/api/kpis', filters),
      getJson('/api/resumen', filters),
      getJson('/api/por-cliente', filters),
      getJson('/api/alertas', filters),
    ])
      .then(([kpis, resumen, clientes, alertas]) => {
        setData({
          kpis: kpis.kpis,
          resumen: resumen.resumen || [],
          clientes: clientes.clientes || [],
          alertas: alertas.alertas || [],
        });
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [filters]);

  const topDesvios = useMemo(() => (
    [...data.clientes]
      .sort((a, b) => Number(a.desvio || 0) - Number(b.desvio || 0))
      .slice(0, 8)
  ), [data.clientes]);

  const kpis = data.kpis || {};

  return (
    <>
      <header className="page-head">
        <div>
          <h2>Dashboard de Facturacion</h2>
          <p>Vista ejecutiva migrada a Next.js usando tus datos actuales.</p>
        </div>
        <a className="button" href="http://127.0.0.1:8009/api/exportar_excel">Exportar Excel</a>
      </header>

      <Filters value={filters} onChange={setFilters} />

      {error && <div className="notice">{error}</div>}
      {loading && <div className="notice">Cargando datos...</div>}

      <section className="kpis">
        <Kpi label="Total Facturado" value={formatMoney(kpis.total_facturado || kpis.total_real)} detail="Incluye tarificacion y ajustes" />
        <Kpi label="Total Teorico" value={formatMoney(kpis.total_teorico)} detail="Objetivo del periodo" />
        <Kpi label="Desvio" value={formatMoney(kpis.desvio)} detail={(kpis.desvio || 0) >= 0 ? 'Sobre objetivo' : 'Debajo del objetivo'} tone={(kpis.desvio || 0) >= 0 ? 'positive' : 'negative'} />
        <Kpi label="% Cumplimiento" value={formatPercent(kpis.porcentaje_cumplimiento)} detail={`${formatNumber(kpis.horas_facturadas)} horas facturadas`} />
      </section>

      <section className="grid-2">
        <div className="panel">
          <h3>Desvio por cliente</h3>
          <p className="panel-subtitle">Ordenado por mayor brecha negativa.</p>
          <div className="bars">
            {topDesvios.map((item) => <Bar key={item.cliente} item={item} />)}
          </div>
        </div>
        <div className="panel">
          <h3>Focos de atencion</h3>
          <p className="panel-subtitle">Alertas del backend Flask.</p>
          <div className="attention-list">
            {data.alertas.map((alerta, index) => (
              <div className="attention-item" key={`${alerta.titulo}-${index}`}>
                <strong>{alerta.titulo}</strong>
                <p className="panel-subtitle">{alerta.detalle}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="panel">
        <h3>Agrupacion por Cliente</h3>
        <p className="panel-subtitle">Totales calculados desde la base actual.</p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Cliente</th>
                <th>Gerente</th>
                <th className="num">Horas Obj.</th>
                <th className="num">Horas Fact.</th>
                <th className="num">Total Facturado</th>
                <th className="num">Total Teorico</th>
                <th className="num">Desvio</th>
                <th className="num">% Cump.</th>
              </tr>
            </thead>
            <tbody>
              {data.clientes.map((cliente) => (
                <tr key={`${cliente.cliente}-${cliente.gerente}`}>
                  <td>{cliente.cliente}</td>
                  <td>{cliente.gerente || '-'}</td>
                  <td className="num">{formatNumber(cliente.horas_objetivo)}</td>
                  <td className="num">{formatNumber(cliente.horas_facturadas)}</td>
                  <td className="num">{formatMoney(cliente.total_facturado || cliente.total_real)}</td>
                  <td className="num">{formatMoney(cliente.total_teorico)}</td>
                  <td className={`num ${(cliente.desvio || 0) >= 0 ? 'positive' : 'negative'}`}>{formatMoney(cliente.desvio)}</td>
                  <td className="num">{formatPercent(cliente.porcentaje_cumplimiento)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel" style={{ marginTop: 18 }}>
        <h3>Resumen por Mes</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Mes</th>
                <th className="num">Horas Obj.</th>
                <th className="num">Horas Fact.</th>
                <th className="num">Var. Productivo</th>
                <th className="num">Total Facturado</th>
                <th className="num">Total Teorico</th>
                <th className="num">Desvio</th>
                <th className="num">% Cump.</th>
              </tr>
            </thead>
            <tbody>
              {data.resumen.map((row) => (
                <tr key={row.mes}>
                  <td>{formatMonth(row.mes)}</td>
                  <td className="num">{formatNumber(row.horas_objetivo)}</td>
                  <td className="num">{formatNumber(row.horas_facturadas)}</td>
                  <td className={`num ${(row.variable_productivo || 0) >= 0 ? 'positive' : 'negative'}`}>{formatMoney(row.variable_productivo)}</td>
                  <td className="num">{formatMoney(row.total_facturado || row.total_real)}</td>
                  <td className="num">{formatMoney(row.total_teorico)}</td>
                  <td className={`num ${(row.desvio || 0) >= 0 ? 'positive' : 'negative'}`}>{formatMoney(row.desvio)}</td>
                  <td className="num">{formatPercent(row.porcentaje_cumplimiento)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

function Kpi({ label, value, detail, tone = '' }) {
  return (
    <article className="card">
      <div className="card-label">{label}</div>
      <div className={`card-value ${tone}`}>{value}</div>
      <div className="card-detail">{detail}</div>
    </article>
  );
}

function Bar({ item }) {
  const abs = Math.abs(Number(item.desvio || 0));
  const width = Math.max(6, Math.min(100, abs / 200000));
  return (
    <div className="bar-row">
      <span>{item.cliente}</span>
      <div className="bar-track">
        <div className={`bar-fill ${(item.desvio || 0) < 0 ? 'negative' : ''}`} style={{ width: `${width}%` }} />
      </div>
      <span className={`num ${(item.desvio || 0) >= 0 ? 'positive' : 'negative'}`}>{formatMoney(item.desvio)}</span>
    </div>
  );
}
