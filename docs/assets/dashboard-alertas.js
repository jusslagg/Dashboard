(() => {
    'use strict';
    const container = document.getElementById('alertasDashboard');
    if (!container) return;
    const escape = value => String(value ?? '').replace(/[&<>"']/g,c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const normalized = value => String(value ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
    const number = value => Number(value).toLocaleString('es-AR',{minimumFractionDigits:2,maximumFractionDigits:2});
    const money = value => value == null ? '—' : `${value < 0 ? '−' : ''}$ ${number(Math.abs(value))}`;
    const description = alert => alert.importe != null ? 'El desvío acumulado de esta alerta es ' + money(alert.importe) + '.' : alert.cumplimiento != null ? 'El cumplimiento acumulado es ' + number(alert.cumplimiento) + '%.' : alert.detalle;
    const dialog = document.createElement('dialog');
    dialog.className = 'da-month-dialog'; dialog.setAttribute('aria-labelledby','daMonthTitle');
    document.body.appendChild(dialog);
    let monthlyTrigger;
    function monthCells(row) {
        return `<td class="${row.desvio < 0 ? 'da-negative' : row.desvio > 0 ? 'da-positive' : ''}">${money(row.desvio)}</td><td>${row.cumplimiento == null ? '—' : number(row.cumplimiento)+'%'}</td><td>${row.horas_facturadas == null ? '—' : number(row.horas_facturadas)+' / '+number(row.horas_objetivo)}</td>`;
    }
    function openMonthly(row,trigger) {
        monthlyTrigger = trigger;
        dialog.innerHTML = `<header><div><h2 id="daMonthTitle">${escape(row.campania || 'Sin campaña asignada')}</h2><p>${escape(row.cliente)} · ${escape(row.periodo)}</p></div><button type="button" data-da-close aria-label="Cerrar detalle mensual">×</button></header><p class="da-month-total">Desvío acumulado: <strong>${money(row.desvio)}</strong></p><div class="da-table-wrap"><table><thead><tr><th scope="col">Mes</th><th scope="col">Desvío mensual</th><th scope="col">Cumplimiento</th><th scope="col">Horas facturadas / objetivo</th></tr></thead><tbody>${row.meses.map(month=>`<tr><th scope="row">${escape(month.mes)}</th>${monthCells(month)}</tr>`).join('')}</tbody><tfoot><tr><th scope="row">Total del período</th>${monthCells(row)}</tr></tfoot></table></div><footer><p>Incluye todos los meses con registros de la selección, también los positivos. El cumplimiento acumulado se calcula sobre los totales, no promediando porcentajes.</p><button type="button" data-da-close>Volver al acumulado</button></footer>`;
        dialog.showModal();
    }
    dialog.addEventListener('click',event=>{if(event.target.closest('[data-da-close]'))dialog.close();});
    const outside = event => {const rect=dialog.getBoundingClientRect();return event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom;};
    let outsideDown=false;
    dialog.addEventListener('pointerdown',event=>{outsideDown=outside(event);});
    dialog.addEventListener('click',event=>{if(event.target===dialog&&outsideDown&&outside(event))dialog.close();});
    dialog.addEventListener('close',()=>{if(monthlyTrigger?.isConnected)monthlyTrigger.focus();});
    let states = [], query = '', revision = 0, busy = false;
    function stop() { if(dialog.open)dialog.close(); states.forEach(state => { state.controller?.abort(); state.details.open = false; }); }
    function draw(state) {
        const term = normalized(state.search);
        const matches = account => normalized(account.cliente).includes(term) || account.campanias.some(row => normalized(row.campania).includes(term));
        const accounts = state.data.clientes.filter(matches);
        const pages = Math.max(1,Math.ceil(accounts.length / 25));
        state.page = Math.min(state.page,pages);
        const start = (state.page-1)*25;
        const shown = accounts.slice(start,start+25);
        state.view.innerHTML = `<p class="da-count">Saldo neto de la selecci\u00f3n: <strong>${money(state.data.total_desvio)}</strong></p><p class="da-criterion">${escape(state.data.criterio_clientes || state.data.criterio)}</p><p class="da-count" role="status">${accounts.length ? `${start+1}–${Math.min(start+25,accounts.length)} de ${accounts.length} clientes` : 'Sin coincidencias para esta selección.'}</p>` + shown.map(account => {
            const index = state.data.clientes.indexOf(account);
            const clientMatches = normalized(account.cliente).includes(term);
            const campaigns = account.campanias.filter(row => clientMatches || normalized(row.campania).includes(term));
            const open = state.openClients.has(index) || (term && !clientMatches);
            return `<details class="da-client" data-da-client="${index}" ${open ? 'open' : ''}><summary><span class="da-client-name">${index+1}. ${escape(account.cliente)}<small>${escape(account.periodo || 'Sin registros')}</small></span><span class="${account.desvio < 0 ? 'da-negative' : account.desvio > 0 ? 'da-positive' : ''}">Acumulado: ${money(account.desvio)}</span><span class="da-client-compliance">Cumplimiento: ${account.cumplimiento == null ? '—' : number(account.cumplimiento)+'%'}</span><span class="da-client-action">Ver campañas (${account.campanias.length})</span></summary><div class="da-table-wrap"><table><thead><tr><th scope="col">Campaña · abrir meses</th><th scope="col">Período con registros</th><th scope="col">Desvío acumulado</th><th scope="col">Cumplimiento acumulado</th><th scope="col">Horas facturadas / objetivo</th></tr></thead><tbody>${campaigns.map(row => `<tr><th scope="row">${row.meses.length ? `<button type="button" class="da-campaign" data-da-account="${index}" data-da-monthly="${account.campanias.indexOf(row)}">${escape(row.campania || 'Sin campaña asignada')} →</button>` : escape(row.campania || 'Sin campaña asignada')}</th><td>${escape(row.periodo || 'Sin registros')}</td>${monthCells(row)}</tr>`).join('')}</tbody></table></div></details>`;
        }).join('') + (pages > 1 ? `<div class="da-pages"><button type="button" data-da-page="-1" ${state.page===1?'disabled':''}>Anterior</button><span>Página ${state.page} de ${pages}</span><button type="button" data-da-page="1" ${state.page===pages?'disabled':''}>Siguiente</button></div>` : '');
    }
    async function load(state) {
        if (busy || !state.details.open) return;
        if (state.data) { draw(state); return; }
        state.controller?.abort();
        const controller = new AbortController(); state.controller = controller;
        const current = revision;
        const timer = setTimeout(() => controller.abort(),30000);
        state.view.setAttribute('aria-busy','true');
        state.view.innerHTML = '<p class="da-count" role="status">Consultando clientes y campañas…</p>';
        try {
            const params = new URLSearchParams(query); params.set('alerta',state.type);
            const response = await fetch('/api/alertas/apertura?' + params.toString(),{signal:controller.signal});
            const data = await response.json();
            if (!response.ok || !data.success || !Array.isArray(data.clientes)) throw Error('Consulta incompleta');
            if (current !== revision || !state.details.open || controller !== state.controller) return;
            const hasDeviation = row => row.desvio != null && Math.abs(Number(row.desvio)) >= 0.005;
            state.data = {...data, clientes: data.clientes.filter(hasDeviation).map(account => ({
                ...account, campanias: account.campanias.filter(hasDeviation)
            }))};
            draw(state);
        } catch (error) {
            if (current !== revision || !state.details.open || controller !== state.controller) return;
            state.view.innerHTML = '<p role="status">No se pudo cargar la apertura.</p><button type="button" data-da-retry>Reintentar</button>';
        } finally { clearTimeout(timer); if (current===revision && controller===state.controller) state.view.setAttribute('aria-busy','false'); }
    }
    container.addEventListener('toggle',event => {
        const details = event.target;
        if (details.matches('[data-da-client]')) {
            const parent = details.closest('[data-da-alert]');
            const state = states[Number(parent.dataset.daAlert)];
            if (state) { const index = Number(details.dataset.daClient); if(details.open) state.openClients.add(index); else state.openClients.delete(index); }
            return;
        }
        if (!details.matches('[data-da-alert]')) return;
        const state = states[Number(details.dataset.daAlert)];
        if (!state || state.details !== details) return;
        if (details.open && !busy) {
            states.filter(item => item !== state).forEach(item => { item.details.open = false; item.controller?.abort(); });
            load(state);
        } else { state.controller?.abort(); if (busy) details.open = false; }
    },true);
    container.addEventListener('input',event => {
        const field = event.target.closest('[data-da-search]');
        if (!field) return;
        const state = states[Number(field.dataset.daSearch)];
        state.search = field.value; state.page = 1;
        if (state.data) draw(state);
    });
    container.addEventListener('click',event => {
        const details = event.target.closest('[data-da-alert]');
        if (!details) return;
        const state = states[Number(details.dataset.daAlert)];
        const page = event.target.closest('[data-da-page]');
        if (page && state.data) { state.page += Number(page.dataset.daPage); draw(state); }
        if (event.target.closest('[data-da-retry]')) load(state);
        const campaign=event.target.closest('[data-da-monthly]');
        if(campaign&&state.data)openMonthly(state.data.clientes[Number(campaign.dataset.daAccount)].campanias[Number(campaign.dataset.daMonthly)],campaign);
    });
    document.addEventListener('click',event => { if (!event.composedPath().includes(container)&&!event.composedPath().includes(dialog)) stop(); });
    window.DashboardAlertas = {
        marcarCarga() { busy = true; ++revision; stop(); container.dataset.updating = 'true'; container.setAttribute('aria-busy','true'); },
        renderizar(alertas,selectedQuery) {
            ++revision; stop(); busy = false; query = selectedQuery || ''; states = [];
            container.dataset.updating = 'false'; container.setAttribute('aria-busy','false');
            container.innerHTML = '<div class="da-heading"><h2>Alertas de la selección</h2><p>Cliente → campañas → desvío mensual.</p></div>' + alertas.map((alert,index) => `<article class="da-card da-${['danger','warning','success','info'].includes(alert.tipo)?alert.tipo:'info'}"><h3>${escape(alert.titulo)}</h3><p>${escape(description(alert))}</p>${alert.apertura === 'desvio' ? `<details data-da-alert="${index}"><summary>Ver clientes</summary><label class="da-search">Buscar cliente o campaña<input type="search" data-da-search="${index}" placeholder="Nombre del cliente o campaña" autocomplete="off"></label><div data-da-view="${index}"></div></details>` : ''}</article>`).join('');
            alertas.forEach((alert,index) => {
                const details = container.querySelector(`[data-da-alert="${index}"]`);
                if (details) states[index] = {details,type:alert.apertura,view:details.querySelector('[data-da-view]'),page:1,search:'',data:null,openClients:new Set()};
            });
        }
    };
})();
