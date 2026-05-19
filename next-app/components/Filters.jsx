'use client';

import { useEffect, useState } from 'react';
import { getJson } from '@/lib/api';

const controls = [
  ['mes', 'Mes', 'meses'],
  ['cliente', 'Cliente', 'clientes'],
  ['gerente', 'Gerente', 'gerentes'],
  ['jefe_site', 'Jefe de Site', 'jefes_site'],
  ['campania', 'Campania', 'campanias'],
  ['subcampania', 'Sub campania', 'subcampanias'],
  ['tipo_negocio', 'Tipo de negocio', 'tipos_negocio'],
];

export default function Filters({ value, onChange, compact = false }) {
  const [options, setOptions] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    getJson('/api/filtros')
      .then((data) => setOptions(data.filtros))
      .catch((err) => setError(err.message));
  }, []);

  function update(name, selected) {
    onChange({ ...value, [name]: selected });
  }

  if (error) {
    return <div className="notice">{error}</div>;
  }

  return (
    <section className="toolbar" style={compact ? { gridTemplateColumns: 'repeat(4, minmax(140px, 1fr))' } : undefined}>
      {controls.map(([name, label, key]) => (
        <div className="field" key={name}>
          <label>{label}</label>
          <select value={value[name] || ''} onChange={(event) => update(name, event.target.value)}>
            <option value="">Todos</option>
            {(options?.[key] || []).map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </div>
      ))}
      <div className="field">
        <label>&nbsp;</label>
        <button className="button secondary" type="button" onClick={() => onChange({})}>Limpiar</button>
      </div>
    </section>
  );
}
