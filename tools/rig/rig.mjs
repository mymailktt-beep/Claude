// Auto-rig the static "Woman Dress 2" model: Mixamo-style skeleton fitted to her A-pose, skin weights from geometry.
import {load} from './load.mjs';
import {Accessor} from '@gltf-transform/core';
const [,,SRC,DST]=process.argv;
const {io,doc,prims}=await load(SRC);
const sub=(a,b)=>a.map((x,i)=>x-b[i]),add=(a,b)=>a.map((x,i)=>x+b[i]),mul=(a,k)=>a.map(x=>x*k),dot=(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2],
  len=a=>Math.hypot(...a),nrm=a=>mul(a,1/len(a)),cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]],lerp=(a,b,t)=>a.map((x,i)=>x+(b[i]-x)*t);
const sstep=(e0,e1,x)=>{const t=Math.max(0,Math.min(1,(x-e0)/(e1-e0)));return t*t*(3-2*t);};
const P=m=>prims.find(p=>p.mat===m);
const ARM=P('Material13462'),TORSO=P('Material13458'),HEADM=P('Material13454'),SHIRT=P('Cotton_Oxford_FCL1PSC011_FRONT_4174');
const vtx=(p,i)=>[p.pos[i*3],p.pos[i*3+1],p.pos[i*3+2]];

/* ---------- skeleton ---------- */
const J=[];const jIndex={};
const joint=(name,pos,parent)=>{jIndex[name]=J.length;J.push({name,pos,parent});};
joint('Hips',[0,0.98,-0.02],null);joint('Spine',[0,1.08,-0.025],'Hips');joint('Spine1',[0,1.20,-0.03],'Spine');joint('Spine2',[0,1.33,-0.03],'Spine1');
joint('Neck',[0,1.55,-0.035],'Spine2');joint('Head',[0,1.665,-0.02],'Neck');joint('HeadTop_End',[0,1.86,-0.02],'Head');
const sideInfo={};
for(const [sx,P0] of [[1,'Left'],[-1,'Right']]){
  const V=[];for(let i=0;i<ARM.n;i++){const v=vtx(ARM,i);if(v[0]*sx>0)V.push(v);}
  const O=[0.17*sx,1.5,0];
  const tip=V.reduce((b,v)=>{const d=len(sub(v,[0.12*sx,1.5,0]));return d>b.d?{d,v}:b},{d:0}).v;
  const u=nrm(sub(tip,O));
  const bins={};for(const v of V){const t=dot(sub(v,O),u);const b=Math.floor(t*100);(bins[b]=bins[b]||[]).push(v);}
  const cen=b=>{const Q=bins[b];return [0,1,2].map(k=>Q.reduce((s,v)=>s+v[k],0)/Q.length);};
  const rad=b=>{const c=cen(b);return Math.max(...bins[b].map(v=>{const d=sub(v,c);return len(sub(d,mul(u,dot(d,u))));}));};
  let wb=40,wr=1;for(let b=40;b<=52;b++)if(bins[b]&&bins[b].length>8){const r=rad(b);if(r<wr){wr=r;wb=b;}}
  const S=add(cen(0),[0,0.008,0]),W=cen(wb);
  // elbow: 56% of the way from shoulder to wrist, on the arm's centre line, nudged to the back of the arm
  const eb=Math.round(wb*0.56);const E=add(cen(eb),[0,0,-0.008]);
  joint(P0+'Shoulder',[0.035*sx,1.49,-0.05],'Spine2');joint(P0+'Arm',S,P0+'Shoulder');joint(P0+'ForeArm',E,P0+'Arm');joint(P0+'Hand',W,P0+'ForeArm');
  // hand frame: A along the hand, L across it (thumb side +), N out of the palm
  const A=nrm(sub(tip,W));let L=[0,0,1];L=nrm(sub(L,mul(A,dot(L,A))));const N=cross(A,L);
  const hand=V.map(v=>{const d=sub(v,W);return {v,t:dot(d,A),s:dot(d,L),q:dot(d,N)};}).filter(h=>h.t>-0.012);
  const isThumb=h=>h.s>=0.035||(h.s>=0.02&&h.t>0.045&&h.t<0.095);
  const FING=[['Index',0.0125,0.034],['Middle',-0.011,0.0125],['Ring',-0.0355,-0.011],['Pinky',-0.06,-0.0355]];   // gaps between the fingers, measured
  const fingerOf=h=>{if(isThumb(h))return 'Thumb';if(h.t<0.085)return null;for(const[f,a,b]of FING)if(h.s>=a&&h.s<b)return f;return null;};
  const at=(t,s,q)=>add(W,add(add(mul(A,t),mul(L,s)),mul(N,q)));
  const centerNear=(list,t,w=0.007)=>{const Q=list.filter(h=>Math.abs(h.t-t)<w);if(!Q.length)return null;const s=Q.reduce((a,h)=>a+h.s,0)/Q.length,q=Q.reduce((a,h)=>a+h.q,0)/Q.length;return [t,s,q];};
  const chains={};
  for(const[f]of FING){const L2=hand.filter(h=>fingerOf(h)===f);const tipT=Math.max(...L2.map(h=>h.t));const m=0.098,len_=tipT-m;
    const ts=[m,m+0.45*len_,m+0.75*len_,tipT-0.004];const pts=ts.map(t=>centerNear(L2,t)||centerNear(hand.filter(h=>Math.abs(h.s-(L2[0]?.s||0))<0.01),t,0.012));
    pts.forEach((p,k)=>joint(P0+'Hand'+f+(k+1),at(...p),k?P0+'Hand'+f+k:P0+'Hand'));chains[f]={ts};}
  { const L2=hand.filter(h=>fingerOf(h)==='Thumb');const tipH=L2.reduce((b,h)=>h.t>b.t?h:b);
    const ts=[0.028,0.062,0.092,tipH.t-0.004];const pts=ts.map((t,k)=>k===0?[t,0.02,(L2.filter(h=>h.t<0.05).reduce((a,h)=>a+h.q,0)/Math.max(1,L2.filter(h=>h.t<0.05).length))||0]:centerNear(L2,t,0.01));
    pts.forEach((p,k)=>joint(P0+'HandThumb'+(k+1),at(...p),k?P0+'HandThumb'+k:P0+'Hand'));chains.Thumb={ts};}
  sideInfo[P0]={sx,S,E,W,A,L,N,chains,fingerOf,isThumb};
  console.log(P0,'S',S.map(x=>x.toFixed(3)),'E',E.map(x=>x.toFixed(3)),'W',W.map(x=>x.toFixed(3)),'tip',tip.map(x=>x.toFixed(3)),'wrist r',wr.toFixed(3));
}

/* ---------- weights ---------- */
const jw=()=>new Map();
const addW=(m,name,w)=>{if(w<=1e-4)return;const i=jIndex[name];m.set(i,(m.get(i)||0)+w);};
const SPINE=[['Hips',0.98],['Spine',1.08],['Spine1',1.20],['Spine2',1.33],['Neck',1.55],['Head',1.665]];
function spineW(m,y,k=1){
  if(y<=SPINE[0][1]){addW(m,'Hips',k);return;}
  for(let i=0;i<SPINE.length-1;i++){const[a,ya]=SPINE[i],[b,yb]=SPINE[i+1];if(y<yb){const f=(y-ya)/(yb-ya);addW(m,a,k*(1-f));addW(m,b,k*f);return;}}
  addW(m,'Head',k);
}
function segParam(v,a,b){const ab=sub(b,a);const t=dot(sub(v,a),ab)/dot(ab,ab);const tc=Math.max(0,Math.min(1,t));return {t,d:len(sub(v,add(a,mul(ab,tc)))),L:len(ab)};}
function chainW(m,t,ts,names,w=0.006){  // bones along a chain split at joint positions ts (names[i] owns ts[i]..ts[i+1])
  let k=0;while(k<ts.length-1&&t>=ts[k+1])k++;
  const blends=names.map(()=>0);blends[k]=1;
  if(k+1<names.length){const f=sstep(ts[k+1]-w,ts[k+1]+w,t);blends[k]-=f;blends[k+1]+=f;}
  if(k>0){const f=1-sstep(ts[k]-w,ts[k]+w,t);blends[k]-=f;blends[k-1]+=f;}
  names.forEach((n,i)=>addW(m,n,blends[i]));
}
function armWeights(v){
  const m=jw();const P0=v[0]>0?'Left':'Right',I=sideInfo[P0];
  const d=sub(v,I.W),t=dot(d,I.A),s=dot(d,I.L),q=dot(d,I.N);
  if(t>-0.012){                                            // hand
    const h={t,s,q},f=I.fingerOf(h);
    const wrist=sstep(-0.012,0.006,t);                     // forearm -> hand across the wrist
    if(wrist<1)addW(m,P0+'ForeArm',1-wrist);
    if(f){const ts=[-1,...I.chains[f].ts.slice(0,3)];chainW(m,t,ts,[P0+'Hand',...[1,2,3].map(k=>P0+'Hand'+f+k)],0.007);
      for(const[k,x]of m)if(k!==jIndex[P0+'ForeArm'])m.set(k,x*wrist);}
    else if(t>0.075&&!I.isThumb(h)){                        // between the fingers near the knuckles: share with the nearest finger
      addW(m,P0+'Hand',wrist);}
    else addW(m,P0+'Hand',wrist);
    return m;}
  const up=segParam(v,I.S,I.E),lo=segParam(v,I.E,I.W);
  const Lu=up.L,u=up.t*Lu;                                // distance along the upper arm from the shoulder joint
  if(up.d<lo.d||up.t<1){
    const e=sstep(Lu-0.035,Lu+0.03,u);                     // elbow blend
    const sh=1-sstep(-0.05,0.02,u);                       // shoulder blend, matching the torso's
    addW(m,P0+'Shoulder',sh*0.5);spineW(m,v[1],sh*0.5);addW(m,P0+'Arm',(1-sh)*(1-e));addW(m,P0+'ForeArm',(1-sh)*e);
  }else{const Ll=lo.L,x=lo.t*Ll;const e=1-sstep(-0.03,0.035,x);addW(m,P0+'Arm',e);addW(m,P0+'ForeArm',1-e);}
  return m;
}
// how far a point sits out along the upper arm from the shoulder joint (negative: towards the neck)
function armOut(v){const P0=v[0]>0?'Left':'Right',I=sideInfo[P0];const ab=nrm(sub(I.E,I.S));return dot(sub(v,I.S),ab);}
function torsoWeights(v){
  const m=jw();const ax=Math.abs(v[0]),P0=v[0]>0?'Left':'Right';
  const a=sstep(-0.05,0.02,armOut(v))*sstep(0.125,0.165,ax)*sstep(1.38,1.45,v[1]);   // the shoulder cap goes with the arm
  const sh=sstep(0.06,0.13,ax)*sstep(1.39,1.47,v[1])*(1-a);
  spineW(m,v[1],1-a-sh);addW(m,P0+'Shoulder',sh);addW(m,P0+'Arm',a);
  return m;
}
const headWeights=v=>{const m=jw();spineW(m,v[1]);return m;};
const skirtWeights=v=>{const m=jw();spineW(m,v[1]);return m;};
const rigid=n=>()=>{const m=jw();addW(m,n,1);return m;};
const SKIRT=P('Stretch_Denim_FCL1PSD003_FRONT_4181');
const weightFn=p=>p===ARM?armWeights:p===TORSO||p===SHIRT?torsoWeights:p===HEADM?headWeights:p===SKIRT?skirtWeights:
  /hair|eye|tooth/.test(p.node)?rigid('Head'):rigid('Hips');

/* ---------- rebuild: bake to metres, add the skin ---------- */
const root=doc.getRoot(),scene=root.listScenes()[0],buf=root.listBuffers()[0];
const jointNodes=J.map(j=>doc.createNode(j.name));
J.forEach((j,i)=>{const p=j.parent==null?null:J[jIndex[j.parent]].pos;const t=p?sub(j.pos,p):j.pos;jointNodes[i].setTranslation(t);});
J.forEach((j,i)=>{if(j.parent!=null)jointNodes[jIndex[j.parent]].addChild(jointNodes[i]);});
const skel=doc.createNode('Armature');skel.addChild(jointNodes[0]);
const ibm=new Float32Array(J.length*16);J.forEach((j,i)=>{ibm.set([1,0,0,0, 0,1,0,0, 0,0,1,0, -j.pos[0],-j.pos[1],-j.pos[2],1],i*16);});
const skin=doc.createSkin('DealerSkin').setSkeleton(jointNodes[0]).setInverseBindMatrices(doc.createAccessor().setType('MAT4').setArray(ibm).setBuffer(buf));
jointNodes.forEach(n=>skin.addJoint(n));
const dealer=doc.createNode('Dealer');dealer.addChild(skel);
const meshNodes=[];
for(const p of prims){
  const prim=p.prim,M=p.M,n=p.n;
  prim.setAttribute('POSITION',doc.createAccessor().setType('VEC3').setArray(p.pos).setBuffer(buf));
  const rot=v=>nrm([M[0]*v[0]+M[4]*v[1]+M[8]*v[2],M[1]*v[0]+M[5]*v[1]+M[9]*v[2],M[2]*v[0]+M[6]*v[1]+M[10]*v[2]]);
  for(const name of['NORMAL','TANGENT']){const a=prim.getAttribute(name);if(!a)continue;const sz=a.getElementSize(),out=new Float32Array(n*sz),e=new Array(sz).fill(0);
    for(let i=0;i<n;i++){a.getElement(i,e);const r=rot(e);out.set(sz===4?[...r,e[3]]:r,i*sz);}
    prim.setAttribute(name,doc.createAccessor().setType(sz===4?'VEC4':'VEC3').setArray(out).setBuffer(buf));}
  if(p===ARM){            // long white sleeves: everything above the wrist cuff is sleeve; push it out a little for cloth thickness
    const nrmA=prim.getAttribute('NORMAL'),uvA=prim.getAttribute('TEXCOORD_0'),idx=prim.getIndices(),e=[0,0,0],sleeve=new Uint8Array(n);
    for(let i=0;i<n;i++){const v=vtx(p,i),I=sideInfo[v[0]>0?'Left':'Right'],t=dot(sub(v,I.W),I.A);
      const k=0.0045*(1-sstep(-0.034,-0.018,t));sleeve[i]=t<-0.024?1:0;
      if(k>0){nrmA.getElement(i,e);const r=rot(e);for(let c=0;c<3;c++)p.pos[i*3+c]+=r[c]*k;}}
    prim.getAttribute('POSITION').setArray(p.pos);
    const tris=[],uv=[0,0];for(let f=0;f<idx.getCount();f+=3){const a=idx.getScalar(f),b=idx.getScalar(f+1),c=idx.getScalar(f+2);
      if(sleeve[a]+sleeve[b]+sleeve[c]<2)continue;for(const i of[a,b,c]){uvA.getElement(i,uv);tris.push(+uv[0].toFixed(5),+uv[1].toFixed(5));}}
    (await import('fs')).writeFileSync(DST.replace(/\.glb$/,'-sleeves.json'),JSON.stringify(tris));
  }
  if(p===TORSO){          // under the blouse: the sides and armpits are cloth, not skin
    const uvA=prim.getAttribute('TEXCOORD_0'),idx=prim.getIndices(),uv=[0,0],tris=[];
    const cov=i=>{const v=vtx(p,i);return v[1]<1.47||(Math.abs(v[0])>0.1&&v[1]<1.6);};
    for(let f=0;f<idx.getCount();f+=3){const t=[idx.getScalar(f),idx.getScalar(f+1),idx.getScalar(f+2)];if(t.filter(cov).length<2)continue;
      for(const i of t){uvA.getElement(i,uv);tris.push(+uv[0].toFixed(5),+uv[1].toFixed(5));}}
    (await import('fs')).writeFileSync(DST.replace(/\.glb$/,'-torso.json'),JSON.stringify(tris));
  }
  const fn=weightFn(p),js=new Uint16Array(n*4),ws=new Float32Array(n*4);
  for(let i=0;i<n;i++){const m=fn(vtx(p,i));const top=[...m].filter(([,w])=>w>1e-4).sort((a,b)=>b[1]-a[1]).slice(0,4);const tot=top.reduce((s,[,w])=>s+w,0)||1;
    if(!top.length)top.push([jIndex.Hips,1]);top.forEach(([j,w],k)=>{js[i*4+k]=j;ws[i*4+k]=w/tot;});}
  prim.setAttribute('JOINTS_0',doc.createAccessor().setType('VEC4').setArray(js).setBuffer(buf));
  prim.setAttribute('WEIGHTS_0',doc.createAccessor().setType('VEC4').setArray(ws).setBuffer(buf));
  const node=doc.createNode(p.node).setMesh(doc.createMesh(p.node).addPrimitive(prim)).setSkin(skin);
  dealer.addChild(node);meshNodes.push(node);
}
for(const n of root.listNodes())if(!jointNodes.includes(n)&&n!==skel&&n!==dealer&&!meshNodes.includes(n))n.dispose();
for(const m of root.listMeshes())if(!meshNodes.some(n=>n.getMesh()===m))m.dispose();
for(const a of root.listAccessors())if(!a.listParents().some(x=>x!==root))a.dispose();
scene.addChild(dealer);
const ex=doc.getRoot().getAsset();ex.generator='auto-rigged for BlackJack 3D';
await io.write(DST,doc);
console.log('joints',J.length,'written',DST);
