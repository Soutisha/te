import unittest,math
from autonexus.data import seed
from autonexus.algorithms import *
from autonexus.recovery import *
from autonexus.compliance import *
from autonexus.audit import AuditChain
from autonexus import voice
class T(unittest.TestCase):
    def test_astar_matches_dijkstra(self):
        g=graph()
        for s in g:
            for t in g:
                self.assertAlmostEqual(dijkstra(g,s,t)["cost"],astar(g,s,t)["cost"],2)
    def test_blockage_reroutes_and_unreachable(self):
        base=dijkstra(graph(),"DealerA","DealerD")
        alt=dijkstra(graph([("DealerA","DealerB")]),"DealerA","DealerD")
        self.assertGreaterEqual(alt["cost"],base["cost"])
        iso=graph([("DealerA","DealerB"),("DealerA","WH2"),("DealerA","WH1")])
        self.assertIsNone(dijkstra(iso,"DealerA","DealerD")["path"])
    def test_hungarian_optimal(self):
        import itertools
        c=[[4,2,8],[4,3,7],[3,1,6]]
        _,v=hungarian(c); self.assertEqual(v,min(sum(c[i][p[i]] for i in range(3)) for p in itertools.permutations(range(3))))
    def test_seed_deterministic_and_sizes(self):
        a,b=seed(),seed(); self.assertEqual(a["stock"],b["stock"]); self.assertGreaterEqual(len(a["parts"]),100); self.assertEqual(len(a["ros"]),200)
        self.assertTrue(all(v>=0 for s in a["stock"].values() for v in s.values()))
    def test_full_recovery(self):
        db=seed(); au=AuditChain(); pl=plan(db,"DealerA","P000"); self.assertGreater(pl["shortage"]["shortage"],0)
        r=execute(db,pl,"inventory_manager",au); self.assertTrue(r["verified"]); self.assertTrue(au.verify())
        au.rec[0]["actor"]="evil"; self.assertFalse(au.verify())
    def test_unauthorised_and_no_stock(self):
        db=seed(); au=AuditChain(); pl=plan(db,"DealerA","P000")
        self.assertFalse(execute(db,pl,"supplier",au)["ok"])
        for s in db["stock"]: 
            if s!="DealerA": db["stock"][s]["P000"]=0
        self.assertIsNone(plan(db,"DealerA","P000")["best"])
    def test_compliance(self):
        db=seed(); self.assertFalse(check_vendor(db["vendors"],"V2",100)["approved"]); self.assertFalse(check_vendor(db["vendors"],"V1",9999)["approved"])
        r=invoice_vs_po({"lines":{"P000":100}},db["po"]["PO-1"]); self.assertFalse(r["approved"])
    def test_voice(self):
        c=voice.parse("Dealer B has received 25 brake pads"); self.assertEqual((c["dealer"],c["qty"]),("DealerB",25))
        db=seed(); au=AuditChain(); self.assertFalse(voice.apply(db,c,False,au)["ok"])
        n=db["stock"]["DealerB"]["P000"]; self.assertTrue(voice.apply(db,c,True,au)["ok"]); self.assertEqual(db["stock"]["DealerB"]["P000"],n+25)
        self.assertFalse(voice.parse("hello")["valid"])
if __name__=="__main__": unittest.main()
