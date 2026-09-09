import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const cookie = (await readFile('.cache/session-cookie.txt', 'utf8')).trim();
const tabs = await (await fetch('http://127.0.0.1:9236/json/list')).json();
const socket = new WebSocket(tabs.find(tab => tab.type === 'page').webSocketDebuggerUrl);
await new Promise(resolve => socket.addEventListener('open', resolve, {once: true}));
let id = 0;
const pending = new Map();
const errors = [];
socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.text);
    if (pending.has(message.id)) {
        const op = pending.get(message.id); pending.delete(message.id);
        message.error ? op.reject(message.error) : op.resolve(message.result);
    }
});
const send = (method, params = {}) => new Promise((resolve, reject) => {
    pending.set(++id, {resolve, reject}); socket.send(JSON.stringify({id, method, params}));
});
const evaluate = async expression => {
    const result = await send('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
};
const waitFor = async expression => {
    for (let attempt = 0; attempt < 150; attempt++) {
        if (await evaluate(expression)) return;
        await new Promise(resolve => setTimeout(resolve, 100));
    }
    throw new Error(`No se cumplió: ${expression}`);
};

try {
    await send('Runtime.enable'); await send('Page.enable'); await send('Network.enable');
    await send('Network.setCookie', {name: 'session', value: cookie, url: 'http://127.0.0.1:8009', httpOnly: true, sameSite: 'Lax'});
    await send('Page.navigate', {url: 'http://127.0.0.1:8009/suma-fija'});
    await waitFor(`document.querySelectorAll('#cuerpo input').length > 100`);
    const suma = await evaluate(`({
        rows: document.querySelectorAll('#cuerpo tr').length,
        inputs: document.querySelectorAll('#cuerpo input').length,
        enabledEmpty: [...document.querySelectorAll('#cuerpo input')].filter(i => !i.disabled && Number(i.value) === 0).length
    })`);
    assert(suma.rows >= 100 && suma.inputs === suma.rows * 12 && suma.enabledEmpty > 0);
    await send('Page.navigate', {url: 'http://127.0.0.1:8009/variable'});
    await waitFor(`document.querySelectorAll('#campaniaSelect option').length > 100`);
    const variable = await evaluate(`({campaignOptions: document.querySelectorAll('#campaniaSelect option').length})`);
    assert(variable.campaignOptions > 100);
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({suma, variable, errors}));
} finally {
    await send('Browser.close'); socket.close();
}
