import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

// Exercise request races without a server or access to production data.
for (const file of ['docs/index.html', 'app/templates/index.html']) {
    const html = fs.readFileSync(file, 'utf8');
    const scripts = [...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)].map(match => match[1]);
    const source = scripts.find(script => script.includes('let chartEvolucion'));
    const elements = new Map();
    const element = id => {
        if (!elements.has(id)) elements.set(id, {
            textContent: '', dataset: {}, disabled: false,
            replaceChildren() {}, appendChild() {},
        });
        return elements.get(id);
    };
    const context = vm.createContext({
        document: { addEventListener() {}, querySelectorAll: () => [], getElementById: element, createElement: () => ({}) },
        URLSearchParams, AbortController, Date, setTimeout, clearTimeout, console,
    });
    vm.runInContext(source, context);
    vm.runInContext(`
        getFiltros = () => ({});
        buildQuery = () => '';
        var renders = [];
        actualizarKPIs = data => renders.push(data.id);
        actualizarGrafico = actualizarTablaResumen = actualizarTablaClientes = actualizarGraficoClientes = actualizarAlertas = () => {};
    `, context);
    const payload = id => ({ success: true, kpis: { id }, datos: [], resumen: [{}], clientes: [], alertas: [] });
    let release;
    context.fetch = () => new Promise(resolve => { (release ??= []).push(resolve); });
    const first = context.cargarDashboard();
    const oldResponses = release;
    release = undefined;
    const second = context.cargarDashboard();
    release.forEach(resolve => resolve({ ok: true, json: async () => payload('latest') }));
    await second;
    oldResponses.forEach(resolve => resolve({ ok: true, json: async () => payload('stale') }));
    await first;
    assert.deepEqual(Array.from(context.renders), ['latest'], 'Stale response must not render');
    assert.equal(element('estadoDashboard').dataset.state, 'success');
    assert.equal(element('btnActualizar').disabled, false);

    context.fetch = async () => ({ ok: false, status: 500 });
    await context.cargarDashboard();
    assert.equal(element('estadoDashboard').dataset.state, 'error');
    assert.equal(element('btnActualizar').disabled, false, 'Retry remains available');
    assert.equal(context.renders.length, 1, 'Failed response must preserve previous display');

    context.fetch = async () => ({ ok: true, json: async () => ({ ...payload('empty'), resumen: [] }) });
    await context.cargarDashboard();
    assert.match(element('estadoDashboard').textContent, /Sin registros/);
    context.fetch = async () => { throw new Error('offline'); };
    await context.actualizarVista();
    assert.equal(element('estadoDashboard').dataset.state, 'error');
    console.log(`${file}: latest response, HTTP error, empty result and retry OK`);
}

const listeners = {};
const form = {
    addEventListener: (type, callback) => { listeners[type] = callback; },
    querySelectorAll: () => [],
};
let unload;
const status = {};
vm.runInNewContext(fs.readFileSync('app/static/workspace.js', 'utf8'), {
    document: { getElementById: id => id === 'formCargar' ? form : status },
    window: { addEventListener: (_, callback) => { unload = callback; }, confirm: () => false },
});
let prevented = false;
const event = { preventDefault() { prevented = true; } };
unload(event);
assert.equal(prevented, false);
listeners.input();
unload(event);
assert.equal(prevented, true);
let stopped = false;
listeners.click({ target: { closest: () => ({}) }, preventDefault() {}, stopImmediatePropagation() { stopped = true; } });
assert.equal(stopped, true, 'Cancel must preserve form');
listeners.reset();
prevented = false;
unload(event);
assert.equal(prevented, false, 'Successful reset clears navigation warning');
console.log('Form: unsaved changes, cancelled clear and reset OK');

{
    const html = fs.readFileSync('docs/cargar.html', 'utf8');
    const source = [...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)].map(match => match[1]).find(script => script.includes('let asignaciones'));
    const fields = new Map();
    const getField = id => {
        if (!fields.has(id)) fields.set(id, { value: '10', disabled: false, reportValidity: () => true });
        return fields.get(id);
    };
    getField('importe_fijo').value = '';
    const controls = [getField('horas_objetivo'), getField('valor_hora')];
    let resolveSave;
    let requests = 0;
    let resets = 0;
    const context = vm.createContext({
        document: { addEventListener() {}, getElementById: getField, querySelectorAll: () => controls },
        fetch: () => { requests++; return new Promise(resolve => { resolveSave = resolve; }); },
        console,
    });
    vm.runInContext(source, context);
    vm.runInContext(`
        obtenerAsignacionSeleccionada = () => ({});
        valoresSeleccionados = () => ({});
        mostrarMensaje = () => {};
    `, context);
    context.limpiarFormulario = () => { resets++; };
    const event = { preventDefault() {} };
    const pending = context.guardarDatos(event);
    await context.guardarDatos(event);
    assert.equal(requests, 1, 'Repeated submit must not send a duplicate request');
    assert.equal(controls[0].disabled, true);
    resolveSave({ ok: false, json: async () => ({ success: false }) });
    await pending;
    assert.equal(resets, 0, 'Failure must preserve entered fields');
    assert.equal(controls[0].disabled, false);
    assert.equal(getField('horas_objetivo').value, '10');
    const retry = context.guardarDatos(event);
    resolveSave({ ok: true, json: async () => ({ success: true }) });
    await retry;
    assert.equal(resets, 1, 'Confirmed save resets once');
    console.log('Static form: duplicate submit, failed save preservation and successful retry OK');
}

for (const file of ['docs/index.html', 'docs/cargar.html', 'app/templates/index.html', 'app/templates/cargar.html']) {
    const html = fs.readFileSync(file, 'utf8');
    for (const match of html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)) {
        if (match[1].includes('{{') || match[1].includes('{%')) continue;
        new vm.Script(match[1], { filename: file });
    }
}
assert.equal(fs.readFileSync('app/static/workspace.js', 'utf8'), fs.readFileSync('docs/assets/workspace.js', 'utf8'));
console.log('Inline JavaScript syntax and shared assets OK');
