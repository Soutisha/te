"""Tool-calling copilot. Intent->deterministic backend tool->answer with citations. No invented facts; optional LLM not required."""
from . import recovery, rag, evaluation, whatif, cybershield
def ask(db,q,role="admin"):
    t=q.lower()
    if "shortage" in t or "risk" in t:
        d=recovery.detect(db,"DealerA","P000"); return {"tool":"detect_shortage","answer":f"DealerA short by {d['shortage']} units; affected ROs: {', '.join(d['affected'])}","cites":d["affected"]}
    if "transfer" in t or "route" in t or "supplier" in t and "alternative" in t:
        p=recovery.plan(db,"DealerA","P000"); b=p["best"]; return {"tool":"plan_transfer","answer":f"Best source {b['source']} via {' > '.join(b['route'])}, cost {b['cost']}" if b else "no feasible source","cites":[b["source"]] if b else []}
    if "blocked" in t or "policy" in t:
        r=rag.RAG(rag.DOCS).query("restricted suppliers prohibited purchase approval",role); return {"tool":"rag","answer":r[0]["text"] if r else "no access","cites":[x["id"] for x in r]}
    if "security" in t or "incident" in t:
        a=cybershield.analyse(cybershield.simulate_attack()); return {"tool":"cybershield","answer":f"risk {a['risk']}: {', '.join(a['reasons'])}; actions: {', '.join(a['actions'])}","cites":["sup_x"]}
    if "report" in t:
        e=evaluation.compare(10); return {"tool":"evaluation","answer":f"Synthetic sim: resolution improvement {e['resolution_hours']['improvement_pct']}% (baseline modelled).","cites":["evaluation"]}
    return {"tool":None,"answer":"I can answer shortage, transfer, policy, security and report questions from backend tools.","cites":[]}
