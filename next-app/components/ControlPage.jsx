'use client';

import { useEffect, useState } from 'react';
import Filters from '@/components/Filters';
import { formatMoneyFull, formatMonth, formatNumber, formatPercent, getJson } from '@/lib/api';

export default function ControlPage() {
  const [filters, setFilters] = useState({});
  const [rows, setRows] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setError('');
    getJson('/api/datos', filters)
      .then((data) => setRows(data.data || []))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [filters]);

  return (
    <>
      <header className="page-head">
        <div>
          <h2>Control de Facturacion</h2>
          <p>Lectura operativa en Next.js. La edicion completa sigue disponible en Flask durante la migracion.</p>
        </div>
        <a className="button" href="http://127.0.0.1:8009/control">Editar en Flask</a>
      </header>

      <Filters value={filters} onChange={setFilters} compact />

      {error && <div className="notice">{error}</div>}
      {loading && <div className="notice">Cargando registros...</div>}

      <section className="panel control-table">
        <h3>Registros de facturacion</h3>
        <p className="panel-subtitle">{rows.length} registro(s) encontrados.</p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Mes</th>
                <th>Cliente</th>
                <th>Gerente</th>
                <th>Jefe Site</th>
                <th>Campania</th>
                <th>Sub campania</th>
                <th>Tipo negocio</th>
                <th>Tipo VH</th>
                <th className="num">H.Obj.</th>
                <th className="num">H.Fact.</th>
                <th className="num">% Horas</th>
                <th className="num">VH Obj.</th>
                <th className="num">VH Alc.</th>
                <th className="num">Fact. Horas</th>
                <th className="num">Tarificacion</th>
                <th className="num">Fact. Bono</th>
                <th className="num">Var. Productivo</th>
                <th className="num">Penaliz.</th>
                <th className="num">Otros</th>
                <th className="num">Total Facturado</th>
                <th className="num">Desvio</th>
                <th className="num">% Cump.</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.fecha}</td>
                  <td>{formatMonth(row.mes)}</td>
                  <td>{row.cliente}</td>
                  <td>{row.gerente || '-'}</td>
                  <td>{row.jefe_site || '-'}</td>
                  <td>{row.campania || '-'}</td>
                  <td>{row.subcampania || '-'}</td>
                  <td>{row.tipo_negocio || '-'}</td>
                  <td>{row.tipo_jornada}</td>
                  <td className="num">{formatNumber(row.horas_objetivo)}</td>
                  <td className="num">{formatNumber(row.horas_facturadas)}</td>
                  <td className="num">{formatPercent(row.porcentaje_cumplimiento_horas)}</td>
                  <td className="num">{formatMoneyFull(row.valor_hora_objetivo || row.valor_hora)}</td>
                  <td className="num">{formatMoneyFull(row.valor_hora_alcanzado || row.valor_hora)}</td>
                  <td className="num">{formatMoneyFull(row.facturado_horas)}</td>
                  <td className="num">{formatMoneyFull(row.tarifacion)}</td>
                  <td className={`num ${(row.facturado_bono || 0) >= 0 ? 'positive' : 'negative'}`}>{formatMoneyFull(row.facturado_bono)}</td>
                  <td className={`num ${(row.variable_productivo || 0) >= 0 ? 'positive' : 'negative'}`}>{formatMoneyFull(row.variable_productivo)}</td>
                  <td className={`num ${(row.penalizaciones || 0) >= 0 ? 'positive' : 'negative'}`}>{formatMoneyFull(row.penalizaciones)}</td>
                  <td className="num">{formatMoneyFull(row.otros)}</td>
                  <td className="num"><strong>{formatMoneyFull(row.total_facturado || row.total_real)}</strong></td>
                  <td className={`num ${(row.desvio || 0) >= 0 ? 'positive' : 'negative'}`}>{formatMoneyFull(row.desvio)}</td>
                  <td className="num">
                    <span className={`badge ${(row.porcentaje_cumplimiento || 0) >= 100 ? 'good' : (row.porcentaje_cumplimiento || 0) >= 95 ? 'warn' : 'bad'}`}>
                      {formatPercent(row.porcentaje_cumplimiento)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
