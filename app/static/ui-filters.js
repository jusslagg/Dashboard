(function () {
    'use strict';

    // Shared by screens: an empty selection means all values.
    const control = origen => typeof origen === 'string' ? document.getElementById(origen) : origen;
    const valores = origen => [...(control(origen)?.selectedOptions || [])].map(opcion => opcion.value).filter(valor => valor !== '' && valor !== 'todos');
    const coincide = (seleccion, valor) => !seleccion.length || seleccion.includes(String(valor ?? ''));
    const seleccionar = (origen, seleccion) => {
        const elemento = control(origen);
        const elegidos = new Set(Array.isArray(seleccion) ? seleccion.map(String) : seleccion ? [String(seleccion)] : []);
        [...elemento.options].forEach(opcion => { opcion.selected = elegidos.has(opcion.value); });
        elemento.dispatchEvent(new Event('app-filter-sync'));
    };
    window.AppFilters = { valores, coincide, seleccionar,
        agregar: (params, nombre, seleccion) => seleccion.forEach(valor => params.append(nombre, valor)),
    };

    const idFiltro = /(?:^filtro|filtro$|Filtro|^buscar|Buscar)/;
    const selectoresFiltro = new Set([
        'year', 'yearSelect', 'anio', 'mesFiltro', 'estadoFiltro', 'metricaFiltro',
        'relojYear', 'relojDesde', 'relojHasta', 'modoFilas', 'jefatura',
        'periodoJefatura', 'bloque', 'signo', 'estado', 'orden', 'desde', 'hasta',
        'baseComparacion', 'baseYear', 'actualYear', 'normalizacionYear',
        'selectorCierreTraficoControl', 'pvfYear', 'pvfDesde', 'pvfHasta',
        'pvfSite', 'pvfCliente', 'pvfServicio', 'pvfMetrica',
    ]);
    const valoresFiltro = new Set(['umbral', 'minimo', 'maximo', 'desde', 'hasta']);

    function esControlFiltro(elemento) {
        if (!(elemento instanceof HTMLElement)) return false;
        if (elemento.closest('.app-filter-dialog') || elemento.matches('[data-app-filter-trigger]')) return false;
        if (elemento.matches('[data-filter-control]')) return true;
        if (elemento.matches('input[type="search"]')) return true;
        if (elemento.matches('[data-dropdown-multiple] > button')) return true;
        if (elemento.closest('[data-filter-scope]') && elemento.matches('button[aria-expanded]')) return true;
        if (elemento.closest('[data-filter-scope]') && elemento.matches('select, input[type="text"], input[type="search"], input[type="number"], input[type="month"]')) return true;
        if (elemento.closest('[data-filter-bar], .app-filter-bar, .rs-tools') && elemento.matches('select')) return true;
        if (!elemento.matches('input, select, button')) return false;
        const id = elemento.id || '';
        if (idFiltro.test(id)) return true;
        if (elemento.matches('select') && selectoresFiltro.has(id)) return true;
        return elemento.matches('input') && valoresFiltro.has(id);
    }

    function prepararControl(elemento) {
        if (!esControlFiltro(elemento)) return;
        elemento.classList.add('app-filter-control');
        if (elemento.matches('[data-dropdown-multiple] > button')) elemento.classList.add('app-filter-trigger');
        const desplegable = elemento.closest('[data-dropdown-multiple]');
        const etiqueta = elemento.closest('label') || desplegable?.parentElement?.querySelector(':scope > label');
        etiqueta?.classList.add('app-filter-label');
        if (desplegable && etiqueta) {
            elemento.dataset.filterName = etiqueta.textContent.trim();
            if (elemento.closest('.app-filter-panel')) etiqueta.classList.add('app-filter-caption');
        }
        desplegable?.querySelector(':scope > div[id^="panel"]')?.classList.add('app-filter-popover');
        if (elemento.matches('select') && !elemento.dataset.appFilterNative) prepararSelector(elemento);
    }

    let dialogo;
    let filtroActivo = null;
    let focoAnterior = null;

    function nombreFiltro(elemento) {
        if (elemento.dataset.filterName) return elemento.dataset.filterName;
        const etiqueta = elemento.closest('label')
            || (elemento.id ? document.querySelector(`label[for="${CSS.escape(elemento.id)}"]`) : null)
            || elemento.closest('[data-dropdown-multiple]')?.parentElement?.querySelector(':scope > label');
        if (etiqueta) {
            const copia = etiqueta.cloneNode(true);
            copia.querySelectorAll('select, input, button, option').forEach(nodo => nodo.remove());
            const nombre = copia.textContent.trim();
            if (nombre) return nombre;
        }
        const nombres = {
            year: 'Año', yearSelect: 'Año', anio: 'Año', yearFiltro: 'Año', relojYear: 'Año',
            mes: 'Mes', mesFiltro: 'Mes', cliente: 'Cliente', clienteSelect: 'Cliente',
            gerente: 'Gerente', gerenteSelect: 'Gerente', jefeSiteSelect: 'Jefe de Site',
            campania: 'Campaña', campaniaSelect: 'Campaña', tipoNegocioSelect: 'Tipo de negocio',
            modoFilas: 'Vista', bloque: 'Bloque', jefatura: 'Jefatura', periodoJefatura: 'Período',
            signo: 'Resultado', estado: 'Estado', orden: 'Orden', normalizacionYear: 'Año',
        };
        if (nombres[elemento.id]) return nombres[elemento.id];
        const primera = elemento.matches('select') ? elemento.options[0]?.textContent.trim() : '';
        const derivado = primera?.replace(/^(?:todos?|todas?|seleccionar)\s+(?:los?|las?|el|la)?\s*/i, '').trim();
        if (derivado && derivado !== primera) return derivado;
        return elemento.getAttribute('aria-label') || elemento.getAttribute('title') || 'Opciones';
    }

    function prepararSelector(select) {
        if (select.closest('[data-dropdown-multiple]')) return;
        select.dataset.appFilterNative = 'true';
        select.classList.add('app-filter-native-select');
        const boton = document.createElement('button');
        boton.type = 'button';
        boton.className = 'app-filter-control app-filter-select-trigger';
        boton.dataset.appFilterTrigger = 'true';
        boton.dataset.filterName = nombreFiltro(select);
        boton.setAttribute('aria-haspopup', 'dialog');
        boton.setAttribute('aria-label', `Filtrar por ${boton.dataset.filterName}`);
        boton.addEventListener('click', () => abrirFiltro({ tipo: 'select', origen: select, disparador: boton }));
        select.insertAdjacentElement('afterend', boton);
        const actualizar = () => {
            boton.dataset.filterName = nombreFiltro(select);
            boton.setAttribute('aria-label', `Filtrar por ${boton.dataset.filterName}`);
            const elegidas = [...select.selectedOptions].filter(opcion => opcion.value !== '' && opcion.value !== 'todos');
            boton.textContent = select.multiple
                ? (elegidas.length > 1 ? `${elegidas.length} seleccionados` : elegidas[0]?.textContent?.trim() || select.options[0]?.textContent?.trim() || 'Todos')
                : select.selectedOptions[0]?.textContent?.trim() || 'Seleccionar';
            boton.disabled = select.disabled;
            boton.hidden = select.hidden || select.classList.contains('hidden') || select.style.display === 'none';
        };
        actualizar();
        select.addEventListener('change', actualizar);
        select.addEventListener('app-filter-sync', actualizar);
        // Screen shortcuts and reset buttons assign .value without a change event.
        const propiedadValor = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value');
        Object.defineProperty(select, 'value', {
            configurable: true,
            get() { return propiedadValor.get.call(this); },
            set(valor) { propiedadValor.set.call(this, valor); actualizar(); },
        });
        new MutationObserver(actualizar).observe(select, { childList: true, subtree: true, characterData: true });
        new MutationObserver(actualizar).observe(select, { attributes: true, attributeFilter: ['class', 'style', 'hidden', 'disabled'] });
    }

    function asegurarDialogo() {
        if (dialogo) return dialogo;
        dialogo = document.createElement('div');
        dialogo.className = 'app-filter-dialog';
        dialogo.hidden = true;
        dialogo.innerHTML = `
            <div class="app-filter-dialog-card" role="dialog" aria-modal="true" aria-labelledby="appFilterTitle">
                <h2 id="appFilterTitle"></h2>
                <input class="app-filter-dialog-search" type="search" placeholder="Buscar opciones..." aria-label="Buscar opciones">
                <div class="app-filter-dialog-tools">
                    <button type="button" data-filter-all>Seleccionar todo</button>
                    <button type="button" data-filter-clear>Quitar selección</button>
                </div>
                <div class="app-filter-dialog-options" role="group"></div>
                <div class="app-filter-dialog-count" aria-live="polite"></div>
                <div class="app-filter-dialog-footer">
                    <button type="button" class="app-filter-dialog-cancel" data-filter-cancel>Cancelar</button>
                    <button type="button" class="app-filter-dialog-apply" data-filter-apply>Aplicar filtro</button>
                </div>
            </div>`;
        document.body.appendChild(dialogo);
        dialogo.addEventListener('click', event => {
            if (event.target === dialogo || event.target.closest('[data-filter-cancel]')) cerrarFiltro();
            if (event.target.closest('[data-filter-apply]')) aplicarFiltro();
            if (event.target.closest('[data-filter-clear]')) {
                if (!filtroActivo) return;
                filtroActivo.seleccion.clear();
                pintarOpciones();
            }
            if (event.target.closest('[data-filter-all]')) {
                if (!filtroActivo) return;
                filtroActivo.opciones.forEach(opcion => filtroActivo.seleccion.add(opcion.valor));
                pintarOpciones();
            }
        });
        dialogo.querySelector('.app-filter-dialog-search').addEventListener('input', pintarOpciones);
        dialogo.querySelector('.app-filter-dialog-options').addEventListener('change', event => {
            if (!filtroActivo || !event.target.matches('input[data-filter-option]')) return;
            const valor = event.target.value;
            if (filtroActivo.tipo === 'select' && !filtroActivo.origen.multiple) filtroActivo.seleccion.clear();
            if (event.target.checked) filtroActivo.seleccion.add(valor);
            else filtroActivo.seleccion.delete(valor);
            pintarOpciones();
        });
        dialogo.addEventListener('keydown', event => {
            if (event.key === 'Escape') {
                event.preventDefault();
                cerrarFiltro();
            }
            if (event.key !== 'Tab') return;
            const focos = [...dialogo.querySelectorAll('input:not([disabled]), button:not([disabled])')]
                .filter(elemento => elemento.offsetParent !== null);
            if (!focos.length) return;
            if (event.shiftKey && document.activeElement === focos[0]) {
                event.preventDefault();
                focos[focos.length - 1].focus();
            } else if (!event.shiftKey && document.activeElement === focos[focos.length - 1]) {
                event.preventDefault();
                focos[0].focus();
            }
        });
        return dialogo;
    }

    function abrirFiltro({ tipo, origen, disparador }) {
        if (filtroActivo) cerrarFiltro();
        const modal = asegurarDialogo();
        const opciones = tipo === 'multiple'
            ? [...origen.querySelectorAll('input[type="checkbox"]:not([data-todos])')].map(input => ({
                valor: input.value, etiqueta: input.closest('label')?.querySelector('span')?.textContent?.trim() || input.value,
            }))
            : [...origen.options].filter(option => (!option.disabled || option.selected) && (!origen.multiple || (option.value !== '' && option.value !== 'todos'))).map(option => ({
                valor: option.value, etiqueta: option.textContent.trim(),
            }));
        const seleccion = tipo === 'multiple'
            ? new Set([...origen.querySelectorAll('input[type="checkbox"]:not([data-todos]):checked')].map(input => input.value))
            : new Set(origen.multiple ? valores(origen) : [origen.value]);
        filtroActivo = { tipo, origen, disparador, opciones, seleccion };
        focoAnterior = disparador;
        modal.querySelector('#appFilterTitle').textContent = `Filtrar por ${nombreFiltro(disparador)}`;
        modal.querySelector('[data-filter-all]').hidden = tipo !== 'multiple' && !origen.multiple;
        modal.querySelector('[data-filter-clear]').hidden = tipo === 'select' && !origen.multiple && !opciones.some(opcion => opcion.valor === '');
        modal.querySelector('.app-filter-dialog-search').value = '';
        modal.hidden = false;
        document.body.classList.add('app-filter-dialog-open');
        disparador.setAttribute('aria-expanded', 'true');
        pintarOpciones();
        modal.querySelector('.app-filter-dialog-search').focus();
    }

    function pintarOpciones() {
        if (!filtroActivo) return;
        const modal = asegurarDialogo();
        const busqueda = modal.querySelector('.app-filter-dialog-search').value.trim().toLocaleLowerCase('es');
        const contenedor = modal.querySelector('.app-filter-dialog-options');
        contenedor.replaceChildren();
        const visibles = filtroActivo.opciones.filter(opcion => opcion.etiqueta.toLocaleLowerCase('es').includes(busqueda));
        visibles.forEach(opcion => {
            const etiqueta = document.createElement('label');
            etiqueta.className = 'app-filter-dialog-option';
            const input = document.createElement('input');
            input.type = filtroActivo.tipo === 'select' && !filtroActivo.origen.multiple ? 'radio' : 'checkbox';
            input.name = 'app-filter-option';
            input.dataset.filterOption = 'true';
            input.value = opcion.valor;
            input.checked = filtroActivo.seleccion.has(opcion.valor);
            const texto = document.createElement('span');
            texto.textContent = opcion.etiqueta;
            etiqueta.append(input, texto);
            contenedor.appendChild(etiqueta);
        });
        if (!visibles.length) {
            const vacio = document.createElement('p');
            vacio.className = 'app-filter-dialog-empty';
            vacio.textContent = 'No hay opciones para esta búsqueda.';
            contenedor.appendChild(vacio);
        }
        const cantidad = [...filtroActivo.seleccion].filter(valor => valor !== '').length;
        modal.querySelector('.app-filter-dialog-count').textContent =
            `${cantidad} ${cantidad === 1 ? 'opción seleccionada' : 'opciones seleccionadas'}`;
    }

    function cerrarFiltro() {
        if (!filtroActivo) return;
        filtroActivo.disparador.setAttribute('aria-expanded', 'false');
        filtroActivo = null;
        dialogo.hidden = true;
        document.body.classList.remove('app-filter-dialog-open');
        focoAnterior?.focus();
        focoAnterior = null;
    }

    function aplicarFiltro() {
        if (!filtroActivo) return;
        const { tipo, origen, seleccion } = filtroActivo;
        if (tipo === 'multiple') {
            const inputs = [...origen.querySelectorAll('input[type="checkbox"]:not([data-todos])')];
            const valoresAntes = inputs.filter(input => input.checked).map(input => input.value);
            inputs.forEach(input => { input.checked = seleccion.has(input.value); });
            const todos = origen.querySelector('input[data-todos]');
            if (todos) todos.checked = inputs.length > 0 && inputs.every(input => input.checked);
            const valoresDespues = inputs.filter(input => input.checked).map(input => input.value);
            cerrarFiltro();
            if (valoresAntes.join('\u0000') !== valoresDespues.join('\u0000') && (inputs[0] || todos)) {
                (inputs[0] || todos).dispatchEvent(new Event('change', { bubbles: true }));
            }
        } else {
            if (origen.multiple) {
                const antes = valores(origen);
                seleccionar(origen, [...seleccion]);
                const cambio = antes.join('\u0000') !== valores(origen).join('\u0000');
                cerrarFiltro();
                if (cambio) origen.dispatchEvent(new Event('change', { bubbles: true }));
                return;
            }
            const valor = [...seleccion][0] ?? '';
            const cambio = origen.value !== valor;
            cerrarFiltro();
            if (cambio) {
                origen.value = valor;
                origen.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }
    }

    function prepararGrupos(raiz) {
        const grupos = new Set();
        raiz.querySelectorAll?.('.app-filter-control').forEach(control => {
            const alcance = control.closest('[data-filter-scope]');
            const grupoSemantico = control.closest('[data-filter-bar], .rs-tools');
            const grupoVisual = alcance ? control.closest('.grid, .flex') : null;
            const grupo = grupoSemantico
                || (grupoVisual && alcance.contains(grupoVisual) ? grupoVisual : alcance);
            if (grupo) grupos.add(grupo);
        });
        grupos.forEach(grupo => {
            if (grupo.matches('body, #appShell, #sidebar, main')) return;
            if (grupo.querySelectorAll('.app-filter-control').length > 1) {
                grupo.classList.add('app-filter-row');
                grupo.querySelectorAll('button:not(.app-filter-trigger):not(.app-filter-tab)').forEach(boton => {
                    boton.classList.add('app-filter-action');
                    if (boton.parentElement !== grupo) boton.parentElement?.classList.add('app-filter-actions');
                });
            }
        });
        document.querySelectorAll('#appShell, #sidebar, main').forEach(contenedor => {
            contenedor.classList.remove('app-filter-row', 'app-filter-actions');
        });
    }

    function prepararFiltros(raiz = document) {
        if (raiz instanceof HTMLElement) prepararControl(raiz);
        raiz.querySelectorAll?.('input, select, button').forEach(prepararControl);
        prepararGrupos(raiz === document ? document : raiz.closest('main') || raiz);
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => prepararFiltros());
    else prepararFiltros();

    document.addEventListener('click', event => {
        const disparador = event.target.closest('[data-dropdown-multiple="true"] > button');
        if (!disparador) return;
        const origen = disparador.parentElement.querySelector('[data-lista-multiple="true"]');
        if (!origen) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        abrirFiltro({ tipo: 'multiple', origen, disparador });
    }, true);

    new MutationObserver(mutaciones => {
        mutaciones.forEach(mutacion => mutacion.addedNodes.forEach(nodo => {
            if (nodo.nodeType === Node.ELEMENT_NODE) prepararFiltros(nodo);
        }));
    }).observe(document.documentElement, { childList: true, subtree: true });
}());
