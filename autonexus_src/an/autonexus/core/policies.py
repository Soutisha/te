"""Compliance engine. Evaluates rows of the policies table against proposed purchases; unknown rules are reported, not ignored."""
from sqlalchemy import select
from . import models as m

def check_purchase(s, supplier, amount):
    results, needs_high = [], False
    for p in s.scalars(select(m.Policy).order_by(m.Policy.id)):
        rule = (p.rule or "").lower()
        if rule == "manager approval above":
            hi = amount > p.limit; needs_high |= hi
            results.append({"policy": p.id, "rule": p.rule, "limit": p.limit, "passed": True, "requires_high_approval": hi})
        elif rule == "restricted supplier prohibited":
            results.append({"policy": p.id, "rule": p.rule, "passed": not supplier.restricted,
                            "detail": f"supplier {supplier.id} is restricted" if supplier.restricted else "supplier not restricted"})
        elif rule == "single po max":
            results.append({"policy": p.id, "rule": p.rule, "limit": p.limit, "passed": amount <= p.limit,
                            "detail": f"amount {amount:.2f} vs limit {p.limit:.0f}"})
        else:
            results.append({"policy": p.id, "rule": p.rule, "passed": None, "detail": "rule not understood by engine; not evaluated"})
    return {"compliant": all(r["passed"] is not False for r in results), "requires_high_approval": needs_high, "checks": results}
