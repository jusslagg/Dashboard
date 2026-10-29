import { chromium } from 'playwright-core';
import fs from 'node:fs';
import assert from 'node:assert/strict';

const browser = await chromium.launch({ channel: 'chrome', headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const cookie = JSON.parse(fs.readFileSync('.cache/multiple-filters/session.json', 'utf8'));
await context.addCookies([{ ...cookie, domain: '127.0.0.1', path: '/' }]);
const page = await context.newPage();
const errors = [];
page.on('pageerror', error => errors.push(error.message));
try {
    await page.goto('http://127.0.0.1:8011/notificaciones-proyecciones', { waitUntil: 'networkidle' });
    await page.waitForFunction(() => document.getElementById('contador').textContent.includes('comparación(es)'));
    await page.locator('button[onclick="limpiarFiltros()"]').click();
    const count = await page.evaluate(() => datosNotificaciones.notificaciones.length);
    assert(count > 0);
    const expected = await page.evaluate(() => ({
        sube: datosNotificaciones.notificaciones.filter(item => item.impacto_facturacion > .005).length,
        baja: datosNotificaciones.notificaciones.filter(item => item.impacto_facturacion < -.005).length,
        cero: datosNotificaciones.notificaciones.filter(item => Math.abs(item.impacto_facturacion) <= .005).length,
    }));
    assert.equal(await page.locator('#kpiPositivas').innerText(), expected.sube.toLocaleString('es-AR'));
    assert.equal(await page.locator('#kpiNegativas').innerText(), expected.baja.toLocaleString('es-AR'));
    assert.equal(await page.locator('#kpiMixtas').innerText(), expected.cero.toLocaleString('es-AR'));
    await page.evaluate(() => {
        AppFilters.seleccionar('estadoFiltro', ['sube']);
        document.getElementById('estadoFiltro').dispatchEvent(new Event('change', { bubbles: true }));
    });
    assert(await page.evaluate(() => notificacionesVisibles().every(item => item.impacto_facturacion > .005)));
    const downloading = page.waitForEvent('download');
    await page.locator('button[onclick="exportarReporte()"]').click();
    const download = await downloading;
    assert(new URL(download.url()).searchParams.getAll('direccion_importe').includes('sube'));
    assert.equal(await download.failure(), null);
    await page.locator('button[onclick="limpiarFiltros()"]').click();
    assert.equal(await page.locator('#estadoFiltro').evaluate(select => [...select.selectedOptions].filter(option => option.value).length), 0);
    await page.locator('#tbodyNotificaciones details').first().locator('summary').click();
    assert(await page.locator('#tbodyNotificaciones details').first().evaluate(element => element.open));
    const opposite = await page.evaluate(() => datosNotificaciones.notificaciones.find(item => item.servicios.some(service => service.impacto_facturacion > .005) && item.servicios.some(service => service.impacto_facturacion < -.005)));
    if (opposite) {
        await page.locator('#buscarFiltro').fill(opposite.cliente);
        assert(await page.locator('.nt-opposing').count() > 0);
    }
    await page.screenshot({ path: '.cache/multiple-filters/notificaciones-desktop.png' });
    await page.setViewportSize({ width: 390, height: 844 });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await page.screenshot({ path: '.cache/multiple-filters/notificaciones-mobile.png', fullPage: true });
    await page.route('**/api/notificaciones-proyecciones?*', route => route.fulfill({ status: 500, contentType: 'application/json', body: '{"success":false}' }));
    await page.locator('button[onclick="cargarNotificaciones()"]').click();
    await page.waitForFunction(() => document.getElementById('contador').textContent.includes('reintentar'));
    assert.equal(await page.locator('#kpiPositivas').innerText(), '—');
    await page.unroute('**/api/notificaciones-proyecciones?*');
    await page.locator('button[onclick="cargarNotificaciones()"]').click();
    await page.waitForFunction(() => document.getElementById('contador').textContent.includes('comparación(es)'));
    assert.deepEqual(errors, []);
    console.log(`OK Chrome: ${count} comparaciones, KPI, filtro por dirección, descarga Excel, detalle de servicios, movimientos opuestos, móvil y recuperación de errores.`);
} catch (error) {
    await page.screenshot({ path: '.cache/multiple-filters/notificaciones-error.png', fullPage: true });
    throw error;
} finally {
    await browser.close();
}
