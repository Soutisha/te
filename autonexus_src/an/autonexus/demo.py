"""120-second guided demo: each step runs real backend code and mutates real state."""
from .data import seed
from .audit import AuditChain
from . import agents,recovery,ml
STEPS=[(0,"PredictX predicts shortage"),(10,"Affected repair orders"),(20,"Inventory agent finds stock"),(30,"Vendor + invoice check"),(40,"CyberShield flags supplier"),(50,"ComplyAI blocks vendor"),(60,"Route computed"),(70,"Road closure -> recalculation"),(80,"Alternative route shown"),(90,"Scheduling reassigns techs/bays"),(105,"Manager approves"),(115,"Recovery verified")]
class Demo:
    def __init__(s): s.db=seed(); s.au=AuditChain(); s.o=agents.Orchestrator(s.db,s.au); s.i=0; s.paused=False; s.log=[]
    def restart(s): s.__init__()
    def pause(s): s.paused=True
    def resume(s): s.paused=False
    def skip(s,to): s.i=to
    def step(s):
        if s.paused or s.i>=len(STEPS): return None
        t,name=STEPS[s.i]; ev={"t":t,"step":name}
        if s.i==0: ev["data"]=recovery.detect(s.db,"DealerA","P000")
        if s.i==6: ev["data"]=recovery.plan(s.db,"DealerA","P000")["best"]
        if s.i==7: s.blocked=[("DealerA","WH1")]; ev["data"]=recovery.plan(s.db,"DealerA","P000",s.blocked)["best"]
        if s.i==9: s.o.run(blocked=getattr(s,"blocked",())); ev["data"]=s.o.state["schedule"]
        if s.i==10: ev["data"]=s.o.approve("inventory_manager")["status"]
        if s.i==11: ev["data"]={"verified":recovery.detect(s.db,"DealerA","P000")["shortage"]==0,"audit_valid":s.au.verify()}
        s.log.append(ev); s.i+=1; return ev
    def run_all(s):
        while s.i<len(STEPS): s.step()
        return s.log
