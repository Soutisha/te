from .data import seed
from .recovery import plan,execute
from .audit import AuditChain
from .compliance import check_vendor
SCENARIOS={1:"stock_loss_80",2:"supplier_delay_48h",3:"highway_closure",4:"demand_x3",5:"warehouse_down",6:"supplier_noncompliant",7:"vendor_account_attack"}
def run(n):
    db=seed(); au=AuditChain(); blocked=[]; out={"scenario":SCENARIOS[n]}
    before=plan(db,"DealerA","P000")["shortage"]["shortage"]
    if n==1:
        for s in db["stock"]: 
            if s!="DealerA": db["stock"][s]["P000"]//=5
    if n==3: blocked=[("DealerA","WH1"),("DealerA","WH2")]
    if n==4:
        for r in db["ros"]:
            if r["part"]=="P000": r["qty"]*=3
    if n==5: db["stock"]["WH1"]["P000"]=0
    if n==6: out["compliance"]=check_vendor(db["vendors"],"V2",100)
    if n==2: out["note"]="48h supplier delay: internal transfer used instead of PO"
    if n==7:
        from .cybershield import analyse,simulate_attack; out["security"]=analyse(simulate_attack())
    pl=plan(db,"DealerA","P000",blocked); out["shortage_before"]=before; out["shortage_after_disruption"]=pl["shortage"]["shortage"]
    r=execute(db,pl,"inventory_manager",au) if n!=7 else {"ok":False,"held":"transaction held pending security review"}
    out["recovery"]=r; out["audit_valid"]=au.verify(); return out
