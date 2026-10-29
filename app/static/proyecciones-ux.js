/* Presentation and navigation only. Projection formulas remain in the template. */
window.ProyeccionesUX = (() => {
    const state = { page: 1, size: 50, signature: '', formDirty: false, loadedYear: '', editorMonths: [], request: 0 };
    let searchTimer;
    const el = id => document.getElementById(id);
    const plpDirty = () => Boolean(document.querySelector('#tbodyEditorPLP tr[data-plp-dirty="1"]'));
    const personalDirty = () => Boolean(document.querySelector('[data-personal-dirty="1"]'));
    const pending = () => state.formDirty || plpDirty() || personalDirty() || Boolean(el('tablaPegadaPLP')?.value.trim());
    function status(text, kind = 'info') {
        el('estadoCargaProyecciones').textContent = text;
        el('estadoCargaProyecciones').dataset.state = kind;
    }
    function updatePending() {
        const labels = [];
        if (state.formDirty) labels.push('formulario de proyección');
        if (plpDirty()) labels.push('campañas PLP');
        if (personalDirty()) labels.push('distribución diurna/nocturna');
        if (el('tablaPegadaPLP')?.value.trim()) labels.push('tabla pegada');
        el('estadoCambiosProyecciones').hidden = !labels.length;
        el('estadoCambiosProyecciones').textContent = 'Cambios sin guardar: ' + labels.join(', ') + '. Ocultar una sección conserva sus cambios.';
    }
    function confirmDiscard() {
        return !pending() || window.confirm('Hay cambios sin guardar. ¿Descartarlos y volver a cargar la información?');
    }
    function abrirEditor() {
        el('editorProyeccion').hidden = false;
        el('editorProyeccion').parentElement.classList.add('px-editor-open');
        el('abrirEditorProyeccion').setAttribute('aria-expanded', 'true');
        el('editorProyeccion').scrollIntoView({ block: 'start', behavior: 'smooth' });
    }
    function cerrarEditor() {
        el('editorProyeccion').hidden = true;
        el('editorProyeccion').parentElement.classList.remove('px-editor-open');
        el('abrirEditorProyeccion').setAttribute('aria-expanded', 'false');
        el('abrirEditorProyeccion').focus();
    }
    function pageItems(items, signature) {
        if (signature !== state.signature) { state.signature = signature; state.page = 1; }
        const pages = Math.max(1, Math.ceil(items.length / state.size));
        state.page = Math.min(state.page, pages);
        const start = (state.page - 1) * state.size;
        el('paginacionProyecciones').hidden = false;
        el('rangoProyecciones').textContent = items.length ? `${start + 1}–${Math.min(start + state.size, items.length)} de ${items.length} servicios · Página ${state.page} de ${pages}` : 'Sin resultados';
        el('paginaAnteriorProyecciones').disabled = state.page <= 1;
        el('paginaSiguienteProyecciones').disabled = state.page >= pages;
        return items.slice(start, start + state.size);
    }
    async function actualizar() {
        if (!confirmDiscard()) return;
        await cargarProyecciones(true);
    }
    async function cambiarAnio() {
        if (!confirmDiscard()) {
            el('yearFiltro').value = state.loadedYear;
            el('yearFiltro').dispatchEvent(new Event('app-filter-sync'));
            return;
        }
        await cargarProyecciones(true);
    }
    document.addEventListener('DOMContentLoaded', () => {
        state.loadedYear = el('yearFiltro').value;
        el('formProyeccion').addEventListener('input', () => { state.formDirty = true; updatePending(); });
        el('formProyeccion').addEventListener('change', () => { state.formDirty = true; updatePending(); });
        el('formProyeccion').addEventListener('reset', () => { state.formDirty = false; updatePending(); });
        el('proyeccionesWorkspace').addEventListener('input', updatePending);
        el('proyeccionesWorkspace').addEventListener('change', updatePending);
        el('proyeccionesWorkspace').addEventListener('click', () => queueMicrotask(updatePending));
        document.querySelectorAll('#formProyeccion label:not([for])').forEach(label => {
            const field = label.parentElement.querySelector('input[id], select[id]');
            if (field) label.htmlFor = field.id;
        });
    });
    window.addEventListener('beforeunload', event => {
        if (!pending()) return;
        event.preventDefault();
        event.returnValue = '';
    });
    return {
        state, status, updatePending, pending, plpDirty, personalDirty, abrirEditor, cerrarEditor, pageItems, actualizar, cambiarAnio,
        buscar() { clearTimeout(searchTimer); searchTimer = setTimeout(() => renderProyecciones(), 180); },
        pagina(delta) { state.page = Math.max(1, state.page + delta); renderProyecciones(); el('tablaProyeccionesScroll').scrollTop = 0; },
        cambiarTamano() { state.size = Number(el('tamanoPaginaProyecciones').value); state.page = 1; renderProyecciones(); },
        limpiarFiltros() {
            el('buscarProyeccion').value = '';
            AppFilters.seleccionar('filtroCliente', []);
            actualizarFiltroCampania();
            AppFilters.seleccionar('filtroCampania', []);
            AppFilters.seleccionar('filtroMes', []);
            renderProyecciones();
        },
        nueva() {
            if (state.formDirty && !window.confirm('¿Descartar los cambios del formulario y empezar una nueva proyección?')) return;
            limpiarFormulario();
            abrirEditor();
        },
    };
})();
