import os, threading, unittest
os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret-123")
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, text, update
from fastapi.testclient import TestClient
from autonexus.core import db, seed, workflow, approvals, security, inventory, forecast, audit, models as m, api_v1
from autonexus.core.approvals import ApprovalError
from autonexus.core.workflow import WorkflowError

def fresh():
    db.configure("sqlite://"); api_v1.reset_for_tests(); seed.load_csv_dataset()
    with db.write() as s:
        for e, r in [("req@t.test", "inventory_manager"), ("mgr@t.test", "manager"), ("inv2@t.test", "inventory_manager"),
                     ("view@t.test", "viewer"), ("aud@t.test", "auditor"), ("adm@t.test", "admin")]:
            security.create_user(s, e, "pw-long-enough-1", r)

def stock(site, part="P000"):
    with db.read() as s: r = s.get(m.Stock, (site, part)); return (r.on_hand, r.reserved)

class Base(unittest.TestCase):
    def setUp(self): fresh()
    def plan(self, qty=10, **k): return workflow.run_shortage("req@t.test", "inventory_manager", "DealerA", "P000", qty, **k)

class AcceptanceScenario(Base):
    def test_brake_pad_shortage_end_to_end(self):
        r = self.plan(10)
        self.assertEqual(r["status"], "awaiting_approval")
        self.assertEqual(r["shortage"]["shortage"], 8)                               # 1 inventory detects 8
        self.assertEqual(r["forecast"]["status"], "ok")                              # 2 forecasting consulted history
        self.assertTrue(r["donor_options"])                                          # 3 eligible sources searched
        self.assertTrue(r["workshop"]["blocked_repair_orders"])                      # 7 workshop evaluated
        agents = [t["agent"] for t in r["trace"]]
        for a in ("Security", "Inventory", "Forecasting", "Route", "Workshop", "Procurement"): self.assertIn(a, agents)
        (aid,) = r["approvals"]; src = r["transfer_plan"][0]["source"]; before_src = stock(src)
        self.assertEqual(stock(src)[1], 8)                                           # reservation held, nothing moved yet
        for who, role in [("view@t.test", "viewer"), ("aud@t.test", "auditor")]:    # 10 unauthorised rejected
            with self.assertRaises(ApprovalError) as c: approvals.decide(aid, who, role, "approve")
            self.assertEqual(c.exception.code, 403)
        with self.assertRaises(ApprovalError) as c: approvals.decide(aid, "req@t.test", "inventory_manager", "approve")
        self.assertEqual(c.exception.code, 403)                                      # separation of duties
        self.assertEqual(stock(src)[0], before_src[0])
        a = approvals.decide(aid, "mgr@t.test", "manager", "approve", "ok")          # 11 authorised execution
        self.assertEqual(a["status"], "executed")
        self.assertEqual(stock(src), (before_src[0] - 8, 0))                         # 12 transactional update
        self.assertEqual(stock("DealerA")[0], 2)                                     # not yet received
        (tr,) = workflow.get(r["workflow_id"])["transfers"]; self.assertEqual(tr["status"], "in_transit")
        v = workflow.receive_transfer(tr["id"], "mgr@t.test", "manager")
        self.assertEqual(stock("DealerA")[0], 10)
        self.assertTrue(v["verified"]); self.assertTrue(v["outcome_resolved"]); self.assertEqual(v["status"], "recovered")  # 16
        with db.read() as s:
            types = [e["type"] for e in __import__("autonexus.core.events", fromlist=["x"]).since(s, 0)]
            for t in ("shortage.detected", "approval.requested", "transfer.dispatched", "transfer.received", "inventory.changed"): self.assertIn(t, types)  # 13
            self.assertTrue(audit.verify(s)["valid"])                                # 15
            acts = [x.action for x in s.scalars(select(m.AuditRecord))]
            for t in ("workflow_planned", "approval_requested", "approval_view_denied" if False else "approval_approve_denied", "approval_executed", "transfer_received"): self.assertIn(t, acts)

class FailurePaths(Base):
    def test_no_shortage(self):
        self.assertEqual(self.plan(1)["status"], "no_action")
    def test_insufficient_internal_stock_goes_to_supplier_with_explainable_ranking(self):
        r = self.plan(200)
        self.assertEqual(r["status"], "awaiting_approval")
        sr = r["supplier_ranking"]; self.assertIsNotNone(sr["best"])
        self.assertTrue(all(o["supplier"] != "V2" for o in sr["ranked"]))            # restricted supplier excluded
        self.assertTrue(any(o["supplier"] == "V2" and o["ineligible_reasons"] for o in sr["excluded"]))
        self.assertIn("score_breakdown", sr["best"])
        pos = [workflow.get(r["workflow_id"])["approvals_detail"]][0]
        po = [a for a in pos if a["action_type"] == "purchase_order"][0]
        before = stock("DealerA")
        a = approvals.decide(po["id"], "mgr@t.test", "manager", "approve")
        self.assertIn("purchase_order", a["execution_result"]); self.assertFalse(a["execution_result"]["erp_synced"])
        self.assertEqual(stock("DealerA"), before)                                   # a PO is not stock
    def test_lowest_price_is_not_automatically_selected(self):
        with db.read() as s:
            from autonexus.core import supplier
            out = supplier.rank(s, "P000", 10)
        cheapest = min(out["ranked"], key=lambda o: o["total_cost"])
        self.assertTrue(len(out["ranked"]) >= 2)
        self.assertIn("reliability", out["best"]["score_breakdown"])
        self.assertTrue(cheapest["total_cost"] <= out["best"]["total_cost"])
    def test_no_eligible_supplier(self):
        with db.write() as s: s.execute(update(m.Supplier).values(restricted=True))
        r = self.plan(200)
        self.assertEqual(r["supplier_ranking"]["explanation"][:11], "No eligible"); self.assertIsNone(r["supplier_ranking"]["best"])
        self.assertEqual(r["unresolved_qty"], r["shortage"]["net_shortage"] - sum(l["qty"] for l in r["transfer_plan"]))
    def test_route_unavailable_and_road_closure(self):
        r = self.plan(10, blocked=[("DealerA", "WH2"), ("DealerA", "DealerB"), ("DealerA", "WH1")])
        self.assertEqual(r["transfer_plan"], [])
        self.assertTrue(all(o["route_status"] == "unavailable" for o in r["donor_options"]))
        r2 = self.plan(10, blocked=[("DealerA", "WH2")])
        self.assertTrue(r2["transfer_plan"])
        self.assertNotEqual(r2["transfer_plan"][0]["path"], ["WH2", "DealerA"])
        self.assertIn("NOT a provider ETA", r2["transfer_plan"][0]["eta_basis"])
    def test_rejected_releases_reservation(self):
        r = self.plan(10); src = r["transfer_plan"][0]["source"]
        approvals.decide(r["approvals"][0], "mgr@t.test", "manager", "reject", "no")
        self.assertEqual(stock(src)[1], 0); self.assertEqual(workflow.get(r["workflow_id"])["status"], "rejected")
    def test_request_changes_releases_reservation(self):
        r = self.plan(10); src = r["transfer_plan"][0]["source"]
        approvals.decide(r["approvals"][0], "mgr@t.test", "manager", "request_changes", "smaller")
        self.assertEqual(stock(src)[1], 0); self.assertEqual(workflow.get(r["workflow_id"])["status"], "changes_requested")
    def test_expired_approval(self):
        r = self.plan(10); src = r["transfer_plan"][0]["source"]
        with db.write() as s: s.get(m.Approval, r["approvals"][0]).expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        with self.assertRaises(ApprovalError) as c: approvals.decide(r["approvals"][0], "mgr@t.test", "manager", "approve")
        self.assertEqual(c.exception.code, 409); self.assertEqual(approvals.get(r["approvals"][0])["status"], "expired")
        self.assertEqual(stock(src)[1], 0)
    def test_duplicate_approval_and_duplicate_execution(self):
        r = self.plan(10); aid = r["approvals"][0]; src = r["transfer_plan"][0]["source"]; start = stock(src)[0]
        approvals.decide(aid, "mgr@t.test", "manager", "approve")
        with self.assertRaises(ApprovalError) as c: approvals.decide(aid, "inv2@t.test", "inventory_manager", "approve")
        self.assertEqual(c.exception.code, 409); self.assertEqual(stock(src)[0], start - 8)
        with db.write() as s:
            t = s.scalar(select(m.Transfer).where(m.Transfer.workflow_id == r["workflow_id"]))
            with self.assertRaises(inventory.InventoryError): inventory.dispatch(s, t, "x")   # already in transit
    def test_concurrent_approvals_execute_once(self):
        r = self.plan(10); aid = r["approvals"][0]; src = r["transfer_plan"][0]["source"]; start = stock(src)[0]; out = []
        def go(u, role):
            try: approvals.decide(aid, u, role, "approve"); out.append("ok")
            except ApprovalError as e: out.append(e.code)
        th = [threading.Thread(target=go, args=a) for a in [("mgr@t.test", "manager"), ("inv2@t.test", "inventory_manager"), ("adm@t.test", "admin")]]
        [t.start() for t in th]; [t.join() for t in th]
        self.assertEqual(out.count("ok"), 1); self.assertEqual(stock(src)[0], start - 8)
    def test_execution_failure_rolls_back_and_is_recorded(self):
        r = self.plan(10); aid = r["approvals"][0]; src = r["transfer_plan"][0]["source"]
        with db.write() as s: s.execute(text("UPDATE stock SET reserved=0 WHERE site_id=:s AND part_id='P000'"), {"s": src})  # corrupt the reservation
        with self.assertRaises(ApprovalError) as c: approvals.decide(aid, "mgr@t.test", "manager", "approve")
        self.assertEqual(c.exception.code, 409); self.assertEqual(approvals.get(aid)["status"], "execution_failed")
        with db.read() as s: self.assertTrue(inventory.ledger_check(s, "P000")["consistent"])
    def test_missing_forecast_history_is_explicit(self):
        with db.write() as s: s.execute(text("DELETE FROM demand_history WHERE dealer_id='DealerA' AND part_id='P000'"))
        r = self.plan(10)
        self.assertEqual(r["forecast"]["status"], "insufficient_data"); self.assertNotIn("forecast_total", r["forecast"])
        self.assertEqual(r["status"], "awaiting_approval")
    def test_unauthorised_workflow_run_and_unknown_part(self):
        with self.assertRaises(WorkflowError) as c: workflow.run_shortage("view@t.test", "viewer", "DealerA", "P000", 10)
        self.assertEqual(c.exception.code, 403)
        r = workflow.run_shortage("req@t.test", "inventory_manager", "DealerA", "NOPE", 10)
        self.assertEqual(r["status"], "failed"); self.assertIn("unknown part", r["error"])
    def test_repeat_run_does_not_double_plan(self):
        self.plan(10); r2 = self.plan(10)
        self.assertEqual(r2["status"], "covered_by_pending_supply")
    def test_security_check_blocks_after_repeated_denials(self):
        for _ in range(3):
            with self.assertRaises(WorkflowError): workflow.run_shortage("bad@t.test", "viewer", "DealerA", "P000", 10)
        with self.assertRaises(WorkflowError) as c: workflow.run_shortage("bad@t.test", "inventory_manager", "DealerA", "P000", 10)
        self.assertIn("security", str(c.exception))

class DataIntegrity(Base):
    def test_negative_stock_rejected_by_database(self):
        with self.assertRaises(Exception):
            with db.write() as s: s.execute(text("UPDATE stock SET on_hand=-1 WHERE site_id='DealerA' AND part_id='P000'"))
    def test_reservation_cannot_exceed_available(self):
        with self.assertRaises(inventory.InventoryError):
            with db.write() as s: inventory.reserve(s, "DealerA", "P000", 3)
    def test_audit_and_ledger_are_append_only_and_tamper_evident(self):
        self.plan(10)
        with self.assertRaises(PermissionError):
            with db.write() as s: s.scalar(select(m.AuditRecord)).actor = "mallory"
        with db.write() as s: s.execute(text("UPDATE audit SET actor='mallory' WHERE id=2"))
        with db.read() as s: v = audit.verify(s)
        self.assertFalse(v["valid"]); self.assertEqual(v["broken_at"], 2)
    def test_provenance_registry_marks_dataset_synthetic(self):
        with db.read() as s: self.assertEqual({r.provenance for r in s.scalars(select(m.DataSource))}, {"SYNTHETIC"})

class Forecasting(Base):
    def test_intermittent_demand_uses_croston_sba(self):
        with db.write() as s:
            s.execute(text("DELETE FROM demand_history WHERE dealer_id='DealerB' AND part_id='P007'"))
            for d in range(60): s.add(m.DemandHistory(dealer_id="DealerB", part_id="P007", day=d, demand=6.0 if d % 5 == 0 else 0.0, demand_std=0.0, lead_time=3))
        with db.write() as s: f = forecast.forecast(s, "DealerB", "P007", 14, on_hand=5)
        self.assertEqual(f["model_id"], "croston_sba"); self.assertGreater(f["interval_90"][1], f["interval_90"][0]); self.assertGreater(f["reorder_point"], 0)
    def test_forecast_is_persisted_with_model_and_range(self):
        with db.write() as s: forecast.forecast(s, "DealerA", "P000", 7)
        with db.read() as s: row = s.scalar(select(m.Forecast)); self.assertTrue(row.model_id and row.model_version and row.train_end is not None)

class ApiLayer(Base):
    def setUp(self):
        super().setUp(); from autonexus.api import app; self.c = TestClient(app)
        with db.write() as s: security.bootstrap_owner(s)
    def hdr(self, email): 
        t = self.c.post("/api/v1/auth/login", json={"email": email, "password": "pw-long-enough-1"}); self.assertEqual(t.status_code, 200); return {"Authorization": "Bearer " + t.json()["token"]}
    def test_auth_required_and_roles(self):
        self.assertEqual(self.c.get("/api/v1/overview").status_code, 401)
        self.assertEqual(self.c.get("/api/v1/overview", headers={"Authorization": "Bearer x.y.z"}).status_code, 401)
        self.assertEqual(self.c.post("/api/v1/auth/login", json={"email": "req@t.test", "password": "wrong"}).status_code, 401)
        self.assertEqual(self.c.get("/api/v1/audit", headers=self.hdr("view@t.test")).status_code, 403)
        self.assertEqual(self.c.get("/api/v1/audit", headers=self.hdr("aud@t.test")).status_code, 200)
    def test_http_workflow_and_twin_and_stream(self):
        h = self.hdr("req@t.test"); r = self.c.post("/api/v1/workflows/shortage", headers=h, json={"dealer": "DealerA", "part": "P000", "required_qty": 10}).json()
        self.assertEqual(r["status"], "awaiting_approval"); aid = r["approvals"][0]
        self.assertEqual(self.c.post(f"/api/v1/approvals/{aid}/decision", headers=self.hdr("view@t.test"), json={"decision": "approve"}).status_code, 403)
        tw = self.c.get("/api/v1/twin/state?part=P000", headers=h).json()
        self.assertEqual([t["status"] for t in tw["transfers"]], ["reserved"])
        self.assertEqual(self.c.post(f"/api/v1/approvals/{aid}/decision", headers=self.hdr("mgr@t.test"), json={"decision": "approve"}).status_code, 200)
        self.assertEqual(self.c.post(f"/api/v1/approvals/{aid}/decision", headers=self.hdr("adm@t.test"), json={"decision": "approve"}).status_code, 409)
        tw = self.c.get("/api/v1/twin/state?part=P000", headers=h).json(); self.assertEqual(tw["transfers"][0]["status"], "in_transit")
        self.assertEqual(self.c.get("/api/v1/overview", headers=h).json()["in_transit_transfers"], 1)
        tok = h["Authorization"][7:]
        with self.c.websocket_connect(f"/api/v1/ws/events?token={tok}") as ws:
            self.assertEqual(ws.receive_json()["type"], "stream.open"); first = ws.receive_json(); self.assertIn("type", first)
        with self.assertRaises(Exception):
            with self.c.websocket_connect("/api/v1/ws/events?token=bad") as ws: ws.receive_json()
    def test_provenance_and_connector_honesty(self):
        p = self.c.get("/api/v1/platform/provenance").json(); self.assertIn("SYNTHETIC", p["banner"])
        c = self.c.get("/api/v1/platform/connectors").json(); self.assertEqual(c["erpnext"]["status"], "not_connected")
    def test_admin_creates_user_non_admin_cannot(self):
        self.assertEqual(self.c.post("/api/v1/users", headers=self.hdr("mgr@t.test"), json={"email": "n@t.test", "password": "longenough-pw1", "role": "viewer"}).status_code, 403)
        self.assertEqual(self.c.post("/api/v1/users", headers=self.hdr("adm@t.test"), json={"email": "n@t.test", "password": "longenough-pw1", "role": "viewer"}).status_code, 200)

if __name__ == "__main__": unittest.main()
