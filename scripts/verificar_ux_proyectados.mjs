// Uses the isolated server started by verificar_seleccion_multiple.py --serve.
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import assert from 'node:assert/strict';

const file = 'app/templates/matriz_proyecciones.html';
// Baseline: git show HEAD:app/templates/matriz_proyecciones.html > .cache/multiple-filters/proyecciones-baseline.html
const before = fs.readFileSync('.cache/multiple-filters/proyecciones-baseline.html', 'utf8').replace(/\r\n/g, '\n');
const after = fs.readFileSync(file, 'utf8').replace(/\r\n/g, '\n');
function functionSource(source, name) {
    const start = source.indexOf(`function ${name}(`);
    assert(start >= 0, name);
    const next = source.slice(start + 1).search(/\n(?:async )?function /);
    return source.slice(start, next < 0 ? undefined : start + 1 + next).trim();
}
for (const name of ['actualizarProyectadas', 'calcularDiasObjetivo', 'obtenerJornadasFormulario', 'filasVisualesProyeccion', 'renderProyeccionesPLPAgrupadas', 'renderResumenPLP', 'numero', 'horasPLPPegadas']) {
    assert.equal(functionSource(after, name), functionSource(before, name), `${name}: calculation changed`);
}
const payload = source => source.match(/    const payload = \{[\s\S]*?\n    \};/)[0];
assert.equal(payload(after), payload(before), 'Save payload changed');
console.log('Parity: 8 calculation/grouping functions and save payload unchanged.');

const browser = await chromium.launch({ channel: 'chrome', headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const cookie = JSON.parse(fs.readFileSync('.cache/multiple-filters/session.json', 'utf8'));
await context.addCookies([{ ...cookie, domain: '127.0.0.1', path: '/' }]);
const page = await context.newPage();
const errors = [];
page.on('pageerror', error => errors.push(error.message));
try {
    await page.goto('http://127.0.0.1:8011/matriz-proyecciones', { waitUntil: 'networkidle' });
    await page.waitForFunction(() => document.getElementById('estadoCargaProyecciones').textContent.includes('Información actualizada'));
    assert.equal(await page.locator('#editorProyeccion').isVisible(), false);
    const general = await page.evaluate(() => proyecciones.filter(item => !item.tipo_plp).map(item => ({ id: item.id, cliente: item.cliente, campania: item.campania, horas: item.horas_proyectadas })));
    assert(general.length > 0);
    const expectedRows = await page.evaluate(() => proyecciones.filter(item => !item.tipo_plp).slice(0, 50).flatMap(filasVisualesProyeccion).length);
    assert.equal(await page.locator('#tbodyProyecciones > tr').count(), expectedRows);
    if (general.length > 50) {
        await page.locator('#paginaSiguienteProyecciones').click();
        assert.match(await page.locator('#rangoProyecciones').innerText(), /51[–-]/);
        await page.locator('#paginaAnteriorProyecciones').click();
    }
    await page.locator('#buscarProyeccion').fill('zzzz-sin-resultados');
    await page.waitForFunction(() => document.getElementById('rangoProyecciones').textContent === 'Sin resultados');
    await page.getByRole('button', { name: 'Limpiar filtros', exact: true }).click();
    assert.equal(await page.locator('#tbodyProyecciones > tr').count(), expectedRows);

    // The existing backend replicates general parameters to future months.
    // Check the edited month and unrelated services, preserving that rule.
    await page.locator('#tbodyProyecciones button').first().click();
    const edited = await page.evaluate(() => ({id: Number(document.getElementById('proyeccionId').value), cliente: document.getElementById('cliente').value, campania: document.getElementById('campania').value}));
    assert.equal(await page.locator('#editorProyeccion').isVisible(), true);
    const preview = await page.locator('#horasProyectadasPreview').innerText();
    await page.locator('#porcentajeCumplimiento').fill(await page.locator('#porcentajeCumplimiento').inputValue());
    assert.equal(await page.locator('#estadoCambiosProyecciones').isVisible(), true);
    await page.getByRole('button', { name: 'Ocultar formulario de proyección' }).click();
    await page.locator('#abrirEditorProyeccion').click();
    assert.equal(await page.locator('#horasProyectadasPreview').innerText(), preview);
    const response = page.waitForResponse(response => new URL(response.url()).pathname === '/api/matriz-proyecciones' && response.request().method() === 'POST');
    await page.locator('#guardarProyeccionBtn').click();
    await page.locator('#revisionProyecciones').waitFor({ state: 'visible' });
    assert((await page.locator('#revisionProyeccionesFilas tr').count()) > 0);
    await page.locator('#cancelarRevisionProyecciones').click();
    await page.waitForFunction(() => !document.getElementById('guardarProyeccionBtn').disabled);
    assert.equal(await page.locator('#horasProyectadasPreview').innerText(), preview);
    await page.locator('#guardarProyeccionBtn').click();
    await page.locator('#revisionProyecciones').waitFor({ state: 'visible' });
    await page.locator('#confirmarRevisionProyecciones').click();
    assert.equal((await response).status(), 200);
    await page.waitForFunction(() => !document.getElementById('guardarProyeccionBtn').disabled);
    const refreshed = await page.evaluate(async () => (await (await fetch('/api/matriz-proyecciones?year=' + document.getElementById('yearFiltro').value)).json()).proyecciones.map(item => ({id:item.id, cliente:item.cliente, campania:item.campania, horas:item.horas_proyectadas})).filter(item => !proyecciones.find(record => record.id === item.id)?.tipo_plp));
    assert.deepEqual(refreshed.find(item => item.id === edited.id), general.find(item => item.id === edited.id), 'Edited month must preserve its hours');
    const unrelated = items => items.filter(item => item.cliente !== edited.cliente || item.campania !== edited.campania);
    assert.deepEqual(unrelated(refreshed), unrelated(general), 'Unrelated services must be unchanged');

    await page.getByRole('button', { name: 'Ocultar formulario de proyección' }).click();
    await page.locator('#tabPersonal').click();
    assert.equal(await page.locator('#panelEditorPLP').isVisible(), true);
    const plpField = page.locator('#tbodyEditorPLP input[data-plp="horas"]').first();
    if (await plpField.count()) {
        const original = await plpField.inputValue();
        await plpField.fill('12345.67');
        await page.locator('#tabTodas').click();
        await page.locator('#tabPersonal').click();
        assert.equal(await plpField.inputValue(), '12345.67', 'Switching tabs must preserve PLP draft');
        page.once('dialog', dialog => dialog.dismiss());
        await page.evaluate(() => {
            AppFilters.seleccionar('filtroMesEditorPLP', ['2026-02']);
            document.getElementById('filtroMesEditorPLP').dispatchEvent(new Event('change', { bubbles: true }));
        });
        assert.equal(await plpField.inputValue(), '12345.67', 'Cancelled month switch must preserve draft');
        page.once('dialog', dialog => dialog.dismiss());
        await page.locator('#actualizarProyeccionesBtn').click();
        assert.equal(await plpField.inputValue(), '12345.67');
        await plpField.fill(original);
        page.once('dialog', dialog => dialog.accept());
        await page.locator('#actualizarProyeccionesBtn').click();
        await page.waitForFunction(() => !document.getElementById('actualizarProyeccionesBtn').disabled);
        await plpField.fill('45678.90');
        await page.locator('#tabTodas').click();
        page.once('dialog', dialog => dialog.dismiss());
        await page.evaluate(async () => {
            document.getElementById('yearFiltro').value = '2027';
            await ProyeccionesUX.cambiarAnio();
        });
        assert.equal(await page.locator('#yearFiltro').inputValue(), '2026', 'Cancelled year switch restores selection');
        page.once('dialog', dialog => dialog.accept());
        await page.evaluate(async () => {
            document.getElementById('yearFiltro').value = '2027';
            await ProyeccionesUX.cambiarAnio();
        });
        assert.equal(await page.locator('#tbodyEditorPLP [data-plp]').count(), 0, 'Discard must clear drafts in hidden PLP editor');
        assert(await page.evaluate(() => proyecciones.every(item => item.mes.startsWith('2027-'))));
        await page.evaluate(async () => {
            document.getElementById('yearFiltro').value = '2026';
            await ProyeccionesUX.cambiarAnio();
        });
    }
    await page.locator('#tabPersonal').click();
    await page.locator('button[onclick="agregarFilaEditorPLP()"]').click();
    const added = page.locator('#tbodyEditorPLP tr[data-plp-id]').last();
    await added.locator('[data-plp="campania"]').fill('UX prueba revisión');
    await added.locator('[data-plp="horas"]').fill('');
    await page.locator('#guardarEditorPLPBtn').click();
    assert.equal(await added.locator('[data-plp="horas"]').getAttribute('aria-invalid'), 'true');
    assert.equal(await page.locator('#revisionProyecciones').isVisible(), false);
    await added.locator('[data-plp="horas"]').fill('123.45');
    await page.locator('#guardarEditorPLPBtn').click();
    await page.locator('#revisionProyecciones').waitFor({ state: 'visible' });
    assert.match(await page.locator('#revisionProyeccionesResumen').innerText(), /1 fila\(s\) a guardar/);
    await page.keyboard.press('Escape');
    await page.waitForFunction(() => !document.getElementById('guardarEditorPLPBtn').disabled);
    assert.equal(await added.locator('[data-plp="horas"]').inputValue(), '123.45');
    await page.route('**/api/proyecciones-plp/edicion-masiva', route => route.fulfill({status: 500, contentType: 'application/json', body: '{"success":false,"errores":["Prueba de fallo"]}'}));
    await page.locator('#guardarEditorPLPBtn').click();
    await page.locator('#revisionProyecciones').waitFor({ state: 'visible' });
    await page.locator('#confirmarRevisionProyecciones').click();
    await page.waitForFunction(() => !document.getElementById('guardarEditorPLPBtn').disabled);
    assert.equal(await added.locator('[data-plp="horas"]').inputValue(), '123.45', 'Failed save must preserve input');
    assert.equal(await added.getAttribute('data-plp-dirty'), '1');
    await page.unroute('**/api/proyecciones-plp/edicion-masiva');
    const bulkSaved = page.waitForResponse(response => response.url().includes('/api/proyecciones-plp/edicion-masiva') && response.request().method() === 'POST');
    await page.locator('#guardarEditorPLPBtn').click();
    await page.locator('#revisionProyecciones').waitFor({ state: 'visible' });
    await page.locator('#confirmarRevisionProyecciones').click();
    assert.equal((await bulkSaved).status(), 200);
    await page.waitForFunction(() => !document.getElementById('guardarEditorPLPBtn').disabled);
    await page.locator('#tablaPegadaPLP').fill('Personal | ene-26 | Prueba | abc');
    await page.locator('#procesarTablaPLPBtn').click();
    await page.locator('[data-plp-line="1"]').click();
    assert(await page.locator('#tablaPegadaPLP').evaluate(field => field.selectionEnd > field.selectionStart), 'Error must select pasted source line');
    const replacement = await page.evaluate(() => {
        const groups = new Map();
        proyecciones.filter(item => item.tipo_plp).forEach(item => groups.set(item.mes, (groups.get(item.mes) || 0) + 1));
        const month = [...groups].find(([, count]) => count > 1)[0];
        const item = proyecciones.find(item => item.tipo_plp && item.mes === month);
        return { text: `${item.tipo_plp} | ${item.mes} | ${item.campania} | ${item.horas_requeridas}`, removed: groups.get(month) - 1 };
    });
    await page.locator('#tablaPegadaPLP').fill(replacement.text);
    await page.locator('#procesarTablaPLPBtn').click();
    await page.locator('#guardarEditorPLPBtn').click();
    await page.locator('#revisionProyecciones').waitFor({ state: 'visible' });
    assert((await page.locator('#revisionProyeccionesResumen').innerText()).includes(`${replacement.removed} campaña(s) a eliminar`));
    await page.screenshot({ path: '.cache/multiple-filters/proyecciones-review.png', fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    assert(await page.locator('#revisionProyecciones').evaluate(dialog => dialog.getBoundingClientRect().right <= innerWidth), 'Review must fit mobile viewport');
    await page.screenshot({ path: '.cache/multiple-filters/proyecciones-review-mobile.png', fullPage: true });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.locator('#cancelarRevisionProyecciones').click();
    await page.waitForFunction(() => !document.getElementById('guardarEditorPLPBtn').disabled);
    page.once('dialog', dialog => dialog.accept());
    await page.locator('#actualizarProyeccionesBtn').click();
    await page.waitForFunction(() => !document.getElementById('actualizarProyeccionesBtn').disabled);
    await page.locator('#tabTodas').click();
    await page.route('**/api/matriz-proyecciones?*', route => route.fulfill({ status: 500, contentType: 'application/json', body: '{"success":false}' }));
    await page.locator('#actualizarProyeccionesBtn').click();
    await page.waitForFunction(() => document.getElementById('estadoCargaProyecciones').dataset.state === 'error');
    assert.equal(await page.locator('#actualizarProyeccionesBtn').isEnabled(), true);
    await page.unroute('**/api/matriz-proyecciones?*');
    await page.locator('#actualizarProyeccionesBtn').click();
    await page.waitForFunction(() => document.getElementById('estadoCargaProyecciones').textContent.includes('Información actualizada'));
    await page.evaluate(() => { document.getElementById('tablaProyeccionesScroll').scrollLeft = 0; });
    await page.screenshot({ path: '.cache/multiple-filters/proyecciones-desktop.png', fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: '.cache/multiple-filters/proyecciones-mobile.png', fullPage: true });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), 'Page must not overflow on mobile');
    assert.deepEqual(errors, []);
    console.log(`Browser OK: ${general.length} services, pagination, search, unchanged save, PLP drafts, errors, retry and mobile.`);
} catch (error) {
    await page.screenshot({ path: '.cache/multiple-filters/proyecciones-test-error.png', fullPage: true });
    throw error;
} finally {
    await browser.close();
}
