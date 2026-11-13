import unittest,csv,os,tempfile
from autonexus import gen_csv,federated,config
D=tempfile.mkdtemp(); gen_csv.generate(D)
R=lambda n:list(csv.DictReader(open(os.path.join(D,n+".csv"))))
class T(unittest.TestCase):
    def test_all_19_and_sizes(self):
        self.assertEqual(len([f for f in os.listdir(D) if f.endswith(".csv")]),19)
        self.assertGreaterEqual(len(R("parts")),100); self.assertEqual(len(R("repair_orders")),200); self.assertGreaterEqual(len(R("inventory_movements")),100); self.assertGreaterEqual(len(R("deliveries")),50)
        self.assertEqual((len(R("technicians")),len(R("service_bays")),len(R("dealerships")),len(R("warehouses")),len(R("suppliers"))),(20,10,5,2,3))
    def test_referential_integrity(self):
        sites={r["dealership_id"] for r in R("dealerships")}|{r["warehouse_id"] for r in R("warehouses")}; parts={r["part_id"] for r in R("parts")}
        tech={r["technician_id"] for r in R("technicians")}; veh={r["vehicle_id"] for r in R("vehicle_records")}; bays={r["bay_id"] for r in R("service_bays")}; ro={r["repair_order_id"] for r in R("repair_orders")}
        for r in R("repair_orders"): self.assertIn(r["part_id"],parts); self.assertIn(r["technician_id"],tech); self.assertIn(r["vehicle_id"],veh)
        for r in R("appointments"): self.assertIn(r["repair_order_id"],ro); self.assertIn(r["bay_id"],bays)
        for r in R("inventory"): self.assertIn(r["site_id"],sites); self.assertIn(r["part_id"],parts); self.assertGreaterEqual(int(r["qty"]),0)
        for f in R("inventory_movements")+R("deliveries"): self.assertIn(f["source"],sites); self.assertIn(f["destination"],sites); self.assertNotEqual(f["source"],f["destination"])
        for r in R("road_network"): self.assertIn(r["from"],sites); self.assertIn(r["to"],sites)
        sup={r["supplier_id"] for r in R("suppliers")}
        for r in R("purchase_orders")+R("quotations"): self.assertIn(r["supplier_id"],sup)
    def test_policy_limits_respected(self):
        lim=max(float(p["limit"]) for p in R("procurement_policies"))
        for po in R("purchase_orders"): self.assertLessEqual(float(po["amount"]),lim)
    def test_deterministic(self):
        d2=tempfile.mkdtemp(); gen_csv.generate(d2); self.assertEqual(open(os.path.join(D,"inventory.csv")).read(),open(os.path.join(d2,"inventory.csv")).read())
    def test_federated(self):
        r=federated.run(os.path.join(D,"historical_demand.csv"),rounds=20)
        self.assertGreater(r["federated"]["f1"],r["local_only_mean_f1"]); self.assertLess(abs(r["federated"]["f1"]-r["centralised"]["f1"]),.1)
        self.assertLess(r["communication_bytes_federated"],r["raw_bytes_centralised"]); self.assertIn("NOT a privacy guarantee",r["privacy_note"])
    def test_env_comments_not_values(self):
        for k in ["ORS_API_KEY","HF_TOKEN","SENTRY_DSN"]: os.environ.pop(k,None)
        p=tempfile.mktemp(); open(p,"w").write("ORS_API_KEY=   # free key\nHF_TOKEN=abc # c\n"); config.load_env(p); self.assertEqual(config.get("ORS_API_KEY"),""); self.assertEqual(config.get("HF_TOKEN"),"abc")
