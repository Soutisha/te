import unittest
from fastapi.testclient import TestClient
from autonexus import auth,drift,demo,ml
from unittest.mock import patch
import numpy as np
from autonexus.api import app
c=TestClient(app)
class T(unittest.TestCase):
    def test_health_and_login(self):
        self.assertTrue(c.get("/health").json()["ok"])
        email="owner@example.test"; password="test-owner-password"
        with patch.object(auth,"OWNER_EMAIL",email),patch.object(auth,"OWNER_PASSWORD_HASH",auth.hash_pw(password)):
            self.assertEqual(c.post("/auth/login",json={"email":"other@example.test","password":password}).status_code,401)
            self.assertEqual(c.post("/auth/login",json={"email":email,"password":"wrong"}).status_code,401)
            self.assertEqual(c.post("/auth/login",json={"email":email,"password":password}).status_code,200)
    def test_rbac(self):
        email="owner@example.test"; password="test-owner-password"
        with patch.object(auth,"OWNER_EMAIL",email),patch.object(auth,"OWNER_PASSWORD_HASH",auth.hash_pw(password)):
            token=c.post("/auth/login",json={"email":email,"password":password}).json()["token"]
            headers={"Authorization":"Bearer "+token}
            self.assertEqual(c.post("/secure/approve").status_code,401)
            self.assertEqual(c.post("/secure/approve",headers=headers).status_code,409)
            self.assertEqual(c.get("/secure/audit",headers=headers).status_code,200)
    def test_jwt_tamper_expiry(self):
        email="owner@example.test"
        with patch.object(auth,"OWNER_EMAIL",email):
            t=auth.make_token(email,"admin"); self.assertIsNotNone(auth.verify(t)); self.assertIsNone(auth.verify(t[:-2]+"zz")); self.assertIsNone(auth.verify(auth.make_token(email,"admin",ttl=-1)))
    def test_endpoints(self):
        self.assertEqual(c.get("/whatif/3").status_code,200); self.assertEqual(c.get("/evaluation").json()["runs"],30)
        self.assertTrue(c.get("/security/simulate").json()["contained"]); self.assertIn("SYNTHETIC",c.get("/ml/evaluate").json()["label"])
        self.assertEqual(c.post("/voice/parse",params={"text":"Dealer B has received 25 brake pads"}).json()["qty"],25)
    def test_dashboard_dataset(self):
        r=c.get("/dashboard/data"); self.assertEqual(r.status_code,200)
        d=r.json(); self.assertIn("SYNTHETIC",d["label"])
        self.assertEqual(len(d["inventory"]["sites"]),7); self.assertEqual(d["repairs"]["total"],200)
        self.assertEqual(d["demand"]["observations"],7200); self.assertIsInstance(d["demand"]["buckets"],list)
        self.assertTrue(d["network"]["route"])
        route=d["network"]
        planned=c.post("/recovery/plan",params={"dealer":route["destination"],"part":route["part"]})
        self.assertEqual(planned.status_code,200)
        self.assertGreater(planned.json()["shortage"]["shortage"],0)
        self.assertEqual(planned.json()["best"]["route"],route["route"])
        closed_edge=route["route"][:2]
        rerouted=c.post("/recovery/plan",params={
            "dealer":route["destination"],"part":route["part"],
            "blocked":"-".join(closed_edge),
        })
        self.assertEqual(rerouted.status_code,200)
        new_route=rerouted.json()["best"]["route"]
        self.assertNotEqual(new_route,route["route"])
        self.assertFalse(any(new_route[index:index+2]==closed_edge
                             or new_route[index:index+2]==closed_edge[::-1]
                             for index in range(len(new_route)-1)))
        custom=c.post("/recovery/plan",params={"dealer":route["destination"],"part":route["part"],"required_qty":route["shortage"]+planned.json()["shortage"]["have"]+3})
        self.assertEqual(custom.status_code,200)
        self.assertEqual(custom.json()["shortage"]["shortage"],route["shortage"]+3)
    def test_mock_telemetry_is_always_synthetic_and_read_only(self):
        with patch.dict("os.environ",{"DATA_PROVENANCE":"operational"}):
            response=c.get("/mock/telemetry/v1/snapshot")
        self.assertEqual(response.status_code,200)
        snapshot=response.json()
        self.assertEqual(snapshot["label"],"SYNTHETIC MOCK TELEMETRY")
        self.assertEqual(snapshot["source"]["kind"],"local_mock")
        self.assertEqual(snapshot["source"]["provenance"],"synthetic")
        self.assertEqual(snapshot["source"]["external_feed_status"],"mock_only")
        self.assertEqual(snapshot["feed"],{"id":"autonexus-local-mock","schema_version":"1.0","read_only":True})
        self.assertIn("inventory",snapshot)
        self.assertIn("repairs",snapshot)
        self.assertEqual(c.post("/mock/telemetry/v1/snapshot").status_code,405)
    def test_fed_and_cfg(self):
        r=c.get('/federated').json(); self.assertIn('federated',r); self.assertEqual(c.get('/site').status_code,200)
        s=c.get('/config/status').json(); self.assertNotIn('sk-',str(s)); self.assertIn('routing',s)
    def test_world_endpoints(self):
        c.post('/world/reset'); s=c.get('/world/state').json(); self.assertEqual(s['phase'],'idle'); self.assertFalse(s['rider']['visible'])
        self.assertEqual(c.post('/world/approve').status_code,401)
        self.assertEqual(c.post('/world/configure',params={"destination":"invalid","part":"invalid"}).status_code,422)
        configured=c.post('/world/configure',params={"destination":s["destinations"][0],"part":s["parts"][0]["id"],"required_qty":5})
        self.assertEqual(configured.status_code,200)
        with patch.object(auth,"OWNER_EMAIL","owner@example.test"),patch.object(auth,"OWNER_PASSWORD_HASH",auth.hash_pw("test-owner-password")):
            token=c.post("/auth/login",json={"email":"owner@example.test","password":"test-owner-password"}).json()["token"]
            self.assertEqual(c.post("/world/approve",headers={"Authorization":"Bearer "+token}).status_code,409)
        self.assertEqual(c.get('/world').status_code,200)
        with c.websocket_connect('/ws/world') as w: self.assertIn('phase',w.receive_json())
    def test_websocket(self):
        with c.websocket_connect("/ws") as w: self.assertIn("audit_records",w.receive_json())
    def test_demo_full_120s(self):
        d=demo.Demo(); log=d.run_all(); self.assertEqual(len(log),12); self.assertEqual(log[-1]["data"],{"verified":True,"audit_valid":True})
        self.assertEqual(log[-1]["t"],115)
    def test_demo_pause_restart(self):
        d=demo.Demo(); d.step(); d.pause(); self.assertIsNone(d.step()); d.resume(); self.assertIsNotNone(d.step()); d.restart(); self.assertEqual(d.i,0)
    def test_drift(self):
        r=np.random.default_rng(0); a=r.normal(0,1,1000); self.assertEqual(drift.status(drift.psi(a,r.normal(0,1,1000))),"stable"); self.assertEqual(drift.status(drift.psi(a,r.normal(2,1,1000))),"significant drift")
class Provenance(unittest.TestCase):
    def test_integrations_are_honestly_classified(self):
        d=c.get("/integrations/status").json(); by={i["name"]:i for i in d["integrations"]}
        self.assertNotIn("LIVE",[i["status"] for i in d["integrations"]])  # nothing is probed, so nothing may claim LIVE
        self.assertEqual(by["Dealership telemetry / DMS / ERP"]["status"],"SIMULATED")
        self.assertIn("read-only",by["Dealership telemetry / DMS / ERP"]["needs"])
        self.assertEqual(by["Federated learning (FedAvg)"]["status"],"LOCAL")
    def test_top_parts_have_readable_names(self):
        p=c.get("/dashboard/data").json()["inventory"]["top_parts"]; self.assertTrue(p and all(x["name"] and x["name"]!=x["part"] for x in p))
    def test_dashboard_has_axis_titles_and_two_chart_types(self):
        h=c.get("/").text; self.assertIn("function columns(",h); self.assertIn("function lollipop(",h); self.assertIn("xTitle",h); self.assertIn("yTitle",h)
class Feed(unittest.TestCase):
    def test_default_is_synthetic_and_valid(self):
        f=c.get("/telemetry/feed").json(); self.assertEqual((f["status"],f["kind"]),("SIMULATED","synthetic")); self.assertFalse(f["errors"]); self.assertGreater(f["summary"]["total_units"],0)
    def test_live_only_after_real_validated_call(self):
        import threading,json as J
        from http.server import HTTPServer,BaseHTTPRequestHandler
        from autonexus import feed
        snap=c.get("/mock/telemetry/v1/snapshot").json()
        class H(BaseHTTPRequestHandler):
            def do_GET(s): b=J.dumps(snap if s.path=="/ok" else {"inventory":{"sites":[{"site":"A","units":-5}]}}).encode(); s.send_response(200); s.send_header("Content-Type","application/json"); s.end_headers(); s.wfile.write(b)
            def log_message(s,*a): pass
        srv=HTTPServer(("127.0.0.1",0),H); threading.Thread(target=srv.serve_forever,daemon=True).start(); port=srv.server_port
        ok=feed.fetch(f"http://localhost:{port}/ok",None,lambda:1/0); self.assertEqual((ok["status"],ok["kind"]),("LIVE","external"))
        bad=feed.fetch(f"http://localhost:{port}/bad",None,lambda:1/0); self.assertEqual(bad["status"],"ERROR"); self.assertTrue(bad["errors"])
        dead=feed.fetch("http://localhost:1/x",None,lambda:{"would":"be synthetic"}); self.assertEqual(dead["status"],"ERROR")  # no silent fallback
        self.assertEqual(feed.fetch("http://evil.example/x",None,lambda:1)["status"],"ERROR")  # plain http to a remote host refused
        srv.shutdown()
    def test_integration_row_reflects_feed(self):
        r=[i for i in c.get("/integrations/status").json()["integrations"] if i["name"].startswith("Dealership")][0]; self.assertEqual(r["status"],"SIMULATED")
