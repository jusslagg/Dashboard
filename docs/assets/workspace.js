(function () {
    const form = document.getElementById('formCargar');
    if (!form) return;
    let changed = false;
    const status = document.getElementById('estadoFormulario');
    function update(value) {
        changed = value;
        if (status) status.textContent = changed ? 'Tiene cambios sin guardar.' : 'Complete los campos obligatorios y revise los cálculos antes de guardar.';
    }
    form.addEventListener('input', () => update(true));
    form.addEventListener('change', () => update(true));
    form.addEventListener('reset', () => update(false));
    window.addEventListener('beforeunload', event => {
        if (!changed) return;
        event.preventDefault();
        event.returnValue = '';
    });
    form.addEventListener('click', event => {
        const clear = event.target.closest('button[onclick="limpiarFormulario()"]');
        if (clear && changed && !window.confirm('¿Descartar los cambios sin guardar de este formulario?')) {
            event.preventDefault();
            event.stopImmediatePropagation();
        }
    }, true);
    // Associate visible labels with their controls for keyboard and screen reader users.
    form.querySelectorAll('label:not([for])').forEach(label => {
        const control = label.parentElement.querySelector('input[id], select[id]');
        if (control) label.htmlFor = control.id;
    });
}());
