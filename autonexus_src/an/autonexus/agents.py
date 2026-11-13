"""Deterministic six-agent orchestrator (LangGraph not installed; same node/state/checkpoint pattern, no LLM)."""
from . import recovery, compliance, cybershield, optim
class Orchestrator:
    def __init__(s,db,audit,max_retries=2): s.db,s.audit,s.max=db,audit,max_retries; s.state={"trace":[],"status":"new"}
    def _run(s,agent,tool,fn):
        for i in range(s.max+1):
            try:
                r=fn(); s.state["trace"].append({"agent":agent,"tool":tool,"ok":True,"summary":r.get("summary"),"attempt":i+1}); return r
            except Exception as e: err=str(e)
        s.state["trace"].append({"agent":agent,"tool":tool,"ok":False,"error":err}); raise RuntimeError(err)
    def run(s,dealer="DealerA",part="P000",blocked=(),vendor="V2",attack=True):
        st=s.state; db=s.db
        sh=s._run("Predictive","detect_shortage",lambda:{**recovery.detect(db,dealer,part),"summary":"shortage detected"}); st["shortage"]=sh
        if not sh["shortage"]: st["status"]="no_action"; return st
        pl=s._run("Inventory","plan_transfer",lambda:{"plan":recovery.plan(db,dealer,part,blocked),"summary":"sources searched, routes computed"}); st["plan"]=pl["plan"]
        amt=sh["shortage"]*50
        cv=s._run("Vendor","check_vendor",lambda:{**compliance.check_vendor(db["vendors"],vendor,amt),"summary":"vendor policy"}); st["vendor_check"]=cv
        if attack:
            an=s._run("Compliance&Security","analyse_events",lambda:{**cybershield.analyse(cybershield.simulate_attack()),"summary":"suspicious account contained"}); st["security"]=an
        st["blocked_vendors"]=[] if cv["approved"] else [vendor]
        jobs=[(r["id"],"brakes",r["priority"]) for r in db["ros"] if r["dealer"]==dealer and r["part"]==part][:5]
        techs={"T1":{"brakes"},"T2":{"engine"},"T3":{"brakes","engine"}}
        sc=s._run("Scheduling","assign",lambda:{"assignment":optim.assign(techs,jobs),"summary":"hungarian assignment"}); st["schedule"]=sc["assignment"]
        st["status"]="awaiting_approval"; s.audit.add("orchestrator","approval_requested",st["plan"].get("best"),"pending"); return st
    def approve(s,role):
        if s.state.get("status")!="awaiting_approval":
            return {"ok":False,"error":"No agent approval is pending.",
                    "status":s.state.get("status")}
        r=recovery.execute(s.db,s.state["plan"],role,s.audit)
        s.state["result"]=r
        if r.get("error")=="approval not authorised":
            return s.state
        s.state["status"]="recovered" if r.get("verified") else "failed"
        return s.state
