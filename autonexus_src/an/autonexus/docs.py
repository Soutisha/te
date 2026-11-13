import re
def classify(text):
    t=text.lower()
    if re.search(r"stock\s+transfer\s+note|transfer\s+note",t): return "stock_transfer_note"
    if re.search(r"insurance\s+(?:policy|certificate)|motor\s+insurance",t): return "insurance_policy"
    if re.search(r"registration\s+certificate|certificate\s+of\s+registration|\bR\.?C\.?\s*(?:book|certificate)?\b",t): return "registration_certificate"
    if re.search(r"vehicle\s+title|title\s+certificate",t): return "ownership_title"
    for k,w in [("invoice","invoice"),("purchase_order","purchase order"),("contract","agreement"),("registration","registration")]:
        if w in t: return k
    return "unknown"
def _norm(text):
    """Fix common OCR confusions inside part IDs (O->0)."""
    return re.sub(r"\bP([0O]{3})\b",lambda m:"P"+m.group(1).replace("O","0"),text)
def extract(text):
    text=_norm(text)
    """Text-layer extraction (deterministic fallback). Image OCR needs pytesseract: not bundled."""
    f={"type":classify(text)}
    m=re.search(r"transfer\s+(?:reference|ref)\s*[:\-]?\s*([A-Z0-9-]+)",text,re.I)
    if not m: m=re.search(r"(?:invoice|po)\s*(?:no\.?|#)?\s*[:\-]?\s*([A-Z]*-?\d+)",text,re.I)
    f["number"]=m and m.group(1)
    f["lines"]={p:int(q) for p,q in re.findall(r"(P\d{3})\s*[x:]\s*(\d+)",text)}
    m=re.search(r"vendor\s*[:\-]\s*(\w+)",text,re.I); f["vendor"]=m and m.group(1)
    f["evidence"]=[l.strip() for l in text.splitlines() if re.search(r"P\d{3}",l)]
    if f["type"] in ("registration_certificate","ownership_title","insurance_policy"):
        def field(pattern):
            match=re.search(pattern+r"\s*:?\s*([^\n]+)",text,re.I)
            return match.group(1).strip() if match else None
        f["registration_number"]=field(r"(?:vehicle\s+)?registration\s+(?:mark|number|no\.?)")
        f["owner_name"]=field(r"(?:registered\s+owner|owner\s+name|name\s+of\s+registered\s+owner)")
        f["chassis_number"]=field(r"(?:chassis\s+(?:number|no\.?)|VIN)")
        f["engine_number"]=field(r"engine\s+(?:number|no\.?)")
        f["make_model"]=field(r"(?:maker'?s?\s+name|make\s*(?:\/|and)\s*model|vehicle\s+model)")
        f["policy_number"]=field(r"policy\s+(?:number|no\.?)")
        f["insurer"]=field(r"(?:insurer|insurance\s+company)")
        f["valid_from"]=field(r"(?:policy\s+)?valid\s+from")
        f["valid_until"]=field(r"(?:policy\s+)?(?:valid\s+until|expiry\s+date|expires\s+on)")
        reg=f["registration_number"] or ""
        state_match=re.search(r"\b([A-Z]{2})[\s-]?\d{1,2}[\s-]?[A-Z]{1,3}[\s-]?\d{1,4}\b",reg,re.I)
        f["registration_state_code"]=state_match.group(1).upper() if state_match else None
        if not f["number"]:
            m=re.search(r"(?:policy|registration|certificate)\s+(?:number|no\.?|#)\s*[:\-]?\s*([A-Z0-9/-]+)",text,re.I)
            if m: f["number"]=m.group(1)
    if f["type"]=="stock_transfer_note":
        def field(pattern):
            match=re.search(pattern+r"\s*:?\s*([^\n]+)",text,re.I)
            return match.group(1).strip() if match else None
        f["source_location"]=field(r"(?:from location|dispatching site)")
        f["destination_location"]=field(r"(?:to location|receiving site)")
        f["source_site_id"]=(re.search(r"\((Dealer[A-Z0-9]+|WH\d+)\)",f["source_location"] or "",re.I) or [None,None])[1]
        f["destination_site_id"]=(re.search(r"\((Dealer[A-Z0-9]+|WH\d+)\)",f["destination_location"] or "",re.I) or [None,None])[1]
        f["part_code"]=(re.search(r"\b(P\d{3})\b",text,re.I) or [None,None])[1]
        qty=re.search(r"total\s+quantity\s*:?\s*(\d+)\s*([A-Z]+)?",text,re.I)
        if qty:
            f["quantity"]=int(qty.group(1)); f["unit"]=qty.group(2)
            if f["part_code"] and not f["lines"]: f["lines"][f["part_code"]]=f["quantity"]
        for key,pattern in (("unit_value",r"unit\s+value\s*:?\s*(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d{1,2})?)"),
                            ("total_value",r"declared\s+transfer\s+value\s*:?\s*(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d{1,2})?)")):
            match=re.search(pattern,text,re.I)
            f[key]=float(match.group(1).replace(",","")) if match else None
        money=re.findall(r"(?:INR|Rs\.?|₹)\s*([\d,]+(?:\.\d{1,2})?)",text,re.I)
        if money and f["unit_value"] is None: f["unit_value"]=float(money[0].replace(",",""))
        if money and f["total_value"] is None: f["total_value"]=float(money[-1].replace(",",""))
        if f["unit_value"] is None and f["total_value"] is not None and f.get("quantity"):
            f["unit_value"]=round(f["total_value"]/f["quantity"],2)
        f["status"]=field(r"status")
        f["expected_arrival"]=field(r"expected arrival")
        f["requested_by"]=field(r"requested by")
    return f
