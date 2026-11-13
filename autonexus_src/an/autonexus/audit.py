import hashlib, json, time
class AuditChain:
    def __init__(s): s.rec=[]
    def add(s,actor,action,resource,decision=None):
        prev=s.rec[-1]["hash"] if s.rec else "0"*64
        r={"id":len(s.rec)+1,"ts":time.time(),"actor":actor,"action":action,"resource":resource,"decision":decision,"prev":prev}
        r["hash"]=hashlib.sha256(json.dumps(r,sort_keys=True).encode()).hexdigest(); s.rec.append(r); return r
    def verify(s):
        prev="0"*64
        for r in s.rec:
            b={k:v for k,v in r.items() if k!="hash"}
            if b["prev"]!=prev or hashlib.sha256(json.dumps(b,sort_keys=True).encode()).hexdigest()!=r["hash"]: return False
            prev=r["hash"]
        return True
