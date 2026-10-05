(function () {
    'use strict';

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
        if (elemento.matches('[data-filter-control]')) return true;
        if (elemento.matches('input[type="search"]')) return true;
        if (elemento.matches('[data-dropdown-multiple] > button')) return true;
        if (elemento.closest('[data-filter-scope]') && elemento.matches('button[aria-expanded]')) return true;
        if (elemento.closest('[data-filter-scope]') && elemento.matches('select, input[type="text"], input[type="search"], input[type="number"], input[type="month"]')) return true;
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
        desplegable?.querySelector(':scope > div[id^="panel"]')?.classList.add('app-filter-popover');
    }

    function prepararGrupos(raiz) {
        const grupos = new Set();
        raiz.querySelectorAll?.('.app-filter-control').forEach(control => {
            const grupo = control.closest('[data-filter-bar], [data-filter-scope], .rs-tools, .grid, .flex');
            if (grupo) grupos.add(grupo);
        });
        grupos.forEach(grupo => {
            if (grupo.querySelectorAll('.app-filter-control').length > 1) {
                grupo.classList.add('app-filter-row');
                grupo.querySelectorAll('button:not(.app-filter-trigger):not(.app-filter-tab)').forEach(boton => {
                    boton.classList.add('app-filter-action');
                });
            }
        });
    }

    function prepararFiltros(raiz = document) {
        if (raiz instanceof HTMLElement) prepararControl(raiz);
        raiz.querySelectorAll?.('input, select, button').forEach(prepararControl);
        prepararGrupos(raiz === document ? document : raiz.closest('main') || raiz);
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => prepararFiltros());
    else prepararFiltros();

    new MutationObserver(mutaciones => {
        mutaciones.forEach(mutacion => mutacion.addedNodes.forEach(nodo => {
            if (nodo.nodeType === Node.ELEMENT_NODE) prepararFiltros(nodo);
        }));
    }).observe(document.documentElement, { childList: true, subtree: true });
}());
