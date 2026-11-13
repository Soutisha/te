"""Federated learning (FedAvg) over 5 dealership datasets read from data/historical_demand.csv.
Own FedAvg implementation (numpy logistic regression). Flower is optional and not used here."""
import csv, numpy as np
from sklearn.metrics import f1_score, average_precision_score, roc_auc_score
F=["stock","avg_demand","demand_std","lead_time","reliability","pending_ros","season","incoming"]
def load(path="data/historical_demand.csv"):
    c={}
    with open(path, newline="", encoding="utf-8-sig") as stream:
        for r in csv.DictReader(stream):
            c.setdefault(r["dealership_id"],[]).append(r)
    out={}
    for d,rs in c.items():
        X=np.array([[float(r[f]) for f in F] for r in rs]); y=np.array([int(r["stockout_next7"]) for r in rs]); day=np.array([int(r["day"]) for r in rs])
        out[d]=(X,y,day)
    return out
def sig(z): return 1/(1+np.exp(-np.clip(z,-30,30)))
def local(w,X,y,epochs=5,lr=.1):
    w=w.copy()
    for _ in range(epochs):
        p=sig(X@w); w-=lr*(X.T@(p-y)/len(y)+1e-3*w)
    return w
def metrics(w,X,y):
    p=sig(X@w); return {"f1":float(f1_score(y,p>.4)),"pr_auc":float(average_precision_score(y,p)),"roc_auc":float(roc_auc_score(y,p)),"accuracy":float(((p>.4)==y).mean())}
def run(path="data/historical_demand.csv",rounds=25,seed=0):
    D=load(path); allX=np.vstack([v[0] for v in D.values()]); mu,sd=allX.mean(0),allX.std(0)+1e-9  # shared normalisation stats (a simplification: reveals aggregate moments)
    prep=lambda X:np.hstack([(X-mu)/sd,np.ones((len(X),1))])
    tr={d:(prep(X[day<90]),y[day<90]) for d,(X,y,day) in D.items()}; te={d:(prep(X[day>=100]),y[day>=100]) for d,(X,y,day) in D.items()}
    TX=np.vstack([v[0] for v in te.values()]); TY=np.concatenate([v[1] for v in te.values()])
    k=TX.shape[1]; w=np.zeros(k); curve=[]
    for _ in range(rounds):
        ws=[];ns=[]
        for d,(X,y) in tr.items(): ws.append(local(w,X,y)); ns.append(len(y))
        w=np.average(ws,axis=0,weights=ns); curve.append(metrics(w,TX,TY)["f1"])
    fed=metrics(w,TX,TY)
    cw=np.zeros(k); CX=np.vstack([v[0] for v in tr.values()]); CY=np.concatenate([v[1] for v in tr.values()]); ccurve=[]
    for _ in range(rounds): cw=local(cw,CX,CY); ccurve.append(metrics(cw,TX,TY)["f1"])
    cen=metrics(cw,TX,TY)
    loc={}
    for d,(X,y) in tr.items():
        lw=np.zeros(k)
        for _ in range(rounds): lw=local(lw,X,y)
        loc[d]=metrics(lw,TX,TY)["f1"]
    comm=rounds*len(tr)*k*8*2
    return {"label":"SYNTHETIC DEMONSTRATION RESULTS","rounds":rounds,"clients":list(tr),"federated":fed,"centralised":cen,"local_only_f1":loc,"local_only_mean_f1":float(np.mean(list(loc.values()))),
            "fed_f1_curve":curve,"central_f1_curve":ccurve,"communication_bytes_federated":comm,"raw_bytes_centralised":int(CX.nbytes),
            "privacy_note":"Raw rows stay local; weight updates are shared. No secure aggregation or differential privacy is implemented, so this is NOT a privacy guarantee."}
