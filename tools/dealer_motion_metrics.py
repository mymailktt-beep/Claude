# Motion metrics for a dealer trace (JSON frames with dt, L/R hand position+quaternion, head quaternion):
# hand speed, acceleration spikes, wrist and head turn rates. Usage: python3 dealer_motion_metrics.py trace.json [v]
import json,sys,math
tr=json.load(open(sys.argv[1]));verbose=len(sys.argv)>2
def ang(q1,q2):
    d=abs(sum(a*b for a,b in zip(q1,q2)));return 2*math.degrees(math.acos(min(1,d)))
T=[f['t'] for f in tr];D=[f['dt'] for f in tr]
import statistics;print('dt median %.1fms max %.1fms'%(statistics.median(D)*1000,max(D)*1000))
print('frames',len(tr))
for s in ['L','R']:
    P=[f[s][:3] for f in tr];Q=[f[s][3:] for f in tr]
    v=[[ (P[i+1][k]-P[i][k])/max(1e-3,D[i+1]) for k in range(3)] for i in range(len(P)-1)]
    spd=[math.hypot(*x) for x in v]
    acc=[math.dist(v[i+1],v[i])/max(1e-3,D[i+1]) for i in range(len(v)-1)]
    rot=[ang(Q[i],Q[i+1])/max(1e-3,D[i+1]) for i in range(len(Q)-1)]
    print(s,'max speed %.2f m/s'%max(spd),'| accel>40 frames',sum(a>40 for a in acc),'| wrist >400°/s frames',sum(r>400 for r in rot),'max %.0f°/s'%max(rot))
    if verbose:
        for i,r in enumerate(rot):
            if r>400 or spd[i]>3: print('  ',s,'t=%.0f'%T[i],tr[i]['ph'],'spd %.2f rot %.0f'%(spd[i],r))
H=[f['H'] for f in tr];hr=[ang(H[i],H[i+1])/max(1e-3,D[i+1]) for i in range(len(H)-1)]
print('head >250°/s frames',sum(r>250 for r in hr),'max %.0f°/s'%max(hr))
if verbose:
    for i,r in enumerate(hr):
        if r>250:print('   head t=%.0f'%T[i],tr[i]['ph'],'%.0f'%r)
