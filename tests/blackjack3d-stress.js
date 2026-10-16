// Plays five rounds back to back (four of them blackjacks), tapping REPEAT/DEAL the moment they light up,
// and checks every round deals and no stray cards are left on the table. Needs a build with the
// window.__w3dCount test hook, served on localhost:8767, and three.js under $BJ_SCRATCH/v/node_modules.
const {chromium}=require('/opt/node22/lib/node_modules/playwright');
const S=process.env.BJ_SCRATCH||__dirname;
(async()=>{const b=await chromium.launch({args:['--use-gl=swiftshader','--enable-unsafe-swiftshader']});const p=await b.newPage({viewport:{width:960,height:720}});
p.on('pageerror',e=>console.log('PAGEERROR',e.message));p.on('console',m=>{if(/3D dealer/.test(m.text()))console.log('console',m.text().slice(0,200))});
await p.route('https://cdn.jsdelivr.net/npm/three@0.169.0/**',r=>{r.fulfill({path:S+'/v/node_modules/three/'+r.request().url().split('three@0.169.0/')[1],contentType:'application/javascript'})});
await p.route('https://fonts.**',r=>r.abort());
await p.goto('http://localhost:8767/blackjack3d.html');await p.waitForFunction('window.__w3dReady',null,{timeout:90000});
const stack=r=>p.evaluate((ranks)=>{const front=ranks.map(r=>{const i=S.shoe.findIndex((c,k)=>k>=S.drawn&&c.rank===r);return S.shoe.splice(i,1)[0];});S.shoe.splice(S.drawn,0,...front);},r);
await p.evaluate(()=>{if(!S.shoe.length)freshShoe(true);});
const st=()=>p.evaluate(()=>({ph:S.phase,cards:(S.hands||[]).reduce((n,h)=>n+h.cards.length,0)+(S.dealer.cards||[]).length,meshes:window.__w3dCount(),bank:S.bankroll}));
const tapWhenOn=async(label,ms=20000)=>{const t0=Date.now();while(Date.now()-t0<ms){const ok=await p.evaluate(l=>{const b=[...document.querySelectorAll('#bjBar .key')].find(b=>b.textContent.trim().toLowerCase().startsWith(l));if(b&&!b.disabled){b.click();return true;}return false;},label.toLowerCase());if(ok)return true;await p.waitForTimeout(100);}return false;};
await p.mouse.click(470,392);await p.waitForTimeout(300);
const hands=[["A","K","9","7"],["K","A","8","6"],["A","Q","5","9"],["9","7","10","8"],["A","J","6","7"]];
for(let r=0;r<hands.length;r++){
  await stack(hands[r]);
  const dealt=await tapWhenOn('deal')||(await tapWhenOn('repeat',30000)&&await tapWhenOn('deal'));
  const t0=Date.now();let ph;
  while(Date.now()-t0<40000){ph=(await st()).ph;if(ph==='player'){await tapWhenOn('stand');}if(ph==='settle')break;await p.waitForTimeout(150);}
  const a=await st();
  // be impatient: tap REPEAT the moment it lights up, then DEAL straight away
  const rep=await tapWhenOn('repeat',30000);
  console.log('round',r+1,'dealt',dealt,'settled',JSON.stringify(a),'repeat',rep);
}
await p.waitForTimeout(15000);console.log('end',JSON.stringify(await st()));
await p.screenshot({path:S+'/stress.png'});
await b.close();})();
