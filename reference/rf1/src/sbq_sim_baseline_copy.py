import numpy as np, math, json
src=open('sim_head1.py').read().split("# ======================= S4")[0]; ns={}; exec(src,ns)
Mutual=ns["Mutual"]; TXs=ns["TXs"]; M_mono=ns["M_mono"]; Bvec_many=ns["Bvec_many"]; TXB=ns["TXB"]; quad_old=ns["quad"]; wf=ns["wf"]
G=json.load(open("kit_v22/sbq_geometry.json")); W,T=0.8e-3,35e-6; mu0=4e-7*math.pi
ZA=[3.18,3.00,2.62,2.44]; ZB=[2.08,1.90,1.52,1.34]
def rot(a,deg):
    c,s=math.cos(math.radians(deg)),math.sin(math.radians(deg)); a=np.asarray(a,float); return np.c_[a[:,0]*c-a[:,1]*s,a[:,0]*s+a[:,1]*c]
def paths(deg,zl,dx=0.0,dy=0.0,terminals=True):
    B=(deg!=0.0); out=[]; P1,P2=(G["padsB"] if B else G["pads"]); deg=0.0
    for li,polys in (G["layersB"] if B else G["layers"]).items():
        for i,p in enumerate(polys):
            p=np.asarray(p,float); isterm=(int(li)==0 and (abs(p[-1]-np.array(P1)).max()<1e-6 or abs(p[-1]-np.array(P2)).max()<1e-6))
            if isterm and not terminals: continue
            if isterm and abs(p[-1]-np.array(P1)).max()<1e-6: p=p[::-1]            # terminal 1 is stored coil->pad; current flows pad->coil
            q=rot(p,deg); out.append(np.c_[q[:,0]*1e-3+dx*1e-3,q[:,1]*1e-3+dy*1e-3,np.full(len(q),zl[int(li)]*1e-3)])
    if terminals:                                       # closing chord between this board's own pads (board B used board A's pads before)
        a=np.array(P2); b=np.array(P1); q=rot(np.array([a,b]),deg); out.append(np.c_[q[:,0]*1e-3+dx*1e-3,q[:,1]*1e-3+dy*1e-3,np.full(2,zl[0]*1e-3)])   # closing wire P2->P1
    return out
def sub(ps,step=1): return [p[::step] for p in ps]
res={}
didt=max(np.max(np.abs(np.gradient(w[1],w[0]))) for w in wf.values()); pk=abs(M_mono)*didt
for nm,deg,zl in (("QUAD-A board",0.0,ZA),("QUAD-B board (rotated 45 deg)",45.0,ZB)):
    row={}
    for lab,(dx,dy) in (("aligned",(0,0)),("0.1 mm x",(0.1,0)),("0.5 mm x",(0.5,0)),("0.5 mm y",(0,0.5))):
        for tm in (True,False):
            M=Mutual(TXs,sub(paths(deg,zl,dx,dy,tm)))/6.0; row[f"{lab}{'' if tm else ' (lobes only)'}"]=dict(rel=abs(M)/abs(M_mono),peak_V=abs(M)/abs(M_mono)*pk)
    res[nm]=row; print(nm,{k:f"{v['peak_V']*1e3:.2f} mV" for k,v in row.items()})
# self inductance of board A (series chain incl. terminals), partial-inductance sum with GMD floor
def selfL(ps):
    segs=[]; 
    for p in ps: d=np.diff(p,axis=0); m=(p[:-1]+p[1:])/2; segs.append((d,m))
    d=np.vstack([s[0] for s in segs]); m=np.vstack([s[1] for s in segs]); gmd=0.2235*(W+T); tot=0.0; n=len(d)
    for a in range(0,n,400):
        r=np.sqrt(((m[a:a+400,None,:]-m[None,:,:])**2).sum(2)); r=np.maximum(r,gmd); tot+=np.sum((d[a:a+400]@d.T)/r)
    return 1e-7*tot
LA=selfL(paths(0.0,ZA,0,0,True)); length=sum(float(np.sqrt((np.diff(p,axis=0)**2).sum(1)).sum()) for p in paths(0.0,ZA,0,0,False))
R1=1.72e-8*length/(W*T); R2=1.72e-8*length/(W*70e-6)
print("L(uH)",round(LA*1e6,1),"length m",round(length,2),"R 1oz",round(R1,1),"R 2oz",round(R2,1))
# signal pattern and strength against the earlier idealised quadrupole
phis=np.radians(np.arange(0,360,15)); out={}
for depth,rho in ((0.10,0.06),(0.10,0.10),(0.20,0.08)):
    pts=np.c_[rho*np.cos(phis),rho*np.sin(phis),np.full(len(phis),-depth)]; Bt=TXB(pts)
    A=np.einsum('ij,ij->i',Bt,Bvec_many(paths(0.0,ZA,0,0,True),pts)); B=np.einsum('ij,ij->i',Bt,Bvec_many(paths(45.0,ZB,0,0,True),pts))
    qa=np.einsum('ij,ij->i',Bt,Bvec_many(quad_old,pts)); 
    est=(0.5*np.degrees(np.arctan2(B,A)))%180; true=np.degrees(phis)%180; off=((est-true+90)%180)-90; off0=np.median(off); err=((off-off0+90)%180)-90
    amp=np.hypot(A,B); out[f"depth {int(depth*1000)} mm, radius {int(rho*1000)} mm"]=dict(bearing_offset_deg=round(float(off0),1),bearing_scatter_deg=round(float(np.sqrt(np.mean(err**2))),2),rss_flat_max_over_min=round(float(amp.max()/amp.min()),3),signal_vs_idealised_quad_A=round(float(np.max(np.abs(A))/np.max(np.abs(qa))),2))
for k,v in out.items(): print(k,v)
json.dump(dict(leak=res,L_uH=round(LA*1e6,1),length_m=round(length,2),R_1oz_ohm=round(R1,1),R_2oz_ohm=round(R2,1),unnulled_peak_V=round(pk,1),pattern=out),open("kit_v22/sbq_sim.json","w"),indent=1,default=float)
