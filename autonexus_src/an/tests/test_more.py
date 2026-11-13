import unittest,io,os,tempfile,shutil
from autonexus import optim,db as dbm,copilot,adapters,simbays,ocr
from autonexus.data import seed
from autonexus.audit import AuditChain
class T(unittest.TestCase):
    def test_ortools(self):
        d={"DealerA":5,"DealerB":5,"DealerC":5,"DealerD":5}; r=optim.vrp_ortools("WH1",list(d),d,10,3)
        self.assertEqual(sorted(x for v in r for x in v),sorted(d)); self.assertTrue(all(sum(d[s] for s in v)<=10 for v in r))
    def test_persistence_roundtrip(self):
        with tempfile.NamedTemporaryFile(suffix=".db",delete=False) as handle: f=handle.name
        e=dbm.engine("sqlite:///"+f); d=seed(); a=AuditChain(); d["stock"]["DealerA"]["P000"]=99; a.add("x","y","z"); dbm.save(e,d,a)
        try:
            d2=seed(); a2=AuditChain(); dbm.load(e,d2,a2); self.assertEqual(d2["stock"]["DealerA"]["P000"],99); self.assertTrue(a2.verify())
        finally:
            e.dispose()
            if os.path.exists(f): os.remove(f)
    def test_copilot_uses_tools(self):
        d=seed(); r=copilot.ask(d,"Which dealership has shortage risk?"); self.assertEqual(r["tool"],"detect_shortage"); self.assertTrue(r["cites"])
        self.assertEqual(copilot.ask(d,"Recommend inventory transfers")["tool"],"plan_transfer"); self.assertIsNone(copilot.ask(d,"tell a joke")["tool"])
    def test_simpy_more_bays_less_wait(self): self.assertLess(simbays.run(6)["mean_wait_h"],simbays.run(2)["mean_wait_h"])
    def test_adapter_is_mock(self): self.assertFalse(adapters.CDKMock().push_stock(seed())["live"])
    @unittest.skipUnless(shutil.which("tesseract"),"Tesseract OCR binary is not installed")
    def test_real_ocr(self):
        from PIL import Image,ImageDraw,ImageFont
        im=Image.new("RGB",(900,200),"white"); dr=ImageDraw.Draw(im)
        try: f=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",34)
        except Exception: f=None
        dr.text((20,20),"INVOICE No: INV-9",fill="black",font=f); dr.text((20,70),"Vendor: V1",fill="black",font=f); dr.text((20,120),"P000 x 100",fill="black",font=f)
        b=io.BytesIO(); im.save(b,"PNG"); r=ocr.extract_image(b.getvalue()); self.assertEqual(r["type"],"invoice"); self.assertEqual(r["lines"].get("P000"),100)
