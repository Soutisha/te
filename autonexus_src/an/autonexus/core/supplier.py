"""Supplier Intelligence: explainable multi-criteria ranking. Lowest price alone never wins."""
from sqlalchemy import select
from . import models as m, policies

WEIGHTS = {"total_cost": 0.35, "lead_time": 0.25, "reliability": 0.40}

def _norm(v, lo, hi): return 0.0 if hi == lo else (v - lo) / (hi - lo)

def rank(s, part, qty):
    opts = []
    for q in s.scalars(select(m.Quotation).where(m.Quotation.part_id == part)):
        sup = s.get(m.Supplier, q.supplier_id); amount = round(q.unit_price * qty, 2)
        comp = policies.check_purchase(s, sup, amount)
        opts.append({"quotation": q.id, "supplier": sup.id, "supplier_name": sup.name, "unit_price": q.unit_price, "qty": qty,
                     "total_cost": amount, "delivery_days": q.delivery_days, "reliability": sup.reliability,
                     "eligible": comp["compliant"], "compliance": comp, "availability": "not provided by quotation data",
                     "ineligible_reasons": [c["detail"] for c in comp["checks"] if c["passed"] is False]})
    elig = [o for o in opts if o["eligible"]]
    if elig:
        c = [o["total_cost"] for o in elig]; d = [o["delivery_days"] for o in elig]
        for o in elig:
            parts = {"total_cost": WEIGHTS["total_cost"] * (1 - _norm(o["total_cost"], min(c), max(c))),
                     "lead_time": WEIGHTS["lead_time"] * (1 - _norm(o["delivery_days"], min(d), max(d))),
                     "reliability": WEIGHTS["reliability"] * o["reliability"]}
            o["score"] = round(sum(parts.values()), 4); o["score_breakdown"] = {k: round(v, 4) for k, v in parts.items()}
        elig.sort(key=lambda o: -o["score"])
    return {"part": part, "qty": qty, "weights": WEIGHTS, "ranked": elig, "excluded": [o for o in opts if not o["eligible"]],
            "best": elig[0] if elig else None,
            "explanation": ("Eligible quotations ranked by weighted score (cost, lead time, supplier reliability); "
                            "policy-violating suppliers are excluded before scoring." if elig else "No eligible supplier: every quotation violates procurement policy or none exists.")}
