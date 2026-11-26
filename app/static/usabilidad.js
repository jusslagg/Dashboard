(() => {
    const nav = document.getElementById('sidebarNav');
    const search = document.getElementById('buscarPantalla');
    const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
    const groups = [...nav.querySelectorAll('[data-sidebar-group]')];
    const initial = new Map();
    const active = nav.querySelector('.sidebar-link.active');
    if (active) {
        active.setAttribute('aria-current', 'page');
        const group = active.closest('[data-sidebar-group]');
        if (group) {
            group.querySelector('.sidebar-group-content').hidden = false;
            group.querySelector('.sidebar-group-toggle').setAttribute('aria-expanded', 'true');
        }
    }
    search.addEventListener('input', () => {
        const query = normalize(search.value);
        let matches = 0;
        groups.forEach(group => {
            const content = group.querySelector('.sidebar-group-content');
            const toggle = group.querySelector('.sidebar-group-toggle');
            if (!initial.has(group)) initial.set(group, content.hidden);
            const links = [...group.querySelectorAll('.sidebar-link')];
            links.forEach(link => {
                link.hidden = Boolean(query) && !normalize(link.textContent + ' ' + toggle.textContent).includes(query);
                if (!link.hidden) matches++;
            });
            group.hidden = !links.some(link => !link.hidden);
            content.hidden = query ? false : initial.get(group);
            toggle.setAttribute('aria-expanded', String(!content.hidden));
        });
        document.getElementById('sinPantallas').hidden = matches > 0;
        if (!query) initial.clear();
    });
    search.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            search.value = '';
            search.dispatchEvent(new Event('input'));
        }
    });

    const main = document.getElementById('contenidoPrincipal');
    // Formularios con una explicación y un bloque de carga de archivos.
    main.querySelectorAll('div[class*="flex-row"]').forEach(row => {
        const controls = [...row.children].find(child =>
            child.tagName === 'DIV' && child.querySelector('input[type=file]'));
        if (controls && row.children.length === 2) {
            row.classList.add('app-form-row');
            controls.classList.add('app-form-controls');
        }
    });
    const observer = new ResizeObserver(entries => {
        entries.forEach(({target}) => {
            const scrollable = target.scrollWidth > target.clientWidth + 2;
            target.tabIndex = scrollable ? 0 : -1;
            target.setAttribute('aria-label', scrollable ? 'Tabla de datos. Desplazate horizontalmente para ver todas las columnas.' : 'Tabla de datos');
            const note = target.previousElementSibling;
            if (note?.classList.contains('app-scroll-note')) note.hidden = !scrollable;
        });
    });
    main.querySelectorAll('.overflow-auto, .overflow-x-auto').forEach(wrapper => {
        if (!wrapper.querySelector('table') || wrapper.querySelector('.app-table-scroll')) return;
        wrapper.classList.add('app-table-scroll');
        wrapper.setAttribute('role', 'region');
        const note = document.createElement('p');
        note.className = 'app-scroll-note';
        note.textContent = 'Desplazá la tabla para ver todas las columnas.';
        note.hidden = true;
        wrapper.before(note);
        observer.observe(wrapper);
    });
    main.addEventListener('change', event => {
        if (event.target.matches('input[type=file]')) {
            event.target.title = [...event.target.files].map(file => file.name).join(', ');
        }
    });
})();
