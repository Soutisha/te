import numpy as np
from sklearn.ensemble import IsolationForest
def simulate_attack():
    """Isolated, in-memory simulation. No network activity."""
    ev=[{"t":i,"acct":"sup_x","action":"login","hour":10,"ip":"10.0.0.5"} for i in range(3)]
    ev+= [{"t":10,"acct":"sup_x","action":"login","hour":3,"ip":"203.0.113.9"},{"t":11,"acct":"sup_x","action":"stock_update","hour":3,"ip":"203.0.113.9"},{"t":12,"acct":"sup_x","action":"purchase_request","hour":3,"ip":"203.0.113.9","amount":90000}]
    return ev
def analyse(events,vendor_role_perms=()):
    score=0;why=[]
    known={e["ip"] for e in events[:3]}
    for e in events[3:]:
        if e["ip"] not in known: score+=30; why.append("new IP")
        if e["hour"]<6: score+=15; why.append("off-hours")
        if e["action"]=="stock_update" and "inventory:update" not in vendor_role_perms: score+=35; why.append("unauthorised stock update")
        if e.get("amount",0)>10000: score+=25; why.append("abnormal purchase amount")
    score=min(100,score); res={"risk":score,"reasons":sorted(set(why)),"contained":score>=70}
    res["actions"]=["lock account","hold transaction","escalate to Security Analyst"] if res["contained"] else []
    return res
def behaviour_model(seed=0):
    r=np.random.default_rng(seed); X=r.normal([5,1],[1,.5],(300,2)); return IsolationForest(random_state=seed,contamination=.02).fit(X)
