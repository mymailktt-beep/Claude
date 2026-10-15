import {NodeIO} from '@gltf-transform/core';
import {ALL_EXTENSIONS} from '@gltf-transform/extensions';
export async function load(path){
  const io=new NodeIO().registerExtensions(ALL_EXTENSIONS);const doc=await io.read(path);
  const prims=[];
  for(const node of doc.getRoot().listNodes()){const mesh=node.getMesh();if(!mesh)continue;
    const M=node.getWorldMatrix();
    for(const p of mesh.listPrimitives()){const pos=p.getAttribute('POSITION'),n=pos.getCount(),out=new Float32Array(n*3),v=[0,0,0];
      for(let i=0;i<n;i++){pos.getElement(i,v);const x=v[0],y=v[1],z=v[2];
        out[i*3]=(M[0]*x+M[4]*y+M[8]*z+M[12])/1000;out[i*3+1]=(M[1]*x+M[5]*y+M[9]*z+M[13])/1000;out[i*3+2]=(M[2]*x+M[6]*y+M[10]*z+M[14])/1000;}
      prims.push({node:node.getName(),mat:p.getMaterial()?.getName(),n,pos:out,prim:p,M});}}
  return {io,doc,prims};
}
