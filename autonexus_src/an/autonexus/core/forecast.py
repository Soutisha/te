"""Predictive Intelligence on stored demand history. Never fabricates: too little data -> insufficient_data."""
import json, math
from statistics import NormalDist, pstdev, mean
from sqlalchemy import select
from . import models as m

MODEL_VERSION = "1.0"
MIN_HISTORY_DAYS = 28
SERVICE_LEVEL = 0.95

def _series(s, dealer, part):
    return [(r.day, r.demand, r.lead_time) for r in s.execute(select(m.DemandHistory.day, m.DemandHistory.demand, m.DemandHistory.lead_time).where(
        m.DemandHistory.dealer_id == dealer, m.DemandHistory.part_id == part).order_by(m.DemandHistory.day))]

def _ses(y, alpha):
    l = y[0]; errs = []
    for v in y[1:]: errs.append(v - l); l = alpha * v + (1 - alpha) * l
    return l, errs

def _croston_sba(y, alpha=0.1):
    nz = [i for i, v in enumerate(y) if v > 0]
    z, p, last = y[nz[0]], (nz[0] + 1), nz[0]; errs = []
    for i in nz[1:]:
        interval = i - last; errs.append(y[i] - z / p * (1 - alpha / 2))
        z = alpha * y[i] + (1 - alpha) * z; p = alpha * interval + (1 - alpha) * p; last = i
    return (z / p) * (1 - alpha / 2), errs

def _fit(y):
    nz = [v for v in y if v > 0]
    if not nz: return None
    adi = len(y) / len(nz); cv2 = (pstdev(nz) / mean(nz)) ** 2 if len(nz) > 1 else 0.0
    if adi > 1.32:
        rate, errs = _croston_sba(y); return {"model_id": "croston_sba", "rate": rate, "errs": errs, "adi": adi, "cv2": cv2}
    best = min(((a, *_ses(y, a)) for a in (0.1, 0.2, 0.3, 0.5)), key=lambda t: sum(abs(e) for e in t[2]) / max(1, len(t[2])))
    return {"model_id": f"ses_alpha_{best[0]}", "rate": best[1], "errs": best[2], "adi": adi, "cv2": cv2}

def forecast(s, dealer, part, horizon_days=14, on_hand=None, persist=True):
    ser = _series(s, dealer, part)
    base = {"dealer": dealer, "part": part, "horizon_days": horizon_days, "provenance_tables": ["demand_history"]}
    if len(ser) < MIN_HISTORY_DAYS:
        out = {**base, "status": "insufficient_data", "history_days": len(ser), "required_days": MIN_HISTORY_DAYS,
               "message": f"{len(ser)} days of history; at least {MIN_HISTORY_DAYS} required. No forecast produced."}
    else:
        y = [v for _, v, _ in ser]; hold = max(7, min(14, len(y) // 4))
        fit_tr = _fit(y[:-hold]); fit = _fit(y)
        if not fit or not fit_tr:
            out = {**base, "status": "insufficient_data", "history_days": len(ser), "message": "no non-zero demand observed"}
        else:
            actual = y[-hold:]; mae = mean(abs(a - fit_tr["rate"]) for a in actual)
            naive = mean(abs(a - mean(y[:-hold])) for a in actual)
            sigma = pstdev(fit["errs"]) if len(fit["errs"]) > 1 else 0.0
            z90 = NormalDist().inv_cdf(0.95); H = horizon_days; total = fit["rate"] * H; sH = sigma * math.sqrt(H)
            lts = [lt for _, _, lt in ser if lt is not None]; L = mean(lts) if lts else 0; sL = pstdev(lts) if len(lts) > 1 else 0.0
            zs = NormalDist().inv_cdf(SERVICE_LEVEL)
            ss = zs * math.sqrt(L * sigma ** 2 + (fit["rate"] ** 2) * sL ** 2); rop = fit["rate"] * L + ss
            p_out = None
            if on_hand is not None:
                sd = sigma * math.sqrt(L) if L else 0
                p_out = (1.0 if on_hand < fit["rate"] * L else 0.0) if sd == 0 else 1 - NormalDist(fit["rate"] * L, sd).cdf(on_hand)
            out = {**base, "status": "ok", "model_id": fit["model_id"], "model_version": MODEL_VERSION,
                   "forecast_total": round(total, 2), "daily_rate": round(fit["rate"], 3),
                   "interval_90": [round(max(0, total - z90 * sH), 2), round(total + z90 * sH, 2)],
                   "lead_time_days": round(L, 2), "lead_time_std": round(sL, 2),
                   "safety_stock": round(ss, 2), "reorder_point": round(rop, 2),
                   "stockout_probability_over_lead_time": None if p_out is None else round(p_out, 4),
                   "training_range_days": [ser[0][0], ser[-1][0]], "history_days": len(ser),
                   "metrics": {"holdout_days": hold, "holdout_mae": round(mae, 3), "naive_mean_mae": round(naive, 3),
                               "beats_naive": mae < naive, "adi": round(fit["adi"], 3), "cv2": round(fit["cv2"], 3)},
                   "explanation": f"{fit['model_id']} fitted on {len(ser)} days (ADI {fit['adi']:.2f}); interval from in-sample residuals; "
                                  f"safety stock at {SERVICE_LEVEL:.0%} service level incl. lead-time variability."}
    if persist:
        ok = out["status"] == "ok"
        s.add(m.Forecast(dealer_id=dealer, part_id=part, horizon_days=horizon_days, status=out["status"],
                         value=out.get("forecast_total"), lower=out["interval_90"][0] if ok else None, upper=out["interval_90"][1] if ok else None,
                         model_id=out.get("model_id"), model_version=out.get("model_version"),
                         train_start=out["training_range_days"][0] if ok else None, train_end=out["training_range_days"][1] if ok else None,
                         metrics=json.dumps(out.get("metrics", {})))); s.flush()
    return out


# ---------------------------------------------------------------------------
# XGBoost demand forecasting (optional — used when xgboost + sklearn installed)
# Trains on demand_history rows; reports MAE / RMSE on a holdout window.
# ---------------------------------------------------------------------------

def train_xgboost_demand(s, dealer=None, part=None, horizon_days=14, min_rows=80):
    """Train an XGBoost regressor on demand history and evaluate on holdout.

    Returns honest metrics. If xgboost/sklearn are missing, returns status=unavailable.
    Does not claim production readiness; labels data provenance.
    """
    try:
        import numpy as np
        from sklearn.metrics import mean_absolute_error, mean_squared_error
    except ImportError:
        return {
            "status": "unavailable",
            "message": "scikit-learn is not installed in this environment",
            "provenance": "SYNTHETIC sample demand_history",
        }
    try:
        import xgboost as xgb
    except ImportError:
        return {
            "status": "unavailable",
            "message": "xgboost is not installed in this environment",
            "provenance": "SYNTHETIC sample demand_history",
        }

    q = select(m.DemandHistory)
    if dealer:
        q = q.where(m.DemandHistory.dealer_id == dealer)
    if part:
        q = q.where(m.DemandHistory.part_id == part)
    rows = list(s.scalars(q.order_by(m.DemandHistory.dealer_id, m.DemandHistory.part_id, m.DemandHistory.day)))
    if len(rows) < min_rows:
        return {
            "status": "insufficient_data",
            "rows": len(rows),
            "required_rows": min_rows,
            "message": f"Need at least {min_rows} demand_history rows; found {len(rows)}",
            "provenance": "SYNTHETIC sample demand_history",
        }

    # Feature matrix: lag structure per (dealer, part) series
    by_key = {}
    for r in rows:
        by_key.setdefault((r.dealer_id, r.part_id), []).append(r)

    X_list, y_list, meta = [], [], []
    for (d, p), series in by_key.items():
        series = sorted(series, key=lambda r: r.day)
        demands = [float(r.demand) for r in series]
        for i in range(7, len(demands)):
            # features: last 7 days, rolling mean/std, day index, lead_time
            window = demands[i - 7 : i]
            feat = window + [
                float(np.mean(window)),
                float(np.std(window) if len(window) > 1 else 0.0),
                float(series[i].day),
                float(series[i].lead_time or 3),
            ]
            X_list.append(feat)
            y_list.append(demands[i])
            meta.append((d, p, series[i].day))

    if len(X_list) < min_rows:
        return {
            "status": "insufficient_data",
            "feature_rows": len(X_list),
            "required_rows": min_rows,
            "message": "Not enough lag windows after feature engineering",
            "provenance": "SYNTHETIC sample demand_history",
        }

    X = np.array(X_list, dtype=float)
    y = np.array(y_list, dtype=float)

    # Time-based split: last 20% holdout
    split = int(len(X) * 0.8)
    X_tr, X_te = X[:split], X[split:]
    y_tr, y_te = y[:split], y[split:]

    model = xgb.XGBRegressor(
        n_estimators=120,
        max_depth=4,
        learning_rate=0.08,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=42,
        n_jobs=1,
        verbosity=0,
    )
    model.fit(X_tr, y_tr)
    pred = model.predict(X_te)
    mae = float(mean_absolute_error(y_te, pred))
    rmse = float(mean_squared_error(y_te, pred) ** 0.5)
    naive = float(mean_absolute_error(y_te, np.full_like(y_te, y_tr.mean())))

    # Next-horizon point forecast for the requested series (or first available)
    target_key = (dealer, part) if dealer and part else next(iter(by_key.keys()))
    series = sorted(by_key.get(target_key, []), key=lambda r: r.day)
    if len(series) >= 7:
        demands = [float(r.demand) for r in series]
        window = demands[-7:]
        feat = window + [
            float(np.mean(window)),
            float(np.std(window) if len(window) > 1 else 0.0),
            float(series[-1].day + 1),
            float(series[-1].lead_time or 3),
        ]
        daily = float(max(0.0, model.predict(np.array([feat]))[0]))
        total = round(daily * horizon_days, 2)
    else:
        daily, total = None, None

    return {
        "status": "ok",
        "model_id": "xgboost_regressor",
        "model_version": "xgb-1.0",
        "dealer": target_key[0],
        "part": target_key[1],
        "horizon_days": horizon_days,
        "daily_rate": round(daily, 3) if daily is not None else None,
        "forecast_total": total,
        "metrics": {
            "holdout_rows": int(len(y_te)),
            "holdout_mae": round(mae, 4),
            "holdout_rmse": round(rmse, 4),
            "naive_mean_mae": round(naive, 4),
            "beats_naive": mae < naive,
            "train_rows": int(len(y_tr)),
            "feature_rows_total": int(len(X)),
        },
        "feature_names": [
            "lag_1", "lag_2", "lag_3", "lag_4", "lag_5", "lag_6", "lag_7",
            "roll_mean_7", "roll_std_7", "day", "lead_time",
        ],
        "provenance": "SYNTHETIC sample demand_history",
        "explanation": (
            f"XGBoost regressor trained on {len(X_tr)} lag windows from demand_history; "
            f"holdout MAE={mae:.3f}, RMSE={rmse:.3f} "
            f"({'beats' if mae < naive else 'does not beat'} naive mean baseline MAE={naive:.3f}). "
            "Data is synthetic demonstration history, not live dealership telemetry."
        ),
    }
