/* Labels and explanations only. Amounts and monthly comparison come from the API. */
window.NotificacionesUX = (() => {
    const direction = value => Number(value) > .005 ? 'sube' : Number(value) < -.005 ? 'baja' : 'sin_impacto';
    const labels = { sube: 'Subió el importe', baja: 'Bajó el importe', sin_impacto: 'Sin impacto neto relevante' };
    function serviceCounts(item) {
        const result = { sube: 0, baja: 0, sin_impacto: 0 };
        (item.servicios || []).forEach(service => { result[direction(service.impacto_facturacion)]++; });
        return result;
    }
    function serviceSummary(item) {
        const counts = serviceCounts(item);
        return `${counts.sube} con suba · ${counts.baja} con baja · ${counts.sin_impacto} sin impacto neto`;
    }
    function reading(item) {
        const currentDirection = direction(item.impacto_facturacion);
        const counts = serviceCounts(item);
        if (counts.sube && counts.baja) return currentDirection === 'sin_impacto'
            ? 'Hay servicios que suben y otros que bajan; sus efectos se compensan en el neto.'
            : `El importe neto ${currentDirection === 'sube' ? 'subió' : 'bajó'}, con servicios que se movieron en ambas direcciones.`;
        if (currentDirection === 'sin_impacto') return 'El importe neto se mantuvo estable, aunque cambiaron algunos componentes.';
        return `El importe proyectado comparable ${currentDirection === 'sube' ? 'subió' : 'bajó'} respecto de ${item.mes_anterior_label}.`;
    }
    function metricChanges(item) {
        const definitions = [['dotacion_requerida', 'Dotación'], ['horas_proyectadas', 'Horas comparables'], ['precio_final', item.servicios ? 'Precio promedio ponderado' : 'Precio']];
        return definitions.map(([key, label]) => {
            const diff = Number(item.comparacion[key].diferencia);
            return `${label}: ${Math.abs(diff) <= .005 ? 'sin cambio' : diff > 0 ? 'subió' : 'bajó'}.`;
        }).join(' ');
    }
    function otherChanges(item) {
        const sources = item.servicios || [item];
        const extras = new Map();
        sources.forEach(service => (service.cambios || []).forEach(change => {
            if (['importe_fijo', 'variable_importe', 'variable_porcentaje', 'tarifacion'].includes(change.metrica)) extras.set(change.metrica, change.etiqueta);
        }));
        return [...extras.values()].join(', ');
    }
    return { direction, labels, serviceCounts, serviceSummary, reading, metricChanges, otherChanges };
})();
