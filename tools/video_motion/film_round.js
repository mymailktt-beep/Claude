// deterministic 'film': step the game clock 1/60 s at a time and take a frame every 100 ms of game time
const {chromium}=require('/opt/node22/lib/node_modules/playwright');
const S='/tmp/claude-0/-home-user-Claude/d20dc974-b918-5a72-9048-20002d015b41/scratchpad';
const dir=S+'/'+(process.argv[2]||'film');const ranks=JSON.parse(process.argv[3]||'["10","6","5","9","K"]');const secs=+(process.argv[4]||14);
require('fs').rmSync(dir,{recursive:true,force:true});require('fs').mkdirSync(dir);
(async()=>{const b=await chromium.launch({args:['--use-gl=swiftshader','--enable-unsafe-swiftshader']});const p=await b.newPage({viewport:{width:960,height:720}});
p.on('pageerror',e=>console.log('PAGEERROR',e.message));p.on('console',m=>{if(/3D dealer/.test(m.text()))console.log(m.text())});
await p.route('https://cdn.jsdelivr.net/npm/three@0.169.0/**',r=>{r.fulfill({path:S+'/v/node_modules/three/'+r.request().url().split('three@0.169.0/')[1],contentType:'application/javascript'})});
await p.route('https://fonts.**',r=>r.abort());
await p.clock.install();await p.goto('http://localhost:8767/blackjack3d.html');
for(let i=0;i<400;i++){await p.clock.runFor(100);if(await p.evaluate(()=>!!window.__w3dReady))break;}
await p.evaluate((ranks)=>{if(!S.shoe.length)freshShoe(true);const front=ranks.map(r=>{const i=S.shoe.findIndex((c,k)=>k>=S.drawn&&c.rank===r);return S.shoe.splice(i,1)[0];});S.shoe.splice(S.drawn,0,...front);addChip(5*SC);},ranks);
await p.clock.pauseAt(await p.evaluate(()=>Date.now()+2000));await p.clock.runFor(800);await p.evaluate(()=>startHand());
let stood=false,n=0;
for(let step=0;step<secs*60;step++){await p.clock.runFor(16.667);
  if(step%(+process.env.EVERY||6)===0){await p.screenshot({path:dir+'/f_'+String(n++).padStart(4,'0')+'.png',clip:{x:170,y:30,width:640,height:480}});}
  if(!stood&&step>60*7&&await p.evaluate(()=>S.phase==='player')){stood=true;await p.evaluate(()=>playerStand());}}
console.log('frames',n,await p.evaluate(()=>S.phase));await b.close();})();
