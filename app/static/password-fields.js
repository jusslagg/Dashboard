// Cada campo conserva su valor y alterna su visibilidad de forma independiente.
document.querySelectorAll('input[type="password"]').forEach(input => {
    const wrapper = document.createElement('span');
    wrapper.className = 'password-field';
    input.before(wrapper);
    wrapper.append(input);

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'password-toggle';
    button.setAttribute('aria-controls', input.id);
    button.setAttribute('aria-label', 'Mostrar contraseña');
    button.setAttribute('aria-pressed', 'false');
    button.title = 'Mostrar contraseña';

    const icon = document.createElement('i');
    icon.className = 'fas fa-eye';
    icon.setAttribute('aria-hidden', 'true');
    button.append(icon);
    wrapper.append(button);

    button.addEventListener('click', event => {
        // Evita que una etiqueta contenedora active también el input.
        event.preventDefault();
        const visible = input.type === 'password';
        input.type = visible ? 'text' : 'password';
        button.setAttribute('aria-pressed', String(visible));
        button.setAttribute('aria-label', visible ? 'Ocultar contraseña' : 'Mostrar contraseña');
        button.title = button.getAttribute('aria-label');
        icon.className = visible ? 'fas fa-eye-slash' : 'fas fa-eye';
    });
});
