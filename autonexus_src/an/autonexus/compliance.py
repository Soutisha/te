def check_vendor(vendors,vid,amount):
    v=vendors[vid]; why=[]
    if v["restricted"]: why.append("restricted supplier")
    if amount>v["limit"]: why.append("exceeds purchase limit")
    return {"approved":not why,"reasons":why}
def invoice_vs_po(inv,po):
    issues=[]
    for part,q in inv["lines"].items():
        a=po["lines"].get(part,0)
        if q>a: issues.append(f"{part}: invoiced {q} > PO {a}")
    return {"approved":not issues,"issues":issues}
ROLE_PERMS={"admin":{"*"},"inventory_manager":{"inventory:update","transfer:approve"},"auditor":{"audit:read"},"supplier":set()}
def allowed(role,perm): p=ROLE_PERMS.get(role,set()); return "*" in p or perm in p
