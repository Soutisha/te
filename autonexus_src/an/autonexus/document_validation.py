"""Local West Bengal vehicle document consistency checks (not legal clearance)."""
from datetime import date, datetime
import re

PROFILE = {
    "id": "IN-WB-local-v1",
    "sources": [
        "https://transport.wb.gov.in/governance-services/vehicle-registration/",
        "https://parivahan.gov.in/parivahan/sites/default/files/DownloadForm/form23.pdf",
    ],
    "scope": "Field presence, WB registration-mark format, expiry, and cross-document/local-record consistency only.",
}

def extract_file(data, file_name, content_type=""):
    """Extract local text from a PDF/image and run the deterministic field parser."""
    from . import docs, ocr
    name = (file_name or "").lower()
    content_type = (content_type or "").lower()
    if content_type == "application/pdf" or name.endswith(".pdf"):
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("Local PDF extraction needs PyMuPDF installed.") from exc
        try:
            pdf = fitz.open(stream=data, filetype="pdf")
        except Exception as exc:
            raise ValueError("The uploaded PDF could not be opened.") from exc
        if pdf.page_count > 100:
            raise OverflowError("PDF is over the 100-page local extraction limit.")
        text = "\n".join(page.get_text("text") for page in pdf)
        if not text.strip():
            page_text = []
            for page in pdf:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                page_text.append(ocr.extract_image(pix.tobytes("png"))["ocr_text"])
            text = "\n".join(page_text)
        fields = docs.extract(text)
        return {"file_name": file_name, "pages": pdf.page_count, "extracted_text": text, "fields": fields, **fields}
    if content_type.startswith("image/") or name.endswith((".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp")):
        extracted = ocr.extract_image(data)
        text = extracted.get("ocr_text", "")
        fields = docs.extract(text)
        return {"file_name": file_name, "extracted_text": text, "fields": fields, **extracted, **fields}
    raise ValueError("Choose a PDF or image file.")

REQUIRED = {
    "registration_certificate": ("registration_number", "owner_name", "chassis_number"),
    "insurance_policy": ("registration_number", "policy_number", "insurer", "valid_from", "valid_until"),
    "ownership_title": ("registration_number", "owner_name", "chassis_number"),
}

def _date(value):
    if not value:
        return None
    value = value.strip().split(" to ")[0]
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %b %Y", "%d %B %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    match = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", value)
    if match:
        try:
            return date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
        except ValueError:
            return None
    return None

def _normal(value):
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())

def validate_package(vehicle_id, documents, vehicle_rows, as_of=None):
    """Check a local document package against the selected CSV vehicle record."""
    as_of = as_of or date.today()
    vehicle = next((r for r in vehicle_rows if r.get("vehicle_id", "").upper() == vehicle_id.upper()), None)
    if not vehicle:
        raise ValueError(f"Unknown local vehicle ID: {vehicle_id}")

    checks = []
    add = lambda name, passed, detail, severity="error": checks.append({"check": name, "passed": bool(passed), "severity": severity, "detail": detail})
    kinds = {d.get("fields", {}).get("type") for d in documents}
    for kind, label in (("registration_certificate", "registration certificate"), ("insurance_policy", "insurance policy")):
        add(f"{label} provided", kind in kinds, f"{'Found' if kind in kinds else 'Missing'} a readable {label}.")

    registrations, chassis_values, owners = [], [], []
    for doc in documents:
        fields = doc.get("fields", {})
        kind = fields.get("type", "unknown")
        add(f"{doc.get('file_name', 'Document')} recognized", kind in REQUIRED,
            f"Detected {kind.replace('_', ' ')}." if kind in REQUIRED else "Document type was not recognized by the local rule profile.",
            "warning" if kind not in REQUIRED else "error")
        for field in REQUIRED.get(kind, ()):
            add(f"{doc.get('file_name', kind)}: {field.replace('_', ' ')} present", bool(fields.get(field)),
                f"{field.replace('_', ' ')} {'extracted' if fields.get(field) else 'not found'}.", "warning")
        reg = fields.get("registration_number")
        if reg:
            registrations.append((doc.get("file_name", kind), _normal(reg)))
            pattern_ok = bool(re.fullmatch(r"WB\d{1,2}[A-Z]{1,3}\d{1,4}", _normal(reg)))
            add(f"{doc.get('file_name', kind)}: West Bengal registration format", pattern_ok,
                "Registration mark matches the local WB format check." if pattern_ok else "Registration mark does not match the local WB format check; verify manually.")
        chassis = fields.get("chassis_number")
        if chassis:
            chassis_values.append((doc.get("file_name", kind), _normal(chassis)))
        owner = fields.get("owner_name")
        if owner:
            owners.append((doc.get("file_name", kind), _normal(owner)))
        expiry = _date(fields.get("valid_until"))
        if kind == "insurance_policy":
            add("Insurance expiry readable", expiry is not None,
                "Could not parse the policy expiry date; verify the original document." if expiry is None else f"Policy expiry parsed as {expiry.isoformat()}.", "warning" if expiry is None else "error")
            if expiry:
                add("Insurance not expired", expiry >= as_of,
                    f"Policy expires {expiry.isoformat()}." if expiry >= as_of else f"Policy expired on {expiry.isoformat()}.")
            starts = _date(fields.get("valid_from"))
            if starts:
                add("Insurance effective today", starts <= as_of,
                    f"Policy starts {starts.isoformat()}." if starts <= as_of else f"Policy does not start until {starts.isoformat()}.")

    if len({v for _, v in registrations}) > 1:
        add("Registration numbers agree", False, "Registration marks differ across uploaded documents.")
    elif registrations:
        add("Registration numbers agree", True, "All extracted registration marks match.")
    if len({v for _, v in chassis_values}) > 1:
        add("Chassis numbers agree", False, "Chassis/VIN values differ across uploaded documents.")
    elif chassis_values:
        add("Chassis numbers agree", True, "All extracted chassis/VIN values match.")
    if len({v for _, v in owners}) > 1:
        add("Registered owners agree", False, "Owner names differ across uploaded documents; verify identity and spelling.")
    elif owners:
        add("Registered owners agree", True, "All extracted owner names match.")
    expected_vin = _normal(vehicle.get("vin"))
    for filename, chassis in chassis_values:
        add(f"{filename}: local vehicle VIN match", chassis == expected_vin,
            "Chassis/VIN matches the selected local vehicle record." if chassis == expected_vin else "Chassis/VIN does not match the selected local vehicle record.")

    failed = [c for c in checks if not c["passed"] and c["severity"] == "error"]
    warnings = [c for c in checks if not c["passed"] and c["severity"] == "warning"]
    return {
        "profile": PROFILE["id"],
        "vehicle": {"vehicle_id": vehicle["vehicle_id"], "vin": vehicle.get("vin"), "model": vehicle.get("model"), "year": vehicle.get("year")},
        "documents": documents,
        "status": "hold_for_review" if failed or warnings else "ready_for_human_review",
        "checks": checks,
        "issues": [c for c in checks if not c["passed"]],
        "note": "Local extraction and format/consistency checks only. This is not an official state validation or approval to finalize a deal.",
        "rule_scope": PROFILE["scope"],
        "rule_sources": PROFILE["sources"],
    }
