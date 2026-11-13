"""MOCK DMS adapters. No real CDK/Reynolds integration is implemented or claimed."""
class MockDMS:
    name="mock"
    def push_stock(s,db): return {"adapter":s.name,"records":sum(len(v) for v in db["stock"].values()),"live":False}
class CDKMock(MockDMS): name="CDK(mock)"
class ReynoldsMock(MockDMS): name="Reynolds(mock)"
