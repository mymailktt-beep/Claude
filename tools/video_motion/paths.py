import json,math,sys
S=sys.argv[1]
t=json.load(open(S+'/track.json'))
W,H=960,720
CAM=(1.691,2.738,2.082);LOOK=(0.487,1.159,0.892);FOV=31.288;TABLE_Y=0.96
def sub(a,b):return [a[i]-b[i] for i in range(3)]
def nrm(a):l=math.sqrt(sum(x*x for x in a));return [x/l for x in a]
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
f=nrm(sub(LOOK,CAM));r=nrm(cross(f,[0,1,0]));u=cross(r,f);k=math.tan(math.radians(FOV)/2)
def ray(px,py,h):
    x=(px-W/2)/(H/2)*k;y=-(py-H/2)/(H/2)*k
    d=[f[i]+r[i]*x+u[i]*y for i in range(3)]
    s=(TABLE_Y+h-CAM[1])/d[1];return [CAM[i]+d[i]*s for i in range(3)]
# dealer's hands: over the felt, above the rail line
def palm(h):return [(h['wrist'][0]+h['mid_mcp'][0])/2,(h['wrist'][1]+h['mid_mcp'][1])/2]
tracks={'R':[],'L':[]}   # dealer's right hand is on screen-left
prev={'R':None,'L':None}
for rec in t:
    cand=[h for h in rec['hands'] if palm(h)[1]<470 and palm(h)[0]>40]
    pts=[(palm(h),h['index_tip']) for h in cand]
    assign={'R':None,'L':None}
    if len(pts)>=2:
        pts=sorted(pts,key=lambda p:p[0][0])[:2]
        a,b=pts
        if prev['R'] and prev['L']:
            c1=math.dist(a[0],prev['R'])+math.dist(b[0],prev['L']);c2=math.dist(b[0],prev['R'])+math.dist(a[0],prev['L'])
            assign['R'],assign['L']=(a,b) if c1<=c2 else (b,a)
        else: assign['R'],assign['L']=a,b
    elif len(pts)==1:
        p=pts[0]
        if prev['R'] and prev['L']:
            side='R' if math.dist(p[0],prev['R'])<math.dist(p[0],prev['L']) else 'L'
        else: side='R' if p[0][0]<560 else 'L'
        if prev[side] and math.dist(p[0],prev[side])>120: side='L' if side=='R' else 'R'
        assign[side]=p
    for s in 'RL':
        if assign[s] and (prev[s] is None or math.dist(assign[s][0],prev[s])<140):
            prev[s]=assign[s][0];pw=ray(*assign[s][0],0.035);ti=ray(*assign[s][1],0.01)
            tracks[s].append({'t':rec['t'],'px':assign[s][0],'palm':pw,'tip':ti})
        else: tracks[s].append({'t':rec['t'],'px':None})
json.dump(tracks,open(S+'/paths.json','w'))
for s in 'RL':print(s,sum(1 for x in tracks[s] if x['px']),'of',len(tracks[s]))
