window.ProyeccionesReview = (() => {
    const el = id => document.getElementById(id);
    const headerKey = value => normalizar(value).replace(/_/g, ' ').replace(/\s+/g, ' ');
    const key = row => `${row.tipo_plp}|${row.mes}|${headerKey(row.campania)}`;
    let errorId = 0;
    async function request(payload) {
        const response = await fetch('/api/matriz-proyecciones/revision', {
            method: 'POST', headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
            body: JSON.stringify(payload),
            signal: AbortSignal.timeout(20000),
        });
        const data = (response.headers.get('content-type') || '').includes('application/json') ? await response.json() : null;
        if (!response.ok || !data?.success) throw new Error((data?.errores || ['No se pudo preparar la revisión. Tus datos siguen sin guardar.']).join(' | '));
        return data;
    }
    function openReview({ description, summary, headers, rows, note, deletions = false }) {
        const dialog = el('revisionProyecciones');
        if (dialog.open) return Promise.resolve(false);
        el('revisionProyeccionesDescripcion').textContent = description;
        el('revisionProyeccionesResumen').textContent = summary;
        el('revisionProyeccionesResumen').classList.toggle('px-delete-warning', deletions);
        el('revisionProyeccionesCabecera').innerHTML = `<tr>${headers.map(text => `<th scope="col">${escapeHtml(text)}</th>`).join('')}</tr>`;
        el('revisionProyeccionesFilas').innerHTML = rows.map(row => `<tr${row.includes('Eliminar') ? ' class="px-review-delete"' : ''}>${row.map(text => `<td>${escapeHtml(text)}</td>`).join('')}</tr>`).join('');
        el('revisionProyeccionesNota').textContent = note;
        return new Promise(resolve => {
            const previousFocus = document.activeElement;
            dialog.returnValue = '';
            const cancel = () => dialog.close('cancel');
            const confirm = () => dialog.close('confirm');
            const closed = () => {
                el('cancelarRevisionArriba').removeEventListener('click', cancel);
                el('cancelarRevisionProyecciones').removeEventListener('click', cancel);
                el('confirmarRevisionProyecciones').removeEventListener('click', confirm);
                previousFocus?.focus({ preventScroll: true });
                resolve(dialog.returnValue === 'confirm');
            };
            el('cancelarRevisionArriba').addEventListener('click', cancel);
            el('cancelarRevisionProyecciones').addEventListener('click', cancel);
            el('confirmarRevisionProyecciones').addEventListener('click', confirm);
            dialog.addEventListener('close', closed, { once: true });
            dialog.showModal();
        });
    }
    async function revisarIndividual(payload) {
        const data = await request(payload);
        const creates = data.filas.filter(row => row.accion === 'Crear').length;
        return openReview({
            description: `${data.cliente} · ${data.campania}${data.tipo_plp ? ' · ' + data.tipo_plp : ''}`,
            summary: `${data.filas.length} mes(es) afectado(s): ${creates} registro(s) nuevos y ${data.filas.length - creates} a actualizar. ${data.tipo_plp ? 'Solo se modifica el mes seleccionado.' : 'Se aplican los parámetros desde el mes seleccionado hasta diciembre.'}`,
            headers: ['Mes', 'Acción', 'Días objetivo', 'Horas actuales', 'Horas propuestas'],
            rows: data.filas.map(row => [row.mes_label, row.accion, row.dias_objetivo, row.horas_actuales === null ? 'Sin registro' : formatNumber(row.horas_actuales), formatNumber(row.horas_propuestas)]),
            note: 'Horas proyectadas calculadas con las jornadas, feriados y cumplimiento vigentes. Volver a editar conserva tus datos. La revisión no guarda cambios.',
        });
    }
    function validarPLP(focus = true) {
        const rows = [...document.querySelectorAll('#tbodyEditorPLP tr[data-plp-dirty="1"]')];
        const year = String(el('yearFiltro').value);
        const duplicates = new Map();
        let firstInvalid;
        let invalidRows = 0;
        rows.forEach((row, index) => {
            row.dataset.plpValidated = '1';
            row.querySelectorAll('[aria-invalid]').forEach(field => { field.removeAttribute('aria-invalid'); field.removeAttribute('aria-describedby'); });
            let message = row.querySelector('[data-plp-error]');
            if (!message) {
                message = document.createElement('p');
                message.dataset.plpError = 'true';
                message.className = 'px-row-error';
                message.id = 'plp-error-' + (++errorId);
                row.querySelector('[data-plp="campania"]').parentElement.appendChild(message);
            }
            message.hidden = true;
            if (row.dataset.plpDeleted === '1') return;
            const field = name => row.querySelector(`[data-plp="${name}"]`);
            const values = Object.fromEntries([...row.querySelectorAll('[data-plp]')].map(control => [control.dataset.plp, control.value.trim()]));
            const errors = [];
            const fail = (name, text) => {
                errors.push(text);
                field(name).setAttribute('aria-invalid', 'true');
                field(name).setAttribute('aria-describedby', message.id);
                firstInvalid ||= field(name);
            };
            if (!values.tipo_plp) fail('tipo_plp', 'Seleccioná la clasificación.');
            if (!new RegExp(`^${year}-(0[1-9]|1[0-2])$`).test(values.mes)) fail('mes', `Seleccioná un mes de ${year}.`);
            if (!values.campania || values.campania.length > 100) fail('campania', 'Ingresá una campaña de hasta 100 caracteres.');
            for (const [name, min, max, label] of [['horas', 0, Infinity, 'Horas'], ['carga_horaria', 0, Infinity, 'Horas de jornada'], ['cumplimiento', 0, 1000, 'Cumplimiento']]) {
                const value = Number(values[name]);
                if (values[name] === '' || !Number.isFinite(value) || value < min || value > max || (name === 'carga_horaria' && value === 0)) fail(name, `${label}: ${name === 'cumplimiento' ? 'entre 0 y 1000' : name === 'horas' ? 'cero o mayor' : 'mayor a cero'}.`);
            }
            const identity = key({ tipo_plp: values.tipo_plp, mes: values.mes, campania: values.campania });
            if (duplicates.has(identity)) fail('campania', `Campaña repetida; también figura en la fila modificada ${duplicates.get(identity)}.`);
            else duplicates.set(identity, index + 1);
            if (errors.length) {
                invalidRows++;
                message.textContent = errors.join(' ');
                message.hidden = false;
            }
        });
        if (rows.length > 500) {
            mostrarMensaje('La edición masiva admite hasta 500 filas modificadas por operación.', 'error');
            return false;
        }
        if (firstInvalid && focus) {
            mostrarMensaje(`Revisá ${invalidRows} fila(s) señaladas antes de continuar. Los datos ingresados se conservan.`, 'error');
            firstInvalid.scrollIntoView({ block: 'center' });
            firstInvalid.focus({ preventScroll: true });
        }
        return !firstInvalid;
    }
    async function revisarPLP(rows, replaceMonths) {
        const data = await request({ modo: 'plp', year: el('yearFiltro').value, filas: rows });
        const existing = data.proyecciones;
        const keep = new Set(rows.filter(row => !row.eliminar).map(key));
        const deleted = new Map(existing.filter(row => replaceMonths.includes(row.mes) && !keep.has(key(row))).map(row => [String(row.id), row]));
        const details = [];
        rows.forEach((row, index) => {
            const byId = existing.find(item => String(item.id) === String(row.id));
            if (row.eliminar) {
                if (byId) deleted.set(String(byId.id), byId);
                return;
            }
            const byName = existing.find(item => item.id === data.coincidencias[index]);
            const actual = byName && String(byName.id) !== String(row.id) && !deleted.has(String(byName.id)) ? byName : byId;
            if (byId && actual && byId.id !== actual.id) deleted.set(String(byId.id), byId);
            details.push([row.mes, row.tipo_plp, row.campania, actual ? 'Actualizar' : 'Crear', actual ? formatNumber(actual.horas_requeridas) : 'Sin registro', formatNumber(Number(row.horas)), `${row.porcentaje_cumplimiento}%`]);
        });
        deleted.forEach(row => details.push([row.mes, row.tipo_plp, row.campania, 'Eliminar', formatNumber(row.horas_requeridas), '—', '—']));
        return openReview({
            description: `Edición masiva PLP · Año ${el('yearFiltro').value}`,
            summary: `${rows.filter(row => !row.eliminar).length} fila(s) a guardar y ${deleted.size} campaña(s) a eliminar.${replaceMonths.length ? ' Se reemplaza el contenido PLP completo de: ' + replaceMonths.join(', ') + '.' : ' Se conservan las demás campañas y meses.'}`,
            headers: ['Mes', 'Clasificación', 'Campaña', 'Acción', 'Horas cargadas actuales', 'Horas cargadas propuestas', 'Cumplimiento'],
            rows: details,
            deletions: deleted.size > 0,
            note: 'Las horas cargadas son las horas requeridas; el cumplimiento determina las horas proyectadas. Revisá especialmente las filas con acción Eliminar. La validación final se realiza al guardar.',
        });
    }
    document.addEventListener('click', event => {
        const button = event.target.closest('[data-plp-line]');
        if (!button) return;
        const textarea = el('tablaPegadaPLP');
        const lines = textarea.value.split('\n');
        const index = Number(button.dataset.plpLine) - 1;
        const start = lines.slice(0, index).reduce((total, line) => total + line.length + 1, 0);
        textarea.focus();
        textarea.setSelectionRange(start, start + (lines[index]?.length || 0));
    });
    return { revisarIndividual, revisarPLP, validarPLP };
})();
