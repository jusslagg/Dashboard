import {readFile} from 'node:fs/promises';

const cookie = (await readFile('.cache/session-cookie.txt', 'utf8')).trim();
const tabs = await (await fetch('http://127.0.0.1:9240/json/list')).json();
const ws = new WebSocket(tabs.find(tab => tab.type === 'page').webSocketDebuggerUrl);
await new Promise(resolve => ws.addEventListener('open', resolve, {once: true}));
let id = 0;
const pending = new Map();
const errors = [];
ws.addEventListener('message', event => {
  const message = JSON.parse(event.data);
  if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails);
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
    if (await run("typeof filas !== 'undefined' && filas.length > 0")) break;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  const result = await run(`(() => {
    const read = label => ({
      label,
      clients: [...clientesSeleccionados],
      campaigns: [...filtroCampania.options].map(option => option.textContent),
      total: kpiTotalFiltrado.textContent,
      rows: tbodyResumen.querySelectorAll('tr').length,
      chip: activeFilterChips.textContent.trim(),
    });
    const states = [read('initial')];
    seleccionarGrupoPersonal(); states.push(read('personal'));
    seleccionarGrupoGetnet(); states.push(read('getnet'));
    seleccionarGrupoSantander(); states.push(read('santander'));
    limpiarFiltros(); states.push(read('cleared'));
    return states;
  })()`);
  console.log(JSON.stringify({result, errors}, null, 2));
} finally {
  await send('Browser.close');
  ws.close();
}
