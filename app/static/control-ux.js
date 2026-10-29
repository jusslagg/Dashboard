window.ControlUX = (() => {
    const state = { rows: [], records: new Map(), page: 1, size: 50, query: '', dirty: false, saving: false, previousFocus: null };
    const el = id => document.getElementById(id);
    function status(text, kind = 'info') {
        el('estadoControl').textContent = text;
        el('estadoControl').dataset.state = kind;
    }
    function setRows(rows, query) {
        if (state.query !== query) state.page = 1;
        state.query = query;
        state.rows = rows;
        state.records = new Map(rows.map(row => [String(row.id), row]));
    }
    function pageRows() {
        const pages = Math.max(1, Math.ceil(state.rows.length / state.size));
        state.page = Math.min(state.page, pages);
        const start = (state.page - 1) * state.size;
        el('controlPaginaAnterior').disabled = state.page === 1;
        el('controlPaginaSiguiente').disabled = state.page === pages;
        status(state.rows.length ? `${start + 1}–${Math.min(start + state.size, state.rows.length)} de ${state.rows.length.toLocaleString('es-AR')} registros filtrados · Página ${state.page} de ${pages}` : 'Sin registros para estos filtros.', 'success');
        return state.rows.slice(start, start + state.size);
    }
    function changed() {
        state.dirty = true;
        el('estadoEdicionControl').textContent = 'Tenés cambios sin guardar en este registro.';
    }
    function open() {
        state.dirty = false;
        el('estadoEdicionControl').textContent = 'Los cambios se aplican a este registro al confirmar con tu contraseña.';
        el('errorEdicionControl').hidden = true;
        state.previousFocus = document.activeElement;
        el('modalEditar').showModal();
    }
    function close(force = false) {
        if (state.saving && !force) return;
        if (state.dirty && !force && !window.confirm('¿Descartar los cambios sin guardar de este registro?')) return;
        state.dirty = false;
        el('editClave').value = '';
        el('modalEditar').close();
        state.previousFocus?.focus({ preventScroll: true });
    }
    function error(text) {
        el('errorEdicionControl').textContent = text;
        el('errorEdicionControl').hidden = false;
        el('errorEdicionControl').focus();
    }
    document.addEventListener('DOMContentLoaded', () => {
        el('tablaDatos').addEventListener('click', event => {
            const button = event.target.closest('[data-control-edit]');
            if (!button) return;
            const row = state.records.get(button.dataset.controlEdit);
            if (row) abrirEditar(row);
        });
        el('formEditar').addEventListener('input', changed);
        el('formEditar').addEventListener('change', changed);
        el('modalEditar').addEventListener('cancel', event => { event.preventDefault(); close(); });
        el('formEditar').querySelectorAll('label:not([for])').forEach(label => {
            const field = label.parentElement.querySelector('input[id], select[id]');
            if (field) label.htmlFor = field.id;
        });
    });
    window.addEventListener('beforeunload', event => {
        if (!state.dirty && !state.saving) return;
        event.preventDefault();
        event.returnValue = '';
    });
    return {
        state, status, setRows, pageRows, open, close, error,
        edit(id) { const row = state.records.get(String(id)); if (row) abrirEditar(row); },
        page(delta) { state.page = Math.max(1, state.page + delta); actualizarTabla(state.rows); el('tablaControlScroll').scrollTop = 0; },
        resize(value) { state.size = Number(value); state.page = 1; actualizarTabla(state.rows); },
        escape(value) { return String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char])); },
    };
})();
