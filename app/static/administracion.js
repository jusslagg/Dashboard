(() => {
    'use strict';
    const el = id => document.getElementById(id);
    const escape = value => String(value ?? '').replace(/[&<>"']/g,c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    let version = null, loadedYear = null, saving = false, settingsBusy = false, checkController, checkVersion = 0;
    let loadedCalendar = false, calendarYear;
    const dirty = () => loadedYear !== null && (el('adCalendar').checked !== loadedCalendar || (!el('adCalendar').checked && Number(el('adYear').value) !== loadedYear));
    function status(id,message,error = false) { el(id).textContent = message; el(id).dataset.error = String(error); }
    async function json(url,options = {}) {
        const response = await fetch(url,{...options,signal:options.signal || AbortSignal.timeout(30000)});
        const data = await response.json();
        if (!response.ok || !data.success) throw Error((data.errores || ['No se pudo completar la consulta.']).join(' '));
        return data;
    }
    async function settings() {
        if (saving || settingsBusy) return;
        if (dirty() && !confirm('¿Descartar la configuración pendiente y consultar la guardada?')) return;
        el('adSave').disabled = true;
        settingsBusy = true; el('adReload').disabled = true;
        try {
            const data = await json('/api/administracion/configuracion');
            version = data.version; loadedYear = data.anio;
            loadedCalendar = data.modo === 'calendario'; calendarYear = data.anio_calendario;
            el('adCalendar').checked = loadedCalendar; el('adYear').readOnly = loadedCalendar;
            el('adYear').value = data.anio;
            el('adPassword').value = '';
            status('adSettingsStatus','Año de apertura actual: ' + data.anio + (loadedCalendar ? ' · Avance automático por calendario.' : ' · Año fijo.'));
        } catch (error) { version = null; status('adSettingsStatus','No se pudo cargar la configuración. Reintentá con Actualizar configuración.',true); }
        finally { settingsBusy = false; el('adReload').disabled = false; el('adSave').disabled = version === null; }
    }
    async function checks() {
        if (!el('adReviewYear').checkValidity()) { el('adReviewYear').reportValidity(); return; }
        checkController?.abort(); checkController = new AbortController();
        const controller = checkController;
        const current = ++checkVersion;
        const timer = setTimeout(() => controller.abort(),30000);
        el('adChecks').replaceChildren(); status('adReviewStatus','Revisando configuración…');
        try {
            const data = await json('/api/administracion/pendientes?year=' + encodeURIComponent(el('adReviewYear').value),{signal:checkController.signal});
            if (current !== checkVersion) return;
            status('adReviewStatus','Revisión del año ' + data.year + '. Los datos no se modificaron.');
            el('adChecks').innerHTML = data.revisiones.map(item => `<details class="ad-check"><summary>${escape(item.titulo)} · ${item.total}</summary><p>${escape(item.descripcion)}</p><ul>${item.detalle.map(row => `<li>${escape(row.cliente)} / ${escape(row.campania)} ${escape(row.mes || '')}</li>`).join('')}</ul>${item.total > item.detalle.length ? '<p>Se muestran los primeros 50 casos.</p>' : ''}<a href="${escape(item.url)}">Abrir tarea para revisar →</a></details>`).join('');
        } catch (error) { if (current === checkVersion) status('adReviewStatus','No se pudo completar la revisión. Volvé a presionar Actualizar revisiones.',true); }
        finally { clearTimeout(timer); }
    }
    el('adSettings').addEventListener('submit',async event => {
        event.preventDefault();
        if (saving || version === null || !el('adSettings').reportValidity()) return;
        saving = true; el('adSave').disabled = true;
        el('adCalendar').disabled = true;
        el('adReload').disabled = true;
        el('adYear').readOnly = true; el('adPassword').readOnly = true;
        status('adSettingsStatus','Guardando año de apertura…');
        try {
            const data = await json('/api/administracion/configuracion',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({anio:Number(el('adYear').value),modo:el('adCalendar').checked ? 'calendario' : 'fijo',version,password_confirmacion:el('adPassword').value})});
            version = data.version; loadedYear = data.anio; el('adPassword').value = '';
            loadedCalendar = data.modo === 'calendario'; el('adYear').value = data.anio;
            status('adSettingsStatus',data.mensaje);
        } catch (error) { status('adSettingsStatus',error.message,true); }
        finally { saving = false; el('adSave').disabled = false; el('adReload').disabled = false; el('adCalendar').disabled = false; el('adYear').readOnly = el('adCalendar').checked; el('adPassword').readOnly = false; }
    });
    el('adReload').addEventListener('click',settings);
    el('adReview').addEventListener('click',checks);
    el('adCalendar').addEventListener('change',() => { el('adYear').readOnly = el('adCalendar').checked; if (el('adCalendar').checked && calendarYear) el('adYear').value = calendarYear; });
    window.addEventListener('beforeunload',event => { if (saving || dirty()) { event.preventDefault(); event.returnValue = ''; } });
    settings(); checks();
})();
