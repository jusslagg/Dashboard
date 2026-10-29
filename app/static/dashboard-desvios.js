/* Read-only exploration of the same billing figures used by the dashboard. */
(() => {
    'use strict';
    const dialog = document.getElementById('dashboardDesviosDialog');
    if (!dialog) return;
    const el = id => document.getElementById(id);
    const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const number = value => Number(value).toLocaleString('es-AR', {minimumFractionDigits:2, maximumFractionDigits:2});
    const money = value => `${value < 0 ? '−' : ''}$ ${number(Math.abs(value))}`;
    const selects = [...dialog.querySelectorAll('[data-dv-filter]')];
    let contextQuery = '', baseQuery = '', trigger, data, tab = 'clientes', controller, version = 0, timer, compareAll = false, selectedCampaign = null;
    function cell(value, tipo, extra = '') {
        if (value == null) return `<td class="${extra}" title="Sin registros o sin objetivo de referencia">—</td>`;
        const signed = ['moneda','total','desvio_porcentaje'].includes(tipo);
        const direction = signed ? (value > .005 ? 'dv-up' : value < -.005 ? 'dv-down' : '') : tipo === 'cumplimiento' ? (value >= 100 ? 'dv-up' : 'dv-down') : '';
        const label = ['moneda','total','importe'].includes(tipo) ? money(value) : number(value) + (['cumplimiento','desvio_porcentaje'].includes(tipo) ? '%' : '');
        return `<td class="${direction} ${extra}">${label}</td>`;
    }
    function signLabel(direction) {
        return direction === 'positivo' ? 'Desvío positivo' : direction === 'negativo' ? 'Desvío negativo' : 'Sin desvío';
    }
    function card(item, index, campaign = false) {
        const action = campaign ? 'data-dv-campaign' : 'data-dv-client-campaigns';
        const percent = value => value == null ? '—' : number(value) + '%';
        return `<article class="dv-explore-card"><button type="button" ${action}="${index}"><strong>${escape(campaign ? item.nombre : item.cliente)}</strong><small class="dv-sign ${item.direccion === 'positivo' ? 'dv-up' : item.direccion === 'negativo' ? 'dv-down' : ''}">${signLabel(item.direccion)}</small><span class="dv-card-amount ${item.direccion === 'positivo' ? 'dv-up' : item.direccion === 'negativo' ? 'dv-down' : ''}">${money(item.resumen.desvio)}</span><span class="dv-card-metrics"><span>Facturación <b>${percent(item.resumen.cumplimiento_facturacion)}</b></span><span>Horas <b>${percent(item.resumen.cumplimiento_horas)}</b></span></span><small>${campaign ? 'Ver detalle mensual' : 'Ver campañas'} →</small></button>${campaign ? '' : `<button type="button" class="dv-card-secondary" data-dv-client="${index}">Ver total mensual del cliente →</button>`}</article>`;
    }
    function render() {
        if (!data) return;
        const panel = el('dvPanel');
        panel.setAttribute('aria-labelledby', {clientes:'dvTabClientes',mensual:'dvTabMensual',campanias:'dvTabCampanias'}[tab]);
        dialog.querySelectorAll('[data-dv-tab]').forEach(button => button.setAttribute('aria-selected', String(button.dataset.dvTab === tab)));
        const pickingClient = tab !== 'clientes' && data.clientes.length > 1 && !el('dvClient').value && (tab === 'campanias' || !compareAll);
        el('dvDetail').parentElement.hidden = tab !== 'mensual' || pickingClient || !data.clientes.length;
        el('dvScrollHint').hidden = tab !== 'mensual' || pickingClient || !data.clientes.length;
        el('dvStatus').textContent = `${data.clientes.length} cliente(s) · Desvío total: ${money(data.totales.desvio)}`;
        el('dvCriteria').textContent = data.criterio;
        el('dvTitle').textContent = tab === 'clientes' && el('dvDirection').value ? (el('dvDirection').value === 'sin_desvio' ? 'Clientes sin desvío' : `Clientes con ${signLabel(el('dvDirection').value).toLowerCase()}`) : 'Desvíos de facturación';
        el('dvDirectionLabel').textContent = tab === 'campanias' || selectedCampaign ? 'Desvío del cliente' : 'Desvío';
        const campaignContext = el('dvCampaignContext');
        campaignContext.hidden = !selectedCampaign && !(tab === 'campanias' && data.clientes.length === 1);
        campaignContext.innerHTML = selectedCampaign ? `<button type="button" data-dv-back-campaigns>← Volver a campañas</button><span>${escape(el('dvClient').value)} / <strong>${escape(selectedCampaign.nombre)}</strong></span>` : tab === 'campanias' && data.clientes.length === 1 ? `<button type="button" data-dv-back-clients>← Volver a clientes</button><strong>${escape(data.clientes[0].cliente)}</strong>` : '';
        if (!data.clientes.length) { panel.innerHTML = '<p class="dv-empty">No hay clientes para esta selección. Probá otro desvío o limpiá los filtros del cuadro.</p>'; return; }
        if (pickingClient) {
            panel.innerHTML = `<div class="dv-picker"><h3>${tab === 'campanias' ? 'Elegí un cliente para ver sus campañas' : 'Elegí un cliente para entender su desvío'}</h3><p>Primero vas a ver los conceptos principales. Podés ampliar los indicadores cuando lo necesites.</p><div class="dv-client-grid">` + data.clientes.map((item,index) => `<button type="button" data-dv-client="${index}"><strong>${escape(item.cliente)}</strong><span class="${item.direccion === 'negativo' ? 'dv-down' : item.direccion === 'positivo' ? 'dv-up' : ''}">${money(item.resumen.desvio)}</span><small>${tab === 'campanias' ? 'Ver campañas' : 'Ver detalle mensual'} →</small></button>`).join('') + `</div>${tab === 'mensual' ? '<button type="button" data-dv-compare class="dv-client-action">Comparar todos los clientes en una tabla</button>' : ''}</div>`;
            return;
        }
        if (tab === 'campanias') {
            const client = data.clientes[0];
            if (!Array.isArray(client.campanias)) { el('dvClient').value = client.cliente; load(); return; }
            el('dvStatus').textContent = `${client.cliente} · ${client.campanias.length} campaña(s) · Desvío total: ${money(client.resumen.desvio)}`;
            panel.innerHTML = '<div class="dv-picker"><h3>Campañas de ' + escape(client.cliente) + '</h3><p>El signo de cada campaña es independiente del total del cliente. Elegí una para ver qué explica su desvío mes a mes.</p><div class="dv-client-grid dv-campaign-grid">' + client.campanias.map((item,index) => card(item,index,true)).join('') + '</div></div>';
            return;
        }
        if (tab === 'clientes') {
            panel.innerHTML = '<div class="dv-picker"><h3>Elegí un cliente para ver sus campañas</h3><p>Las tarjetas muestran el desvío total del cliente. Abrí sus campañas para entender cómo se compone.</p><div class="dv-client-grid dv-accounts-grid">' + data.clientes.map((item,index) => card(item,index)).join('') + '</div></div>';
        } else {
            const matrixItems = selectedCampaign ? data.clientes.flatMap(item => (item.campanias || []).filter(campaign => campaign.campania === selectedCampaign.campania).map(campaign => ({...campaign,cliente:campaign.nombre}))) : data.clientes;
            if (!matrixItems.length) { panel.innerHTML = '<p class="dv-empty">Esta campaña no tiene registros para los filtros elegidos. Podés volver a campañas o cambiar los filtros.</p>'; return; }
            if (selectedCampaign) el('dvStatus').textContent = `${selectedCampaign.nombre} · Desvío: ${money(matrixItems[0].resumen.desvio)}`;
            const essentials = ['desvio_horas','desvio_variable','penalizaciones_bonos','cumplimiento_facturacion','cumplimiento_horas','desvio'];
            const rows = data.filas.filter(row => el('dvDetail').checked || essentials.includes(row.id));
            const value = (summary,row) => !summary ? null : row.id === 'conciliacion' ? summary.ajuste_objetivo + summary.redondeo : summary[row.id];
            const adjustments = {id:'conciliacion',label:'Ajustes de conciliación',tipo:'moneda'};
            if (!el('dvDetail').checked && matrixItems.some(item => [item.resumen,...Object.values(item.meses)].some(summary => Math.abs(value(summary,adjustments)) > .005))) rows.splice(3,0,adjustments);
            panel.innerHTML = `<table class="dv-table dv-matrix"><thead><tr><th scope="col">${selectedCampaign ? 'Campaña' : 'Cuenta'}</th><th scope="col">Concepto</th>` + data.meses.map(month => `<th scope="col">${escape(month.label)}</th>`).join('') + '<th scope="col">Total período</th></tr></thead><tbody>' + matrixItems.map(item => rows.map((row,index) => `<tr class="${row.tipo === 'total' ? 'dv-total' : ''}">${index === 0 ? `<th scope="rowgroup" rowspan="${rows.length}" class="dv-account">${escape(item.cliente)}</th>` : ''}<th scope="row" class="dv-concept">${escape(row.label)}</th>${data.meses.map(month => cell(value(item.meses[month.value],row),row.tipo)).join('')}${cell(value(item.resumen,row),row.tipo,'dv-period')}</tr>`).join('')).join('') + '</tbody></table>';
        }
    }
    function populate(options) {
        selects.filter(select => select.dataset.dvFilter !== 'direccion').forEach(select => {
            const key = select.dataset.dvFilter;
            const inherited = new URLSearchParams(baseQuery).getAll(key);
            select.innerHTML = `<option value="">${key === 'cliente_grupo' ? 'Todos los clientes' : inherited.length ? 'Según dashboard: ' + escape(inherited.join(', ')) : 'Todos'}</option>` + (options[key] || []).map(value => `<option value="${escape(value)}">${escape(value)}</option>`).join('');
        });
    }
    async function load(initial = false) {
        clearTimeout(timer);
        if (controller) controller.abort();
        controller = new AbortController();
        const current = ++version;
        const query = new URLSearchParams(baseQuery);
        selects.forEach(select => { if (select.value) { query.delete(select.dataset.dvFilter); query.append(select.dataset.dvFilter, select.value); } });
        if (el('dvSearch').value.trim()) query.set('buscar',el('dvSearch').value.trim());
        if (tab === 'campanias' || selectedCampaign) query.set('apertura','campanias');
        el('dvPanel').setAttribute('aria-busy','true');
        el('dvStatus').textContent = 'Consultando Facturación…';
        el('dvRetry').hidden = true;
        const advancedCount = [...el('dvAdvanced').querySelectorAll('select,input')].filter(input => input.value.trim()).length;
        el('dvFilterCount').textContent = advancedCount ? `(${advancedCount} activos)` : '';
        data = null;
        // Hide previous figures while a different selection is being loaded.
        el('dvPanel').replaceChildren();
        try {
            const response = await fetch('/api/dashboard/desvios?' + query.toString(), {signal:controller.signal});
            if (!response.ok) throw new Error('No se pudo consultar Facturación');
            const result = await response.json();
            if (!result.success || !Array.isArray(result.clientes)) throw new Error('Respuesta incompleta');
            if (current !== version || !dialog.open) return;
            data = result;
            if (initial) populate(result.opciones);
            render();
        } catch (error) {
            if (error.name === 'AbortError' || current !== version) return;
            data = null;
            el('dvStatus').textContent = 'No se pudo cargar la apertura. Reintentá la consulta.';
            el('dvRetry').hidden = false;
        } finally { if (current === version) el('dvPanel').setAttribute('aria-busy','false'); }
    }
    document.querySelectorAll('[data-open-desvios]').forEach(button => button.addEventListener('click', () => {
        trigger = button;
        baseQuery = contextQuery;
        data = null;
        tab = button.dataset.openDesvios === 'mensual' ? 'mensual' : 'clientes';
        compareAll = false;
        selectedCampaign = null;
        el('dvCampaignContext').hidden = true;
        el('dvDetail').checked = false;
        el('dvDetail').parentElement.hidden = true;
        el('dvScrollHint').hidden = true;
        el('dvAdvanced').open = false;
        dialog.querySelector('.dv-footer details').open = false;
        el('dvFilters').reset();
        selects.filter(select => select.dataset.dvFilter !== 'direccion').forEach(select => { select.innerHTML = '<option value="">Todos</option>'; });
        el('dvDirection').value = tab === 'mensual' ? '' : button.dataset.openDesvios;
        dialog.querySelectorAll('[data-dv-tab]').forEach(item => item.setAttribute('aria-selected', String(item.dataset.dvTab === tab)));
        el('dvCriteria').textContent = '';
        dialog.showModal();
        load(true);
    }));
    el('dvFilters').addEventListener('submit', event => event.preventDefault());
    selects.forEach(select => select.addEventListener('change', () => { compareAll = false; if (select.id === 'dvClient') selectedCampaign = null; load(); }));
    el('dvSearch').addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(() => load(),250); });
    el('dvDetail').addEventListener('change', render);
    el('dvReset').addEventListener('click', () => { el('dvFilters').reset(); compareAll = false; selectedCampaign = null; load(); });
    el('dvRetry').addEventListener('click', () => load(!data && !el('dvYear').options[1]));
    dialog.addEventListener('click', event => {
        const close = event.target.closest('[data-dv-close]');
        if (close) dialog.close();
        const button = event.target.closest('[data-dv-tab]');
        if (button) { tab = button.dataset.dvTab; selectedCampaign = null; if (tab === 'campanias') load(); else render(); }
        if (event.target.closest('[data-dv-back-campaigns]')) { selectedCampaign = null; tab = 'campanias'; render(); }
        if (event.target.closest('[data-dv-back-clients]')) { selectedCampaign = null; el('dvClient').value = ''; tab = 'clientes'; load(); }
        if (event.target.closest('[data-dv-compare]')) { compareAll = true; render(); }
        const client = event.target.closest('[data-dv-client]');
        if (client && data) { el('dvClient').value = data.clientes[Number(client.dataset.dvClient)].cliente; if (tab !== 'campanias') tab = 'mensual'; selectedCampaign = null; load(); }
        const campaigns = event.target.closest('[data-dv-client-campaigns]');
        if (campaigns && data) { el('dvClient').value = data.clientes[Number(campaigns.dataset.dvClientCampaigns)].cliente; tab = 'campanias'; selectedCampaign = null; load(); }
        const campaign = event.target.closest('[data-dv-campaign]');
        if (campaign && data) { selectedCampaign = data.clientes[0].campanias[Number(campaign.dataset.dvCampaign)]; tab = 'mensual'; render(); }
    });
    let outsideDown = false;
    const outside = event => { const rect = dialog.getBoundingClientRect(); return event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom; };
    dialog.addEventListener('pointerdown', event => { outsideDown = outside(event); });
    dialog.addEventListener('click', event => { if (event.target === dialog && outsideDown && outside(event)) dialog.close(); });
    dialog.addEventListener('close', () => { ++version; controller?.abort(); clearTimeout(timer); trigger?.focus(); });
    window.DashboardDesvios = {
        marcarCarga() {
            document.querySelectorAll('[data-open-desvios]').forEach(button => { button.disabled = true; });
        },
        actualizarContexto(clientes, query) {
            contextQuery = query;
            for (const [direction,prefix,sign] of [['positivo','Positive',1],['negativo','Negative',-1]]) {
                const filtered = clientes.filter(item => Number(item.desvio) * sign > .005);
                el('dv' + prefix + 'Count').textContent = filtered.length.toLocaleString('es-AR');
                el('dv' + prefix + 'Amount').textContent = money(filtered.reduce((sum,item) => sum + Number(item.desvio),0));
            }
            document.querySelectorAll('[data-open-desvios]').forEach(button => { button.disabled = false; });
        }
    };
})();
