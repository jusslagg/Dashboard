import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

const cookie = (await readFile('.cache/session-cookie.txt', 'utf8')).trim();
const tabs = await (await fetch('http://127.0.0.1:9241/json/list')).json();
const ws = new WebSocket(tabs.find(tab => tab.type === 'page').webSocketDebuggerUrl);
await new Promise(resolve => ws.addEventListener('open', resolve, {once: true}));
let id = 0;
const pending = new Map();
const errors = [];
ws.addEventListener('message', event => {
  const message = JSON.parse(event.data);
  if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.text);
  if (pending.has(message.id)) {
    const promise = pending.get(message.id);
    pending.delete(message.id);
    message.error ? promise.reject(message.error) : promise.resolve(message.result);
  }
});
const send = (method, params = {}) => new Promise((resolve, reject) => {
  pending.set(++id, {resolve, reject});
  ws.send(JSON.stringify({id, method, params}));
});
const run = async expression => {
  const response = await send('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
  if (response.exceptionDetails) throw new Error(JSON.stringify(response.exceptionDetails));
  return response.result.value;
};

try {
  await send('Runtime.enable');
  await send('Page.enable');
  await send('Network.enable');
  await send('Network.setCookie', {name: 'session', value: cookie, url: 'http://127.0.0.1:8009', httpOnly: true, sameSite: 'Lax'});
  await send('Page.navigate', {url: 'http://127.0.0.1:8009/resumen'});
  for (let attempt = 0; attempt < 200; attempt += 1) {
    if (await run("typeof filas !== 'undefined' && filas.length > 0 && gruposFiltro.length > 0")) break;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  const summary = await run(`(() => {
    const options = () => [...filtroCampania.options].map(option => option.textContent);
    const groups = gruposFiltro.map(group => group.nombre);
    const states = {};
    for (const group of groups) {
      seleccionarGrupo(group);
      states[group] = {
        label: filtroClienteLabel.textContent,
        campaigns: options(),
        total: kpiTotalFiltrado.textContent,
        rows: tbodyResumen.querySelectorAll('tr').length,
        chip: activeFilterChips.textContent.trim(),
      };
    }
    limpiarFiltros();
    return {groups, states, options: options(), concepts: [...filtroConcepto.options].map(option => option.textContent)};
  })()`);
  assert.deepEqual(summary.groups, ['Getnet', 'Personal', 'Santander']);
  assert(!summary.options.includes('TOTAL CAT'));
  assert(!summary.options.includes('TOTAL GRUPO PERSONAL'));
  assert(summary.concepts.includes('Horas'));
  assert(summary.states.Getnet.campaigns.includes('Santander Getnet'));
  assert(summary.states.Getnet.campaigns.includes('Santander Getnet Onboarding'));
  assert(!summary.states.Getnet.campaigns.includes('Santander Getnet Supervisor exclusivo'));
  assert(summary.states.Santander.campaigns.includes('Santander Getnet Supervisor exclusivo'));
  assert(summary.states.Personal.rows > 1);

  await send('Page.navigate', {url: 'http://127.0.0.1:8009/catalogos'});
  for (let attempt = 0; attempt < 200; attempt += 1) {
    if (await run("typeof asignacionesCatalogo !== 'undefined' && asignacionesCatalogo.length > 0")) break;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  const masters = await run(`(() => ({
    field: !!document.getElementById('grupo_facturacion'),
    filter: !!document.getElementById('filtroGrupoFacturacionCatalogo'),
    groups: [...document.getElementById('gruposFacturacionDisponibles').options].map(option => option.value),
    badges: [...document.querySelectorAll('#tablaAsignaciones span')].map(span => span.textContent.trim()),
  }))()`);
  assert(masters.field && masters.filter);
  assert(masters.groups.includes('Personal') && masters.groups.includes('Getnet') && masters.groups.includes('Santander'));
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({summary, masters, errors}, null, 2));
} finally {
  await send('Browser.close');
  ws.close();
}
