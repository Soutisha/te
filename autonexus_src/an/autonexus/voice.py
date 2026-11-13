import re
W={"twenty five":25,"ten":10,"five":5,"fifty":50}
def parse(text):
    t=text.lower()
    m=re.search(r"dealer ([a-e]) has received (\d+|[a-z ]+?) (brake pads?|filters?|rotors?)",t)
    if not m: return {"valid":False,"error":"unrecognised command"}
    q=m.group(2); q=int(q) if q.isdigit() else W.get(q.strip())
    if not q or q<=0: return {"valid":False,"error":"bad quantity"}
    part={"b":"P000"}.get(m.group(3)[0],None)
    if not part: return {"valid":False,"error":"unsupported part"}
    return {"valid":True,"dealer":"Dealer"+m.group(1).upper(),"part":part,"qty":q,"needs_confirmation":True}

def parse_lot_walk(text, vehicle_rows):
    """Deterministic local extraction for a spoken/typed vehicle walk observation."""
    raw=(text or "").strip()
    normalized=raw.upper()
    ids={r.get("vehicle_id","").upper():r for r in vehicle_rows}
    vins={re.sub(r"[^A-Z0-9]","",r.get("vin","").upper()):r for r in vehicle_rows if r.get("vin")}
    token=re.search(r"\b(VH\d{3,}|INANX[A-Z0-9]{6,})\b",normalized)
    vehicle=(ids.get(token.group(1)) if token and token.group(1) in ids else None)
    if not vehicle and token:
        vehicle=vins.get(re.sub(r"[^A-Z0-9]","",token.group(1)))
    issues=[]
    if not raw: issues.append("Record a note or type one before previewing.")
    if not token: issues.append("Include the vehicle ID (for example VH001) or VIN.")
    elif not vehicle: issues.append(f"Vehicle {token.group(1)} was not found in the local vehicle inventory.")

    location_match=re.search(r"\b(?:row|space|stall|spot|bay|parking\s+spot|पंक्ति|लाइन|स्थान|अवस्थिति|সারি|রো|অবস্থান)\s*(?:number|no\.?|#|नंबर|নম্বর)?\s*([A-Z0-9]+(?:[- ][A-Z0-9]+)?)",normalized,re.I)
    location=(f"{location_match.group(0).strip()}" if location_match else None)
    if not location:
        site_match=re.search(r"\b(?:at|location(?:\s+is)?)\s+(Dealer[A-E]|WH[12])\b",normalized,re.I)
        location=site_match.group(1) if site_match else None
    if not location: issues.append("Add a lot location, such as row B-12.")

    low=raw.lower()
    damage_words=("scratch","dent","crack","damage","broken","chip","paint","windshield","missing","flat tire","खरोंच","डेंट","नुकसान","टूटा","क्षति","স্ক্র্যাচ","ডেন্ট","ভাঙা")
    clean_words=("clean","no damage","good condition","excellent condition","अच्छी हालत","साफ","कोई नुकसान नहीं","क्षति नहीं","ভালো","পরিষ্কার","কোনো ক্ষতি নেই","ক্ষতি নেই")
    no_damage=any(phrase in low for phrase in ("no damage","कोई नुकसान नहीं","क्षति नहीं","কোনো ক্ষতি নেই","ক্ষতি নেই"))
    if any(w in low for w in damage_words) and not (no_damage and all(w not in low for w in damage_words if w not in ("damage","नुकसान","ক্ষতি"))):
        condition="needs_inspection"
    elif any(w in low for w in clean_words):
        condition="good"
    else:
        condition="not_assessed"

    status_map=(("reserved","reserved"),("आरक्षित","reserved"),("সংরক্ষিত","reserved"),("sold","sold"),("बिक गया","sold"),("বিক্রি","sold"),("hold","hold"),("হোল্ড","hold"),("service","service"),("repair","service"),("मरम्मत","service"),("মেরামত","service"),("ready","in_stock"),("तैयार","in_stock"),("প্রস্তুত","in_stock"),("available","in_stock"),("उपलब्ध","in_stock"),("উপলব্ধ","in_stock"),("in stock","in_stock"),("স্টকে","in_stock"))
    status=next((mapped for phrase,mapped in status_map if phrase in low),"needs_review")
    return {"valid":bool(vehicle and location),"vehicle_id":vehicle.get("vehicle_id") if vehicle else None,
            "vin":vehicle.get("vin") if vehicle else None,"model":vehicle.get("model") if vehicle else None,
            "dealer_id":vehicle.get("dealership_id") if vehicle else None,"location":location,
            "condition":condition,"status":status,"notes":raw,"transcript":raw,
            "issues":issues,"needs_confirmation":True,
            "message":"Review the extracted vehicle, location, condition and status before saving."}

def apply(db,cmd,confirmed,audit,role="inventory_manager"):
    from .compliance import allowed
    if not confirmed: return {"ok":False,"error":"confirmation required"}
    if not allowed(role,"inventory:update"): return {"ok":False,"error":"forbidden"}
    db["stock"][cmd["dealer"]][cmd["part"]]+=cmd["qty"]; audit.add("voice","stock_in",cmd,"confirmed"); return {"ok":True}
