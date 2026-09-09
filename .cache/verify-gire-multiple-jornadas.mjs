import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const cookie = (await readFile('.cache/session-cookie.txt', 'utf8')).trim();
const tabs = await (await fetch('http://127.0.0.1:9243/json/list')).json();
const socket = new WebSocket(tabs.find(tab => tab.type === 'page').webSocketDebuggerUrl);
await new Promise(resolve => socket.addEventListener('open', resolve, { once: true }));

let id = 0;
const pending = new Map();
const errors = [];
socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.method === 'Runtime.exceptionThrown') {
        errors.push(message.params.exceptionDetails.exception?.description || message.params.exceptionDetails.text);
    }
    if (pending.has(message.id)) {
        const operation = pending.get(message.id);
        pending.delete(message.id);
        message.error ? operation.reject(message.error) : operation.resolve(message.result);
    }
});
const send = (method, params = {}) => new Promise((resolve, reject) => {
    pending.set(++id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params }));
});
const evaluate = async expression => {
    const result = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
};
const waitFor = async expression => {
    for (let attempt = 0; attempt < 200; attempt++) {
        if (await evaluate(expression)) return;
        await new Promise(resolve => setTimeout(resolve, 100));
    }
    throw new Error(`No se cumplio: ${expression}`);
};

try {
    await send('Runtime.enable');
    await send('Page.enable');
    await send('Network.enable');
    await send('Network.setCookie', {
        name: 'session', value: cookie, url: 'http://127.0.0.1:8009', httpOnly: true, sameSite: 'Lax'
    });
    await send('Page.navigate', { url: 'http://127.0.0.1:8009/matriz-proyecciones' });
    await waitFor(`typeof editarProyeccion === 'function' && Array.isArray(proyecciones) && proyecciones.some(item => item.id === 35)`);

    const setup = await evaluate(`(() => {
        editarProyeccion(35);
        const filas = [...document.querySelectorAll('.jornada-row')];
        const valores = [[11, 6, 'L a V'], [6, 5, 'S']];
        filas.forEach((fila, index) => {
            fila.querySelector('[data-field="dotacion"]').value = valores[index][0];
            fila.querySelector('[data-field="horas"]').value = valores[index][1];
            fila.querySelector('[data-field="carga"]').value = valores[index][2];
        });
        actualizarDesdeJornadas();
        window.__postCapturado = null;
        const fetchOriginal = window.fetch;
        window.fetch = async (url, options = {}) => {
            if (url === '/api/matriz-proyecciones' && options.method === 'POST') {
                window.__postCapturado = JSON.parse(options.body);
                return new Response('<html>Prohibido</html>', { status: 403, headers: { 'Content-Type': 'text/html' } });
            }
            return fetchOriginal(url, options);
        };
        const formulario = document.getElementById('formProyeccion');
        const invalidos = [...formulario.elements].filter(campo => !campo.checkValidity()).map(campo => ({
            id: campo.id, value: campo.value, validationMessage: campo.validationMessage
        }));
        formulario.requestSubmit();
        return { filas: filas.length, invalidos, textoBoton: document.getElementById('guardarProyeccionBtn').textContent.trim() };
    })()`);

    assert.equal(setup.filas, 2);
    assert.deepEqual(setup.invalidos, []);
    assert.match(setup.textoBoton, /Guardando/);
    await waitFor(`window.__postCapturado && !document.getElementById('guardarProyeccionBtn').disabled && !document.getElementById('mensajeProyeccion').classList.contains('hidden')`);
    const result = await evaluate(`({
        jornadas: window.__postCapturado.jornadas,
        desdeMes: window.__postCapturado.mes,
        mensaje: document.getElementById('mensajeProyeccion').textContent.trim(),
        botonHabilitado: !document.getElementById('guardarProyeccionBtn').disabled,
        textoBoton: document.getElementById('guardarProyeccionBtn').textContent.trim()
    })`);
    assert.equal(result.jornadas.length, 2);
    assert.deepEqual(result.jornadas.map(jornada => [jornada.dotacion_requerida, jornada.carga_horaria, jornada.carga_semanal]), [
        [11, 6, 'L a V'], [6, 5, 'S']
    ]);
    assert.equal(result.desdeMes, '2026-06');
    assert.match(result.mensaje, /permiso Edici.n/i);
    assert.equal(result.botonHabilitado, true);
    assert.match(result.textoBoton, /Guardar proyecci.n/i);
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ setup, result, errors }));
} finally {
    await send('Browser.close');
    socket.close();
}
