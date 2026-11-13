from .algorithms import graph,dijkstra,astar
from .compliance import check_vendor,allowed
from .audit import AuditChain
def detect(db,dealer,part,required_qty=None):
    need=required_qty if required_qty is not None else sum(r["qty"] for r in db["ros"] if r["dealer"]==dealer and r["part"]==part and r["id"] not in db["closed"])
    have=db["stock"][dealer][part]
    return {"shortage":max(0,need-have),"need":need,"have":have,"affected":[r["id"] for r in db["ros"] if r["dealer"]==dealer and r["part"]==part]}
def plan(db,dealer,part,blocked=(),required_qty=None,network=None):
    sh=detect(db,dealer,part,required_qty); 
    if not sh["shortage"]: return {"status":"no_shortage",**sh}
    g=graph(blocked,**network) if network else graph(blocked); opts=[]
    for site,st in db["stock"].items():
        if site==dealer or st[part]<sh["shortage"]: continue
        r=astar(g,site,dealer,positions=network["nodes"]) if network else astar(g,site,dealer)
        if r["path"]: opts.append({"source":site,"qty":sh["shortage"],"route":r["path"],"cost":r["cost"],"nodes_explored":len(r["visited"])})
    opts.sort(key=lambda o:o["cost"])
    return {"status":"planned","part":part,"shortage":sh,"options":opts,"best":opts[0] if opts else None}
def execute(db,pl,approver_role,audit:AuditChain):
    if not pl.get("best"): return {"ok":False,"error":"no feasible source"}
    if not allowed(approver_role,"transfer:approve"): audit.add(approver_role,"transfer_denied",pl["best"],"rejected"); return {"ok":False,"error":"approval not authorised"}
    b=pl["best"]; d=pl["shortage"]
    dealer=b["route"][-1]
    if db["stock"][b["source"]][d_part(db,pl)]<b["qty"]: return {"ok":False,"error":"insufficient stock"}
    p=d_part(db,pl); db["stock"][b["source"]][p]-=b["qty"]; db["stock"][dealer][p]+=b["qty"]
    audit.add(approver_role,"transfer_executed",b,"approved")
    v=detect(db,dealer,p); return {"ok":v["shortage"]==0,"verified":v["shortage"]==0,"after":v}
def d_part(db,pl): return pl.get("part","P000")
