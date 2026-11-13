# AUTONEXUS AI 2.0 — Kolkata AutoNexus Motors build

## Changes in this package
- Seed data rebranded to **AutoNexus Motors** with branches:
  - Kolkata Central, Salt Lake, Howrah (+ New Town & Rajarhat satellites)
  - Regional hubs: Dum Dum, Howrah Yard
- **Brake-pad stockout demo** hard-coded into inventory:
  - Kolkata Central: 0 × P000
  - Salt Lake: 18
  - Howrah: 4
  - Dum Dum hub: 40
- 8 suppliers with reliability + defect rates
- 30 vehicle records with days-in-inventory and list price
- Workshop reschedule suggestions + apply API retained
- Business-friendlier labels in platform status
- `gen_csv` no longer requires scikit-learn at import time

## Honest scope
This remains a **FastAPI + HTML/Three.js** core. There is no React/shadcn 18-page shell in the repository. External systems (ERPNext, Flower, live SIEM, live OSRM) are reported as not connected.

## Run
```bash
cd an
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Configure JWT_SECRET (≥32 chars) and OWNER_PASSWORD_HASH
./start.sh
```

## Key demo path
1. Login as owner
2. Start shortage workflow for DealerA / P000 (qty 2+)
3. System should prefer internal transfer from Salt Lake or hub
4. Approve → transfer → receive → repair order can proceed
