import os, json
from sqlalchemy import create_engine, Column, Integer, String, Text, Float, select
from sqlalchemy.orm import declarative_base, Session
Base=declarative_base()
class StockRow(Base): __tablename__="inventory"; id=Column(Integer,primary_key=True); site=Column(String); part=Column(String); qty=Column(Integer)
class AuditRow(Base): __tablename__="audit_events"; id=Column(Integer,primary_key=True); body=Column(Text)
def engine(url=None): 
    e=create_engine(url or os.environ.get("DATABASE_URL","sqlite:///autonexus.db")); Base.metadata.create_all(e); return e
def save(e,db,audit):
    with Session(e) as s:
        s.query(StockRow).delete(); s.query(AuditRow).delete()
        s.add_all([StockRow(site=a,part=p,qty=q) for a,d in db["stock"].items() for p,q in d.items()])
        s.add_all([AuditRow(body=json.dumps(r,default=str)) for r in audit.rec]); s.commit()
def load(e,db,audit):
    with Session(e) as s:
        for r in s.scalars(select(StockRow)): db["stock"][r.site][r.part]=r.qty
        audit.rec=[json.loads(r.body) for r in s.scalars(select(AuditRow).order_by(AuditRow.id))]
