import fs from 'node:fs';
import assert from 'node:assert/strict';
import vm from 'node:vm';

function functionCode(source, name) {
    const start = source.indexOf(`function ${name}(`);
    assert(start >= 0, name);
    const next = source.slice(start + 1).search(/\n(?:async )?function /);
    return source.slice(start, next < 0 ? undefined : start + 1 + next).trim();
}
for (const [name, functions] of [
    ['control', ['parseNumeroCampo', 'justificacionesDesdeImportes', 'formatCurrency', 'formatDecimal']],
    ['variable', ['registrarCambioDolarNextGen', 'registrarCambioProductoNextGen', 'sumarProductosNextGen', 'renderNextGen']],
]) {
    const original = fs.readFileSync(`.cache/${name}-baseline.html`, 'utf8').replace(/\r\n/g, '\n');
    const current = fs.readFileSync(`app/templates/${name}.html`, 'utf8').replace(/\r\n/g, '\n');
    for (const fn of functions) assert.equal(functionCode(current, fn), functionCode(original, fn), fn);
    if (name === 'control') {
        const payload = source => functionCode(source, 'guardarEdicion').match(/const payload = \{[\s\S]*?\n    \};/)[0];
        assert.equal(payload(current), payload(original), 'Facturación save payload changed');
    }
    for (const match of current.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)) new vm.Script(match[1]);
}
console.log('OK: funciones de importes, justificaciones y Next Gen intactas; mismos campos de guardado; JS válido.');
