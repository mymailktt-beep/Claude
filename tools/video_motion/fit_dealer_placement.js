const {chromium}=require('/opt/node22/lib/node_modules/playwright');
const S='/tmp/claude-0/-home-user-Claude/d20dc974-b918-5a72-9048-20002d015b41/scratchpad';
(async()=>{const b=await chromium.launch({args:['--use-gl=swiftshader','--enable-unsafe-swiftshader']});const p=await b.newPage({viewport:{width:960,height:720}});
await p.route('https://cdn.jsdelivr.net/npm/three@0.169.0/**',r=>{r.fulfill({path:S+'/v/node_modules/three/'+r.request().url().split('three@0.169.0/')[1],contentType:'application/javascript'})});
await p.route('https://fonts.**',r=>r.abort());
await p.goto('http://localhost:8767/blackjack3d.html');await p.waitForFunction('window.__w3dReady',null,{timeout:90000});await p.waitForTimeout(3000);
const res=await p.evaluate(()=>{const {dealer,body,cam,bone,THREE}=window.__w3dFit;
  const L=bone('LeftArm'),R=bone('RightArm');const tgt={R:[520,65],L:[715,70]};
  const proj=o=>{const v=o.getWorldPosition(new THREE.Vector3()).project(cam);return [(v.x+1)/2*960,(1-v.y)/2*720];};
  const p0=dealer.position.clone(),r0=dealer.rotation.y,s0=body.scale.x;
  const cur={R:proj(R),L:proj(L)};
  let best=null;
  for(let x=-0.1;x<=0.5;x+=0.02)for(let z=-0.25;z<=0.1;z+=0.02)for(let yaw=0.2;yaw<=1.1;yaw+=0.05)for(let yy=-0.3;yy<=0.05;yy+=0.025){const sc=0.92;
    dealer.position.set(x,yy,z);dealer.rotation.y=yaw;body.scale.setScalar(sc);dealer.updateMatrixWorld(true);
    const a=proj(R),c=proj(L);const e=(a[0]-tgt.R[0])**2+(a[1]-tgt.R[1])**2+(c[0]-tgt.L[0])**2+(c[1]-tgt.L[1])**2;
    if(!best||e<best.e)best={e,x,y:yy,z,yaw,sc,R:a,L:c};}
  dealer.position.copy(p0);dealer.rotation.y=r0;body.scale.setScalar(s0);
  return {cur,best,camPos:cam.position.toArray()};});
console.log(JSON.stringify(res));await b.close();})();
