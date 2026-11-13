"""Telemetry feed adapter. Reads ONE read-only snapshot and validates its schema.
 * TELEMETRY_URL unset  -> the built-in SYNTHETIC feed (/mock/telemetry/v1/snapshot, generated from data/*.csv). Labelled SIMULATED.
 * TELEMETRY_URL set    -> a real HTTPS call (optional TELEMETRY_TOKEN bearer). LIVE only if the call succeeds and the schema validates.
A failed live call is reported as ERROR. It never silently falls back to synthetic data."""
import json, time, urllib.request
from datetime import datetime, timezone
SCHEMA="1.0"
def validate(s):
    """Returns a list of schema problems (empty = valid)."""
    e=[]
    if not isinstance(s,dict): return ["snapshot is not a JSON object"]
    f=s.get("feed") or {}
    if f.get("schema_version")!=SCHEMA: e.append(f"feed.schema_version must be {SCHEMA}")
    if f.get("read_only") is not True: e.append("feed.read_only must be true")
    inv=s.get("inventory") or {}
    if not isinstance(inv.get("sites"),list) or not inv["sites"]: e.append("inventory.sites must be a non-empty list")
    else:
        for i,x in enumerate(inv["sites"]):
            if not isinstance(x.get("site"),str) or not isinstance(x.get("units"),int) or x["units"]<0: e.append(f"inventory.sites[{i}] needs site:str and units:int>=0")
    for k in ("repairs","deliveries","source"):
        if not isinstance(s.get(k),dict): e.append(f"missing object: {k}")
    return e
def fetch(url,token,local_snapshot):
    t0=time.perf_counter(); now=datetime.now(timezone.utc).isoformat()
    base={"fetched_at":now,"url":url or "local:/mock/telemetry/v1/snapshot"}
    try:
        if url:
            if not url.lower().startswith("https://") and not url.lower().startswith("http://localhost"): raise ValueError("TELEMETRY_URL must be https:// (or http://localhost for development)")
            req=urllib.request.Request(url,headers={"Accept":"application/json",**({"Authorization":"Bearer "+token} if token else {})})
            with urllib.request.urlopen(req,timeout=5) as r: snap=json.loads(r.read().decode())
        else: snap=local_snapshot()
    except Exception as ex:
        return {**base,"status":"ERROR","kind":"external" if url else "synthetic","errors":[f"{type(ex).__name__}: {ex}"],"latency_ms":round((time.perf_counter()-t0)*1000,1)}
    errs=validate(snap); ms=round((time.perf_counter()-t0)*1000,1)
    kind="external" if url else "synthetic"
    status="ERROR" if errs else ("LIVE" if url else "SIMULATED")
    inv=snap.get("inventory") or {}
    return {**base,"status":status,"kind":kind,"provenance":(snap.get("source") or {}).get("provenance","unknown"),"errors":errs,"latency_ms":ms,
            "feed":snap.get("feed"),"summary":None if errs else {"sites":len(inv["sites"]),"total_units":sum(x["units"] for x in inv["sites"]),"repair_orders":(snap.get("repairs") or {}).get("total"),"deliveries":(snap.get("deliveries") or {}).get("total")},
            "label":"SYNTHETIC FEED (generated locally, not a real dealership)" if not url else "EXTERNAL FEED (validated)"}
