# AUTONEXUS AI 2.0 — App Shell Release

## New: multi-page operations shell
Open **http://127.0.0.1:8000/app/** (or **/ops**)

| Page | Purpose | API used |
|------|---------|----------|
| Situation board | What / Why / What to do + one-click transfer request | `/workflows/shortage`, `/twin/state`, `/overview` |
| Waiting for your OK | Approve / reject transfers | `/approvals`, decision |
| Stock management | On hand / reserved / need by branch | `/inventory/{part}`, `/twin/state` |
| Buying parts | Supplier ranking | `/suppliers/rank` |
| Predict demand | SES/Croston + XGBoost MAE/RMSE | `/forecast`, `/forecast/xgboost` |
| Workshop schedule | Staffing + reschedule suggestions | `/workshop/evaluate` |
| Cars waiting | Vehicle aging guidance | dataset note |
| Live map | Existing Three.js world | `/world` |

Design: midnight base, lime accents, business language, shared auth bar.

## Still proven
- Kolkata Central P000 stockout → approval → dispatch
- XGBoost eval endpoint
- Twin bridge in Living World

## Run
```bash
cd an
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
./start.sh
```
Then open http://127.0.0.1:8000/app/
