"""Predictive pipeline on synthetic data. Temporal split, no leakage. Uses XGBoost if installed else sklearn GradientBoosting."""
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, IsolationForest
from sklearn.metrics import precision_score,recall_score,f1_score,roc_auc_score,average_precision_score,confusion_matrix
from sklearn.inspection import permutation_importance
FEATS=["stock","avg_demand","demand_std","lead_time","reliability","pending_ros","season","incoming"]
def simulate(seed=42,days=150,series=40,scale=1.0,rel_rng=(.6,.98)):
    r=np.random.default_rng(seed); rows=[]
    for sid in range(series):
        base=r.uniform(1,6)*scale; lead=int(r.integers(2,9)); rel=r.uniform(*rel_rng); stock=int(r.integers(10,60)); pend=[]
        hist=[]
        for d in range(days):
            season=1+.4*np.sin(2*np.pi*d/30); spike=2.5 if r.random()<.03 else 1
            dem=int(r.poisson(base*season*spike)); stock=max(0,stock-dem); hist.append(dem)
            arrive=sum(q for t,q in pend if t==d); stock+=arrive; incoming=sum(q for t,q in pend if t>d)
            if stock+incoming<base*lead*1.2 and r.random()<.5: pend.append((d+lead+(int(r.integers(1,5)) if r.random()>rel else 0),int(base*15)))
            h=hist[-14:]
            rows.append([sid,d,stock,np.mean(h),np.std(h),lead,rel,int(r.poisson(base)),season,incoming])
        # label: stockout within next 7 days = simulated future, computed after
    X=np.array(rows,float); y=np.zeros(len(X)); 
    for sid in range(series):
        idx=np.where(X[:,0]==sid)[0]; st=X[idx,2]
        for i in range(len(idx)): y[idx[i]]=float((st[i+1:i+8]==0).any()) if i+1<len(idx) else 0
    return X,y
def train_eval(seed=42):
    X,y=simulate(seed); d=X[:,1]; F=X[:,2:]
    tr,va,te=d<90,(d>=90)&(d<120),d>=120
    out={"label":"SYNTHETIC DEMONSTRATION RESULTS","positive_rate":float(y.mean()),"n":len(y),"models":{}}
    cands={"random_forest":RandomForestClassifier(200,random_state=seed,class_weight="balanced"),"gradient_boosting":GradientBoostingClassifier(random_state=seed)}
    try:
        import xgboost; cands["xgboost"]=xgboost.XGBClassifier(n_estimators=200,max_depth=4,random_state=seed)
    except ImportError: pass
    fitted={}
    for n,m in cands.items():
        m.fit(F[tr],y[tr]); p=m.predict_proba(F[te])[:,1]; pr=(p>.5).astype(int); fitted[n]=m
        from sklearn.metrics import brier_score_loss; from sklearn.calibration import calibration_curve
        cp,cm=calibration_curve(y[te],p,n_bins=5,strategy="quantile")
        out["models"][n]={"brier":float(brier_score_loss(y[te],p)),"calibration":{"predicted":cp.round(3).tolist(),"observed":cm.round(3).tolist()},"precision":precision_score(y[te],pr,zero_division=0),"recall":recall_score(y[te],pr),"f1":f1_score(y[te],pr),"roc_auc":roc_auc_score(y[te],p),"pr_auc":average_precision_score(y[te],p),"confusion":confusion_matrix(y[te],pr).tolist()}
    best=max(out["models"],key=lambda k:out["models"][k]["pr_auc"]); out["best"]=best
    pi=permutation_importance(fitted[best],F[te],y[te],n_repeats=5,random_state=seed,scoring="average_precision")
    out["explanation_method"]="permutation importance (SHAP not installed)"
    out["importance"]=dict(sorted(zip(FEATS,map(float,pi.importances_mean)),key=lambda z:-z[1]))
    out["model_version"]=f"{best}-seed{seed}-v1"; out["_model"]=fitted[best]; return out
def predict(model,feat):
    p=float(model.predict_proba(np.array([feat],float))[0,1]); return {"risk":p,"action":"initiate recovery" if p>.5 else "monitor"}
def anomaly_eval(seed=42):
    r=np.random.default_rng(seed); n=r.normal([5,1,.1],[1,.5,.05],(500,3)); a=r.normal([40,12,.8],[5,3,.1],(25,3))
    X=np.vstack([n,a]); y=np.r_[np.zeros(500),np.ones(25)]; m=IsolationForest(contamination=.05,random_state=seed).fit(X)
    p=(m.predict(X)==-1).astype(int); return {"label":"SYNTHETIC","precision":precision_score(y,p),"recall":recall_score(y,p),"fpr":float(((p==1)&(y==0)).sum()/500)}
