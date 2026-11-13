import unittest
from autonexus import ml,optim,cybershield,docs,rag,agents,evaluation,whatif
from autonexus.data import seed
from autonexus.audit import AuditChain
class T(unittest.TestCase):
    def test_ml_temporal_and_reproducible(self):
        a=ml.train_eval(7); b=ml.train_eval(7)
        self.assertEqual(a["models"]["random_forest"],b["models"]["random_forest"]); self.assertGreater(a["models"][a["best"]]["roc_auc"],.6)
        self.assertIn("SYNTHETIC",a["label"]); self.assertIn("brier",a["models"][a["best"]])
    def test_anomaly(self): self.assertGreater(ml.anomaly_eval()["recall"],.8)
    def test_ga_beats_or_matches_baseline(self):
        stops=["DealerB","DealerC","DealerD","DealerE","WH1"]; o,l=optim.ga_order(stops,"DealerA"); self.assertEqual(sorted(o),sorted(stops)); self.assertLessEqual(l,optim.route_baseline(stops,"DealerA")+1e-9)
    def test_vrp_capacity(self):
        r=optim.vrp("WH1",["DealerA","DealerB","DealerC"],{"DealerA":5,"DealerB":5,"DealerC":5},10); self.assertTrue(all(sum(5 for _ in x)<=10 for x in r)); self.assertEqual(sum(map(len,r)),3)
    def test_assign_skills(self):
        a=optim.assign({"T1":{"brakes"},"T2":{"engine"}},[("R1","brakes",5),("R2","engine",3)]); self.assertEqual(a,{"R1":"T1","R2":"T2"})
    def test_montecarlo(self): m=optim.monte_carlo(10,5); self.assertGreater(m["p95"],m["p50"])
    def test_cyber(self): r=cybershield.analyse(cybershield.simulate_attack()); self.assertTrue(r["contained"]); self.assertEqual(cybershield.analyse(cybershield.simulate_attack()[:3])["risk"],0)
    def test_docs(self):
        t="INVOICE No: INV-9\nVendor: V1\nP000 x 100"; f=docs.extract(t); self.assertEqual((f["type"],f["lines"]),("invoice",{"P000":100}))
    def test_rag_acl(self):
        R=rag.RAG(rag.DOCS); self.assertEqual(R.query("security incident lock account","technician")[0]["id"]!="SEC-2",True)
        self.assertEqual(R.query("purchase limit approval","procurement")[0]["id"],"POL-1")
    def test_graph(self): g=rag.Graph(); g.add("V1","supplies","P000"); self.assertEqual(g.dependency("V1"),["P000"])
    def test_orchestrator_end_to_end(self):
        db=seed(); au=AuditChain(); o=agents.Orchestrator(db,au); st=o.run(blocked=[("DealerA","WH1")])
        self.assertEqual(st["status"],"awaiting_approval"); self.assertEqual(st["blocked_vendors"],["V2"]); self.assertTrue(st["security"]["contained"])
        self.assertEqual({t["agent"] for t in st["trace"]},{"Predictive","Inventory","Vendor","Compliance&Security","Scheduling"})
        self.assertEqual(o.approve("auditor")["status"],"awaiting_approval")
        self.assertEqual(o.approve("inventory_manager")["status"],"recovered"); self.assertTrue(au.verify())
    def test_eval(self):
        e=evaluation.compare(); self.assertEqual(e["runs"],30); self.assertGreater(e["resolution_hours"]["improvement_pct"],0)
    def test_whatif_all(self):
        for n in range(1,8): r=whatif.run(n); self.assertTrue(r["audit_valid"])
