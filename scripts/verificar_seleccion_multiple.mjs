// Run after: .venv/Scripts/python.exe scripts/verificar_seleccion_multiple.py --serve
import { chromium } from 'playwright-core';
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';

const browser = await chromium.launch({ channel: 'chrome', headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const cookie = JSON.parse(readFileSync('.cache/multiple-filters/session.json', 'utf8'));
await context.addCookies([{ ...cookie, domain: '127.0.0.1', path: '/' }]);
const screens = [
    ['/matriz', 'clienteSelect'], ['/resumen', 'filtroCampania'],
    ['/control-proyecciones', 'filtroCliente'], ['/matriz-precios', 'filtroCliente'],
    ['/matriz-proyecciones', 'filtroCliente'], ['/variable', 'filtroCliente'],
    ['/catalogos', 'filtroClienteCatalogo'], ['/notificaciones-proyecciones', 'estadoFiltro'],
    ['/proyectado-vs-facturado', 'pvfCliente'], ['/dashboard-operativo', 'cliente'],
    ['/historial', 'filtroAccion'], ['/cumplimiento-horas-clientes', 'signo'],
    ['/cumplimiento-facturacion-clientes', 'signo'], ['/comparativo-anual-clientes', 'signo'],
    ['/variacion-horas-clientes', 'estado'], ['/resumen-horas', 'jefatura'],
    ['/carga-datos-personal', 'filtroTipoProforma'],
];
try {
    const start = process.argv[2] ? screens.findIndex(([route]) => route === process.argv[2]) : 0;
    assert(start >= 0, 'Unknown starting route');
    for (const [route, id] of screens.slice(start)) {
        const page = await context.newPage();
        const errors = [];
        const pending = new Set();
        page.on('request', request => pending.add(request));
        page.on('requestfinished', request => pending.delete(request));
        page.on('requestfailed', request => pending.delete(request));
        const settle = async () => {
            const deadline = Date.now() + 60000;
            while (pending.size) {
                assert(Date.now() < deadline, route + ': API request timed out');
                await new Promise(resolve => setTimeout(resolve, 50));
            }
        };
        page.on('pageerror', error => errors.push(error.message));
        await page.goto('http://127.0.0.1:8011' + route, { waitUntil: 'networkidle', timeout: 60000 });
        assert(!page.url().includes('/login'), route + ': unauthenticated');
        await page.waitForFunction(id => {
            const select = document.getElementById(id);
            return select?.multiple && [...select.options].filter(o => o.value !== '' && o.value !== 'todos').length >= 2;
        }, id, { timeout: 30000 });
        if (id === 'jefatura') {
            await page.evaluate(() => cambiarVista('detalle'));
        }
        const trigger = page.locator(`#${id} + [data-app-filter-trigger]`);
        await trigger.click();
        const boxes = page.locator('.app-filter-dialog-options input');
        await boxes.nth(0).check();
        await boxes.nth(1).check();
        assert.equal(await page.locator('.app-filter-dialog-options input:checked').count(), 2, route);
        await page.locator('[data-filter-apply]').click();
        await settle();
        assert.equal(await page.evaluate(id => AppFilters.valores(id).length, id), 2, route + ': selection lost');
        const dataCheck = await page.evaluate(({ route, id }) => {
            const selected = AppFilters.valores(id);
            const byClient = rows => rows.filter(row => selected.includes(row.cliente));
            if (route === '/catalogos') return {
                actual: asignacionesFiltradas().length, expected: byClient(asignacionesCatalogo).length,
            };
            if (route === '/resumen') return {
                actual: obtenerFilasFiltradas().length, expected: filas.filter(row => selected.includes(row.campania)).length,
            };
            if (route === '/control-proyecciones') return {
                actual: document.querySelectorAll('#tbodyControl tr').length - 1, expected: byClient(filas).length,
            };
            if (route === '/variable') return {
                actual: parseInt(document.getElementById('contadorVariable').textContent, 10), expected: byClient(filas).length,
            };
            if (route === '/proyectado-vs-facturado') return {
                actual: pvfFilas().length, expected: byClient(pvfState.rows).length,
            };
            if (route === '/dashboard-operativo') return {
                actual: document.querySelectorAll('#tbody tr').length, expected: byClient(filas).length,
            };
            if (route === '/matriz') return {
                actual: matrizData.seleccion.cliente.length, expected: 2,
            };
            if (route === '/resumen-horas') {
                const expected = data.detalle_jefaturas.filter(row => selected.includes(row.nombre)).reduce((sum,row) => sum+row.total.total_facturado,0);
                return { actual: Math.round(data.detalle_seleccionado.total.total_facturado), expected: Math.round(expected) };
            }
            if (route === '/variacion-horas-clientes') return {
                actual: Math.round(totalVisible().real), expected: Math.round(filasVisibles.reduce((sum,row) => sum+row.real,0)),
            };
            return null;
        }, { route, id });
        if (dataCheck) assert.equal(dataCheck.actual, dataCheck.expected, route + ': filtered data/totals');
        if (route === '/variable') {
            for (const mode of ['tarifacion', 'nextgen']) {
                const check = await page.evaluate(mode => {
                    cambiarVistaVariable(mode);
                    const selected = AppFilters.valores('filtroCliente');
                    const source = mode === 'tarifacion' ? filasTarifacion : dataNextGen.filas || [];
                    const filtered=source.filter(row=>selected.includes(row.cliente));
                    const actualTotal=mode==='nextgen'?document.querySelector('#tbodyVariable tr:first-child td:nth-child(2) div').textContent:null;
                    const expectedTotal=mode==='nextgen'?formatoMoneda(filtered.reduce((sum,row)=>sum+Number(row.total_pesos||0),0)):null;
                    return {actual:parseInt(document.getElementById('contadorVariable').textContent,10),expected:filtered.length,actualTotal,expectedTotal};
                }, mode);
                assert.equal(check.actual, check.expected, 'Variable / ' + mode);
                assert.equal(check.actualTotal, check.expectedTotal, 'Variable / ' + mode + ' total');
            }
            await page.evaluate(() => cambiarVistaVariable('porcentajes'));
        }
        await trigger.click();
        await page.locator('[data-filter-clear]').click();
        await page.locator('[data-filter-cancel]').click();
        assert.equal(await page.evaluate(id => AppFilters.valores(id).length, id), 2, route + ': cancel changed state');
        await trigger.click();
        await page.locator('[data-filter-clear]').click();
        await page.locator('[data-filter-apply]').click();
        await settle();
        assert.equal(await page.evaluate(id => AppFilters.valores(id).length, id), 0, route + ': clear failed');
        assert.deepEqual(errors, [], route + ': JavaScript errors');
        if (route === '/matriz') {
            // Month choices must remain available after narrowing the dataset.
            const months = await page.locator('#mesFiltro option[value]:not([value=""])').evaluateAll(options => options.slice(0,2).map(o => o.value));
            await page.evaluate(months => {
                AppFilters.seleccionar('mesFiltro', months);
                document.getElementById('mesFiltro').dispatchEvent(new Event('change'));
            }, months);
            await settle();
            assert.equal(await page.evaluate(() => AppFilters.valores('mesFiltro').length), 2);
            assert.equal(await page.locator('#mesFiltro option[value]:not([value=""])').count(), 12);
        }
        console.log('OK ' + route + ': multiple / apply / cancel / clear');
        await page.close();
    }
} finally {
    await browser.close();
}
