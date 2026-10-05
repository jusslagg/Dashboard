(function () {
    'use strict';

    const idFiltro = /(?:^filtro|filtro$|Filtro|^buscar|Buscar|^year$|^yearSelect$|^reloj(?:Year|Desde|Hasta)$|^mesFiltro$|^(?:cliente|gerente|jefeSite|campania|tipoNegocio)Select$|^modoFilas$|^jefatura$|^periodoJefatura$|^bloque$|^signo$|^estado$|^umbral$)/;

    function esControlFiltro(elemento) {
        if (!(elemento instanceof HTMLElement)) return false;
        if (elemento.matches('[data-filter-control]')) return true;
        if (elemento.matches('input[type="search"]')) return true;
        if (elemento.matches('[data-dropdown-multiple] > button')) return true;
        if (!elemento.matches('input, select, button')) return false;
        return idFiltro.test(elemento.id || '');
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
            const grupo = control.closest('[data-filter-bar], .rs-tools, .grid, .flex');
            if (grupo) grupos.add(grupo);
        });
        grupos.forEach(grupo => {
            if (grupo.querySelectorAll('.app-filter-control').length > 1) grupo.classList.add('app-filter-row');
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
