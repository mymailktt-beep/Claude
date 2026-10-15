const TABLE_Y=0.96,EDGE_Z=0.22;
const arc=(r,deg,y=TABLE_Y)=>[r*Math.cos(deg*Math.PI/180),y,EDGE_Z+r*Math.sin(deg*Math.PI/180)];
const W=960,H=720;
const Q=[[550,358],[343,302],[288,182],[708,262],[400,82]];
const pts=(dl,sr)=>[arc(sr,90-dl),arc(sr,90),arc(sr,90+dl),[0.5,TABLE_Y+0.05,EDGE_Z],[-0.5,TABLE_Y+0.06,EDGE_Z-0.02]];
function proj(c,p){const[cx,cy,cz,tx,ty,tz,fov]=c;let f=[tx-cx,ty-cy,tz-cz];const fl=Math.hypot(...f);f=f.map(v=>v/fl);
  let r=[-f[2],0,f[0]];const rl=Math.hypot(...r);r=r.map(v=>v/rl);const u=[r[1]*f[2]-r[2]*f[1],r[2]*f[0]-r[0]*f[2],r[0]*f[1]-r[1]*f[0]];
  const d=[p[0]-cx,p[1]-cy,p[2]-cz];const z=d[0]*f[0]+d[1]*f[1]+d[2]*f[2];if(z<=0.01)return[1e4,1e4];
  const x=d[0]*r[0]+d[1]*r[1]+d[2]*r[2],y=d[0]*u[0]+d[1]*u[1]+d[2]*u[2];const k=1/Math.tan(fov*Math.PI/360);return[W/2+(x/z)*k*(H/2),H/2-(y/z)*k*(H/2)];}
const err=c=>{const P=pts(c[7],c[8]);return P.reduce((s,p,i)=>{const a=proj(c,p);return s+(a[0]-Q[i][0])**2+(a[1]-Q[i][1])**2;},0);};
let gbest=null,gbe=1e18;
for(let run=0;run<12;run++){let best=[Math.random()*2-0.5,1.6+Math.random(),1+Math.random(),0,0.9,0.4,40+Math.random()*20,30+Math.random()*30,0.45],be=err(best);
for(let it=0;it<150000;it++){const sc=it<70000?0.2:0.02;const c=best.map((v,i)=>v+(Math.random()-.5)*sc*(i===6?30:i===7?40:i===8?0.3:1));
  if(c[6]<25||c[6]>60||c[7]<20||c[7]>65||c[8]<0.35||c[8]>0.6)continue;const e=err(c);if(e<be){be=e;best=c;}}
if(be<gbe){gbe=be;gbest=best;}}
console.log('rms px',Math.sqrt(gbe/5).toFixed(1),gbest.map(v=>v.toFixed(3)).join(','));
pts(gbest[7],gbest[8]).forEach((p,i)=>console.log(Q[i],proj(gbest,p).map(v=>v.toFixed(0))));
