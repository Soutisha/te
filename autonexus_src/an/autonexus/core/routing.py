"""Route Intelligence. Road-network graph from the database; optional OSRM provider for real road ETA.
Straight-line distance is never used as road distance, and a locally computed ETA is always labelled as such."""
import math
from sqlalchemy import select
from .. import config
from ..algorithms import astar
from . import models as m

def _load(s):
    sites = {x.id: x for x in s.scalars(select(m.Site))}
    edges = {(e.a, e.b): e for e in s.scalars(select(m.RoadEdge))}
    return sites, edges

def _graph(edges, blocked):
    g = {}
    for (a, b), e in edges.items():
        if (a, b) in blocked or (b, a) in blocked: continue
        g.setdefault(a, {})[b] = e.cost; g.setdefault(b, {})[a] = e.cost
    return g

def _edge(edges, a, b): return edges.get((a, b)) or edges.get((b, a))

def _search(sites, edges, src, dst, blocked):
    g = _graph(edges, blocked)
    for n in sites: g.setdefault(n, {})
    nodes = {k: (v.lon, v.lat) for k, v in sites.items()}
    r = astar(g, src, dst, positions=nodes)
    if not r["path"]: return None
    legs = [_edge(edges, a, b) for a, b in zip(r["path"], r["path"][1:])]
    return {"path": r["path"], "cost": r["cost"], "distance_km": round(sum(l.distance_km for l in legs), 2), "time_min": round(sum(l.time_min for l in legs), 1)}

def _osrm(sites, src, dst):
    if config.get("OFFLINE_MODE", "1") == "1": return None, "offline mode enabled"
    url = config.get("OSRM_URL").rstrip("/")
    if not url: return None, "OSRM_URL not configured"
    try:
        import httpx
        a, b = sites[src], sites[dst]
        r = httpx.get(f"{url}/route/v1/driving/{a.lon},{a.lat};{b.lon},{b.lat}", params={"overview": "false"}, timeout=4.0)
        r.raise_for_status(); j = r.json()["routes"][0]
        return {"distance_km": round(j["distance"] / 1000, 2), "time_min": round(j["duration"] / 60, 1)}, None
    except Exception as e: return None, f"{type(e).__name__}: {e}"

def route(s, src, dst, blocked=()):
    sites, edges = _load(s)
    for n in (src, dst):
        if n not in sites: return {"status": "unknown_site", "site": n}
    blocked = {tuple(b) for b in blocked}
    best = _search(sites, edges, src, dst, blocked)
    if not best: return {"status": "unavailable", "source": src, "destination": dst, "blocked": sorted(map(list, blocked)),
                         "message": "no road path with the given closures; no ETA produced"}
    alt = None
    for a, b in zip(best["path"], best["path"][1:]):
        c = _search(sites, edges, src, dst, blocked | {(a, b)})
        if c and c["path"] != best["path"] and (alt is None or c["cost"] < alt["cost"]): alt = c
    prov, err = _osrm(sites, src, dst)
    eta = prov["time_min"] if prov else best["time_min"]
    return {"status": "ok", "source": src, "destination": dst, "best": best, "alternative": alt,
            "comparison": None if not alt else {"extra_distance_km": round(alt["distance_km"] - best["distance_km"], 2), "extra_time_min": round(alt["time_min"] - best["time_min"], 1)},
            "eta_minutes": eta,
            "eta_basis": "provider:osrm (direct road route)" if prov else "local planning estimate from road_network edge times; NOT a provider ETA",
            "provider": {"name": "osrm", "configured": bool(config.get("OSRM_URL")), "ok": bool(prov), "error": err},
            "blocked": sorted(map(list, blocked)),
            "explanation": "A* over road_edges (cost-weighted) minimising travel cost; alternative = best path avoiding one edge of the primary route."}
