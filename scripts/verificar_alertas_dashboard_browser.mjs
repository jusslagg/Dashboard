import {chromium} from 'playwright-core';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const browser=await chromium.launch({channel:'chrome',headless:true});
const context=await browser.newContext({viewport:{width:1440,height:1000}});
const cookie=JSON.parse(fs.readFileSync('.cache/multiple-filters/session.json','utf8'));
await context.addCookies([{...cookie,domain:'127.0.0.1',path:'/'}]);
const page=await context.newPage();
const errors=[];page.on('pageerror',error=>errors.push(error.message));
let detailCalls=0;page.on('request',request=>{if(request.url().includes('/api/alertas/apertura?'))detailCalls++;});
try{
 await page.goto('http://127.0.0.1:8011/',{waitUntil:'networkidle'});
 await page.waitForSelector('[data-da-alert]');
 assert.equal(await page.locator('[data-da-alert]').count(),1,'Only the Alertas ranking has an opening');
 assert.equal(await page.locator('[data-open-desvios]').count(),0,'Duplicate deviation cards were removed');
 assert.equal(await page.locator('[data-da-alert]').locator('..').locator('h3').innerText(),'Alertas');
 assert.equal(detailCalls,0,'Details must load only on demand');
 const original=await page.evaluate(()=>({query:buildQuery(),kpi:document.getElementById('kpiDesvio').textContent}));
 const details=page.locator('[data-da-alert]').first();
 await details.locator('summary').click();
 await details.locator('.da-client').first().waitFor();
 assert.equal(detailCalls,1);
 const reconciliation=await page.evaluate(async()=>{
  const query=buildQuery();
  const params=new URLSearchParams(query);params.set('alerta','desvio');
  const [kpis,alerts,ranking]=await Promise.all([
   fetch('/api/kpis'+query).then(response=>response.json()),
   fetch('/api/alertas'+query).then(response=>response.json()),
   fetch('/api/alertas/apertura?'+params).then(response=>response.json())
  ]);
  return {kpi:kpis.kpis.desvio,alert:alerts.alertas.find(alert=>alert.titulo==='Desvio negativo')?.importe,
   total:ranking.total_desvio,sum:ranking.clientes.reduce((total,account)=>total+account.desvio,0),
   values:ranking.clientes.filter(account=>Math.abs(account.desvio)>=.005).map(account=>account.desvio)};
 });
 assert.equal(reconciliation.total,reconciliation.kpi);
 if(reconciliation.kpi<0)assert.equal(reconciliation.alert,reconciliation.kpi);
 assert(Math.abs(reconciliation.sum-reconciliation.kpi)<.1);
 assert.deepEqual(reconciliation.values,[...reconciliation.values].sort((a,b)=>a-b));
 assert(await details.locator('.da-client').count()<=25);
 const firstClient=details.locator('.da-client').first();
 assert.equal(await firstClient.evaluate(element=>element.open),false);
 assert.equal(await firstClient.locator('table').isVisible(),false);
 await firstClient.locator('summary').click();
 assert((await firstClient.locator('thead').innerText()).includes('Campaña'));
 assert((await firstClient.locator('thead').innerText()).includes('Desvío acumulado'));
 const firstCampaign=firstClient.locator('[data-da-monthly]').first();
 const accumulated=await firstCampaign.evaluate(button=>button.closest('tr').cells[2].textContent);
 await firstCampaign.click();
 const dialog=page.locator('.da-month-dialog');
 assert(await dialog.evaluate(element=>element.open));
 assert.equal(await dialog.locator('tfoot td').first().innerText(),accumulated);
 assert(await dialog.locator('tbody tr').count()>0);
 assert.equal(detailCalls,2,'Monthly popup uses the same accumulated scope without another query');
 await page.screenshot({path:'.cache/multiple-filters/alerta-mensual-desktop.png'});
 await page.mouse.click(1,1);
 assert.equal(await dialog.evaluate(element=>element.open),false);
 assert(await details.evaluate(element=>element.open));
 assert(await firstCampaign.evaluate(button=>button===document.activeElement));
 await firstCampaign.click();
 await page.keyboard.press('Escape');
 assert.equal(await dialog.evaluate(element=>element.open),false);
 if(await details.locator('[data-da-page="1"]').count()){
  await details.locator('[data-da-page="1"]').click();
  const pagination=await details.locator('.da-pages').innerText();
  assert(pagination.includes('Página 2'),pagination);
 }
 const clientName=await firstClient.locator('.da-client-name').evaluate(element=>element.firstChild.textContent);
 await details.locator('input').fill(clientName);
 assert((await details.locator('.da-client-name').allTextContents()).every(text=>text.includes(clientName)));
 await details.locator('input').fill('nonexistent-alert-client');
 assert.equal(await details.locator('.da-client').count(),0);
 await details.locator('input').fill('');
 if(!await firstClient.evaluate(element=>element.open))await firstClient.locator('summary').click();
 await page.screenshot({path:'.cache/multiple-filters/dashboard-alertas-desktop.png'});
 await page.setViewportSize({width:390,height:844});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 await details.locator('[data-da-monthly]').first().click();
 assert(await dialog.evaluate(element=>element.getBoundingClientRect().right<=innerWidth));
 await page.screenshot({path:'.cache/multiple-filters/alerta-mensual-mobile.png'});
 await dialog.locator('[data-da-close]').last().click();
 await page.screenshot({path:'.cache/multiple-filters/dashboard-alertas-mobile.png'});
 await page.locator('main h1').click();
 assert.equal(await details.evaluate(element=>element.open),false);
 assert.deepEqual(await page.evaluate(()=>({query:buildQuery(),kpi:document.getElementById('kpiDesvio').textContent})),original);
 await page.setViewportSize({width:1440,height:1000});
 // Refresh risk details to exercise an uncached failed request and retry.
 await page.evaluate(()=>cargarDashboard());
 const other=page.locator('[data-da-alert]').first();
 await page.route('**/api/alertas/apertura?*',route=>route.fulfill({status:500,contentType:'application/json',body:'{"success":false}'}));
 await other.locator('summary').click();
 await other.locator('[data-da-retry]').waitFor();
 await page.unroute('**/api/alertas/apertura?*');
 await other.locator('[data-da-retry]').click();
 await other.locator('.da-client').first().waitFor();
 assert.equal(await page.locator('[data-da-alert][open]').count(),1);
 assert.equal(errors.length,0,errors.join('\n'));
 console.log('OK: lazy alert dropdowns, client/campaign/month details, search/pagination, outside close, independent filters, retry and mobile layout.');
}finally{await browser.close();}
