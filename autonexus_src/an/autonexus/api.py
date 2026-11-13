import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, Header, UploadFile, File, WebSocket, WebSocketDisconnect, Query, Body, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from . import auth, config as cfg
from .recovery import plan,execute
from .audit import AuditChain
from .voice import parse, parse_lot_walk
from .telemetry import load_world_dataset, planner_database, read_rows

_ROOT=os.path.dirname(os.path.dirname(__file__))
_DATA=os.path.join(_ROOT,"data")
_UI=os.path.join(_ROOT,"ui")
_dataset=load_world_dataset(_DATA)
DB=planner_database(_dataset)
DB["parts"]=[{"id":key,"name":value["name"]} for key,value in _dataset["parts"].items()]
AUD=AuditChain()

@asynccontextmanager
async def lifespan(_):
    task=asyncio.create_task(_world_loop())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

app=FastAPI(title="AUTONEXUS Core",lifespan=lifespan)
app.mount("/app", StaticFiles(directory=os.path.join(_UI, "app"), html=True), name="app_shell")


class LoginRequest(BaseModel):
    email: str
    password: str

class TextPayload(BaseModel):
    text: str

class LotWalkPayload(BaseModel):
    text: str

def user(authorization:str=Header(None)):
    token=(authorization or "")
    if not token.startswith("Bearer "):
        raise HTTPException(401,"authentication required")
    claims=auth.verify(token[7:])
    if not claims:
        raise HTTPException(401,"invalid or expired owner session")
    return claims

@app.get("/health")
def health(): return {"ok":True}
@app.post("/recovery/plan")
def p(dealer:str|None=None,part:str|None=None,required_qty:int|None=None,
      blocked:list[str]=Query(default=[])):
    dealer=dealer or _dataset["dealerships"][0]
    part=part or next(iter(_dataset["parts"]))
    return plan(DB,dealer,part,[tuple(b.split("-")) for b in blocked],
                required_qty=required_qty,network=_dataset["network"])
@app.post("/recovery/execute")
def e(dealer:str|None=None,part:str|None=None,blocked:list[str]=Query(default=[]),
       u=Depends(user)):
    dealer=dealer or _dataset["dealerships"][0]
    part=part or next(iter(_dataset["parts"]))
    return execute(DB,plan(DB,dealer,part,[tuple(b.split("-")) for b in blocked],
                           network=_dataset["network"]),u["role"],AUD)
@app.get("/audit/verify")
def v(): return {"valid":AUD.verify(),"records":len(AUD.rec)}
@app.post("/voice/parse")
def vp(text:str|None=Query(None), payload:TextPayload|None=Body(None)):
    value=payload.text if payload is not None else text
    if not value or not value.strip(): raise HTTPException(422,"Enter an instruction to preview.")
    if len(value)>100000: raise HTTPException(413,"Instruction text exceeds the 100,000 character limit.")
    return parse(value)
def _transcribe_local_audio(data: bytes):
    import io
    from functools import lru_cache
    from .config import get
    model_path=get("WHISPER_MODEL_PATH") or os.path.join(_ROOT,"models","faster-whisper-base")
    if not os.path.isdir(model_path):
        raise HTTPException(503,"Local multilingual speech model is not installed. Set WHISPER_MODEL_PATH to a local faster-whisper model folder.")
    try:
        from faster_whisper import WhisperModel
        from faster_whisper.audio import decode_audio
    except ImportError as exc:
        raise HTTPException(503,"Local transcription needs faster-whisper installed from the project requirements.") from exc
    try:
        model=_local_whisper_model(model_path)
        audio=decode_audio(io.BytesIO(data),sampling_rate=16000)
        segments,info=model.transcribe(audio,beam_size=1,language=None,multilingual=True,vad_filter=True)
        transcript=" ".join(part.text.strip() for part in segments).strip()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422,"Could not decode or transcribe this local audio recording.") from exc
    if not transcript:
        raise HTTPException(422,"No speech was recognized. Try again closer to the microphone.")
    return {"transcript":transcript,"engine":"faster_whisper_local","language":info.language,
            "language_probability":round(float(info.language_probability),3),"model":os.path.basename(model_path)}

from functools import lru_cache as _lru_cache
@_lru_cache(maxsize=1)
def _local_whisper_model(model_path):
    from faster_whisper import WhisperModel
    return WhisperModel(model_path,device="cpu",compute_type="int8",local_files_only=True)

@app.post("/voice/transcribe")
async def transcribe_voice(file:UploadFile=File(...)):
    from starlette.concurrency import run_in_threadpool
    data=await file.read()
    if not data: raise HTTPException(422,"The audio recording is empty.")
    if len(data)>25*1024*1024: raise HTTPException(413,"Audio recording is over the 25 MB local limit.")
    return await run_in_threadpool(_transcribe_local_audio,data)
# ---- extended endpoints (UNTESTED: fastapi not installable in build sandbox) ----
from . import whatif, evaluation, ml, cybershield, docs, agents
ORCH=agents.Orchestrator(DB,AUD)
@app.post("/agents/run")
def ar(dealer:str|None=None,part:str|None=None,blocked:list[str]=Query(default=[])):
    return agents.Orchestrator.run(ORCH,dealer or _dataset["dealerships"][0],
                                   part or next(iter(_dataset["parts"])),
                                   blocked=[tuple(b.split("-")) for b in blocked])
@app.post("/agents/approve")
def aa(u=Depends(user)):
    result=ORCH.approve(u["role"])
    if result.get("ok") is False:
        raise HTTPException(409,result["error"])
    return result
@app.get("/whatif/{n}")
def wi(n:int): return whatif.run(n)
@app.get("/evaluation")
def ev(): return evaluation.compare()
@app.get("/ml/evaluate")
def mle(): r=ml.train_eval(); r.pop("_model"); return r
@app.post("/documents/extract")
def dx(text:str|None=Query(None), payload:TextPayload|None=Body(None)):
    value=payload.text if payload is not None else text
    if not value or not value.strip(): raise HTTPException(422,"Paste document text before extracting fields.")
    if len(value)>100000: raise HTTPException(413,"Document text exceeds the 100,000 character limit.")
    return docs.extract(value)
@app.post("/documents/extract-file")
async def dx_file(file:UploadFile=File(...)):
    from .document_validation import extract_file
    try:
        return extract_file(await file.read(),file.filename or "upload",file.content_type or "")
    except ocr.OCRUnavailable as exc:
        raise HTTPException(503,str(exc)) from exc
    except OverflowError as exc:
        raise HTTPException(413,str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503,str(exc)) from exc
@app.post("/documents/validate")
async def validate_document_package(vehicle_id:str=Form(...),files:list[UploadFile]=File(...)):
    from . import document_validation
    try:
        extracted=[]
        for file in files:
            extracted.append(document_validation.extract_file(await file.read(),file.filename or "upload",file.content_type or ""))
        return document_validation.validate_package(vehicle_id,extracted,read_rows(_DATA,"vehicle_records"))
    except KeyError as exc:
        raise HTTPException(422,f"Required document data was not found: {exc}") from exc
    except ocr.OCRUnavailable as exc:
        raise HTTPException(503,str(exc)) from exc
    except OverflowError as exc:
        raise HTTPException(413,str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503,str(exc)) from exc
@app.post("/vehicles/lot-walk/preview")
def preview_lot_walk(payload:LotWalkPayload):
    return parse_lot_walk(payload.text,read_rows(_DATA,"vehicle_records"))
@app.post("/vehicles/lot-walk/apply")
def apply_lot_walk(payload:LotWalkPayload,u=Depends(user)):
    parsed=parse_lot_walk(payload.text,read_rows(_DATA,"vehicle_records"))
    if not parsed["valid"]: raise HTTPException(422,{"message":"Lot-walk note needs a known vehicle and a location.","issues":parsed["issues"]})
    from .core import api_v1 as core_api, db as core_db, models as core_models, audit as core_audit, events as core_events
    core_api.ensure_init()
    with core_db.write() as s:
        if not s.get(core_models.Vehicle,parsed["vehicle_id"]): raise HTTPException(404,"vehicle is not loaded in the local operations database")
        row=core_models.VehicleWalkUpdate(vehicle_id=parsed["vehicle_id"],location=parsed["location"],condition=parsed["condition"],
                                           status=parsed["status"],notes=parsed["notes"],transcript=parsed["transcript"],actor=u["sub"])
        s.add(row); s.flush()
        core_audit.add(s,u["sub"],"vehicle.lot_walk.updated",{"vehicle_id":row.vehicle_id,"location":row.location,"condition":row.condition,"status":row.status},"updated")
        core_events.emit(s,"vehicle.lot_walk.updated",{"vehicle_id":row.vehicle_id,"location":row.location,"condition":row.condition,"status":row.status},source="voice_lot_walk")
        result={"id":row.id,"vehicle_id":row.vehicle_id,"location":row.location,"condition":row.condition,"status":row.status,
                "notes":row.notes,"updated_by":row.actor,"updated_at":row.created_at.isoformat() if row.created_at else None,
                "message":"Lot-walk update saved to the local vehicle inventory."}
    return result
@app.get("/security/simulate")
def sec(): return cybershield.analyse(cybershield.simulate_attack())
@app.websocket("/ws")
async def ws(w:WebSocket):
    await w.accept(); await w.send_json({"audit_records":len(AUD.rec),"status":ORCH.state["status"]}); await w.close()

# ---- auth + protected endpoints ----
from . import demo as demomod
from .compliance import allowed

@app.post("/auth/login")
def login(credentials:LoginRequest):
    claims=auth.authenticate(credentials.email,credentials.password)
    if not claims: raise HTTPException(401,"invalid credentials or owner account is not configured")
    return {"token":auth.make_token(claims["sub"],claims["role"]),"role":claims["role"]}
@app.post("/secure/approve")
def sec_approve(u=Depends(user)):
    if not allowed(u["role"],"transfer:approve"): AUD.add(u["sub"],"approve_denied","transfer","rejected"); raise HTTPException(403,"forbidden")
    result=ORCH.approve(u["role"])
    if result.get("ok") is False:
        raise HTTPException(409,result["error"])
    return result
@app.get("/secure/audit")
def sec_audit(u=Depends(user)):
    if not allowed(u["role"],"audit:read") and u["role"]!="admin": raise HTTPException(403,"forbidden")
    return AUD.rec
DEMO=demomod.Demo()
@app.post("/demo/{cmd}")
def demo_cmd(cmd:str):
    global DEMO
    if cmd=="restart": DEMO=demomod.Demo()
    elif cmd=="pause": DEMO.pause()
    elif cmd=="resume": DEMO.resume()
    elif cmd=="next": return DEMO.step()
    elif cmd=="all": return DEMO.run_all()
    return {"i":DEMO.i}

# ---- dashboard, copilot, OCR, persistence ----
from . import copilot, ocr, db as dbm, simbays
@app.get("/copilot")
def cp(q:str): return copilot.ask(DB,q)
@app.post("/ocr")
async def ocr_ep(file:UploadFile=File(...)):
    try:
        return ocr.extract_image(await file.read())
    except ocr.OCRUnavailable as exc:
        raise HTTPException(503,str(exc))
    except ValueError as exc:
        raise HTTPException(422,str(exc))
@app.post("/persist/save")
def psave(): e=dbm.engine(); dbm.save(e,DB,AUD); return {"saved":True}
@app.get("/simulate/bays")
def sb(bays:int=4): return simbays.run(bays)
@app.get("/state")
def state():
    part=next(iter(_dataset["parts"]))
    return {"stock":{site:values.get(part,0) for site,values in DB["stock"].items()},
            "part":part,"audit_records":len(AUD.rec),"audit_valid":AUD.verify(),
            "status":ORCH.state["status"]}
@app.get("/ops",response_class=HTMLResponse)
def ops_redirect():
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/app/")

@app.get("/",response_class=HTMLResponse)
def root(): return (Path(_UI)/"dashboard.html").read_text(encoding="utf-8")
@app.get("/ui/{name}",response_class=HTMLResponse)
def ui(name:str):
    page=Path(_UI)/os.path.basename(name)
    return page.read_text(encoding="utf-8") if page.is_file() else HTMLResponse("not found",404)

from . import federated as fedm
@app.get("/federated")
def fed_ep(): return fedm.run(os.path.join(_DATA,"historical_demand.csv"))
@app.get("/config/status")
def cfg_status(): return cfg.status()
@app.get("/site",response_class=HTMLResponse)
def site(): return (Path(_UI)/"site.html").read_text(encoding="utf-8")

@app.get("/dashboard/data")
def dashboard_data():
    dataset=load_world_dataset(_DATA)
    rows=lambda name:read_rows(_DATA,name)

    inventory=rows("inventory")
    site_stock={}
    part_stock={}
    stock_by_part={}
    for r in inventory:
        qty=int(r["qty"])
        site_stock.setdefault(r["site_id"],{"site":r["site_id"],"units":0,"low_skus":0,"sku_count":0})
        site_stock[r["site_id"]]["units"]+=qty
        site_stock[r["site_id"]]["sku_count"]+=1
        site_stock[r["site_id"]]["low_skus"]+=qty<10
        part_stock[r["part_id"]]=part_stock.get(r["part_id"],0)+qty
        site_parts=stock_by_part.setdefault(r["site_id"],{})
        site_parts[r["part_id"]]=site_parts.get(r["part_id"],0)+qty

    repairs=rows("repair_orders")
    repair_sites={}
    repair_status={}
    priorities={}
    for r in repairs:
        repair_sites[r["dealership_id"]]=repair_sites.get(r["dealership_id"],0)+1
        repair_status[r["status"]]=repair_status.get(r["status"],0)+1
        priorities[r["priority"]]=priorities.get(r["priority"],0)+1

    bays=rows("service_bays")
    bay_sites={}
    for r in bays:
        site=bay_sites.setdefault(r["dealership_id"],{"site":r["dealership_id"],"total":0,"available":0})
        site["total"]+=1
        site["available"]+=int(r["available"])

    suppliers=rows("suppliers")
    purchase_orders=rows("purchase_orders")
    supplier_metrics=[]
    for s in suppliers:
        pos=[r for r in purchase_orders if r["supplier_id"]==s["supplier_id"]]
        supplier_metrics.append({
            "id":s["supplier_id"],"name":s["name"],
            "reliability":float(s["reliability"]),
            "lead_time_days":int(s["lead_time_days"]),
            "restricted":bool(int(s["restricted"])),
            "orders": len(pos),
"order_value": round(sum(float(r.get("value") or r.get("amount") or 0) for r in pos), 2),
        })

    delivery_status={}
    for r in rows("deliveries"):
        delivery_status[r["status"]]=delivery_status.get(r["status"],0)+1

    buckets={}
    demand_rows=rows("historical_demand")
    for r in demand_rows:
        bucket=int(r["day"])//6
        item=buckets.setdefault(bucket,{"day":bucket*6,"demand":0.0,"stockouts":0,"count":0})
        item["demand"]+=float(r["avg_demand"])
        item["stockouts"]+=int(r["stockout_next7"])
        item["count"]+=1
    demand=[]
    for item in buckets.values():
        count=item.pop("count")
        demand.append({
            "day":item["day"],
            "avg_demand":round(item["demand"]/count,2),
            "stockout_rate":round(item["stockouts"]/count,3),
        })

    security=rows("security_events")
    security_actions={}
    for r in security:
        security_actions[r["action"]]=security_actions.get(r["action"],0)+1
    planner_db=planner_database(dataset)
    destination=dataset["dealerships"][0]
    part=next(iter(dataset["parts"]))
    route_plan=None
    for candidate_dealer in dataset["dealerships"]:
        for candidate_part in dataset["parts"]:
            candidate_demand=sum(r["qty"] for r in planner_db["ros"]
                                 if r["dealer"]==candidate_dealer and r["part"]==candidate_part)
            candidate=plan(planner_db,candidate_dealer,candidate_part,
                           required_qty=candidate_demand,network=dataset["network"])
            if candidate.get("best"):
                destination,part,route_plan=candidate_dealer,candidate_part,candidate
                break
        if route_plan:
            break
    if route_plan is None:
        route_plan=plan(planner_db,destination,part,required_qty=0,
                        network=dataset["network"])
    best=route_plan.get("best")
    source_kind=cfg.get("DATA_PROVENANCE","synthetic").strip().lower()
    if source_kind not in {"synthetic","operational"}:
        raise HTTPException(500,"DATA_PROVENANCE must be 'synthetic' or 'operational'.")
    modified=datetime.fromtimestamp(dataset["updated_at"],timezone.utc).isoformat()
    site_rows=dataset["sites"]
    coords=dataset["network"]["nodes"]
    inventory_sites=list(site_stock.values())
    network_nodes=[{"id":key,"x":coords[key][0],"y":coords[key][1]}
                   for key in site_rows]
    network_edges=[{"from":a,"to":b,"cost":cost}
                   for (a,b),cost in dataset["network"]["edge_map"].items()]
    return {
        "label":"OPERATIONAL TELEMETRY" if source_kind=="operational" else "SYNTHETIC SAMPLE DATA",
        "source":{"kind":"csv_directory","provenance":source_kind,
                  "refreshed_at":modified,
                  "external_feed_status":"external_configured" if __import__("autonexus.config",fromlist=["x"]).get("TELEMETRY_URL") else "synthetic_feed"},
        "inventory":{
            "total_units":sum(x["units"] for x in site_stock.values()),
            "sites":inventory_sites,
            "part_stock_by_site":stock_by_part,
            "low_stock_skus":sum(x["low_skus"] for x in site_stock.values()),
            "top_parts":[{"part":k,"name":dataset["parts"].get(k,{}).get("name",k),"units":v} for k,v in sorted(part_stock.items(),key=lambda x:x[1],reverse=True)[:8]],
            "parts":[{"id":key,"name":value["name"]} for key,value in dataset["parts"].items()],
        },
        "repairs":{
            "total":len(repairs),"by_site":[{"site":k,"count":v} for k,v in sorted(repair_sites.items())],
            "by_status":repair_status,"by_priority":[{"priority":k,"count":v} for k,v in sorted(priorities.items())],
        },
        "bays":list(bay_sites.values()),
        "suppliers":supplier_metrics,
        "deliveries":{"total":len(rows("deliveries")),"by_status":delivery_status},
        "demand":{"days":len({r["day"] for r in demand_rows}),"observations":len(demand_rows),"buckets":demand},
        "security":{"total":len(security),"flagged":sum(int(r["is_attack"]) for r in security),"by_action":security_actions},
        "network":{
            "nodes":network_nodes,
            "edges":network_edges,
            "route":best["route"] if best else [],
            "route_cost":best["cost"] if best else None,
            "shortage":route_plan.get("shortage",{}).get("shortage",0),
            "destination":destination,"part":part,
        },
    }

@app.get("/telemetry/feed")
def telemetry_feed():
    from . import feed, config
    if config.get("OFFLINE_MODE", "1") == "1":
        return feed.fetch(None, None, mock_telemetry_snapshot)
    return feed.fetch(config.get("TELEMETRY_URL"),config.get("TELEMETRY_TOKEN"),mock_telemetry_snapshot)

@app.get("/integrations/status")
def integrations_status():
    """Honest classification of every integration. Nothing here is probed over the network: it reports what is configured and what is simulated."""
    c=cfg_status=__import__("autonexus.config",fromlist=["x"]).status()
    config=__import__("autonexus.config",fromlist=["x"])
    def row(name,status,why,needs=""): return {"name":name,"status":status,"why":why,"needs":needs}
    feed=telemetry_feed()
    has_osrm=bool(config.get("OSRM_URL")) and not c.get("offline_mode")
    return {"legend":{"LIVE":"proved by a successful end-to-end call (none are probed automatically)","CONFIGURED":"supported endpoint is configured but not verified here","LOCAL":"working local implementation","SIMULATED":"synthetic data or simulated events","OFFLINE":"not configured","NEEDS_CREDENTIALS":"needs credentials or an endpoint","NOT_IMPLEMENTED":"this build has no adapter; adding a key alone does not enable it"},
     "integrations":[
      row("Dealership telemetry / DMS / ERP",feed["status"],("Local mode: synthetic, read-only schema 1.0 snapshot from data/*.csv; not real dealership data." if feed["kind"]=="synthetic" and feed["status"]=="SIMULATED" else "External feed "+feed["url"]+" "+("validated OK." if feed["status"]=="LIVE" else "failed: "+"; ".join(feed["errors"]))),"None for local use. External telemetry is optional and requires OFFLINE_MODE=0 plus TELEMETRY_URL (HTTPS schema 1.0 JSON)."),
      row("Living World stream","SIMULATED","/ws/world streams state from the local simulation and CSV-backed algorithms; it is not a live dealership feed."),
      row("Machine learning (XGBoost/RF/Isolation Forest)","SIMULATED","Trained on synthetic generated demand history, so scores describe the generator, not real dealerships."),
      row("Federated learning (FedAvg)","LOCAL","Real FedAvg maths over 5 synthetic dealer datasets in one process. No network exchange, no secure aggregation, no differential privacy."),
      row("Operations copilot","LOCAL","Uses the local rule router. No LLM API key or network access is needed."),
      row("Road network / routing","CONFIGURED" if has_osrm else "LOCAL",("Local mode uses A* over road_network.csv; external routing is disabled." if c.get("offline_mode") else "Uses the local graph unless an OSRM endpoint is configured."),"None for local use. OSRM_URL is optional when OFFLINE_MODE=0."),
      row("Geocoding / maps","LOCAL","The map uses coordinates from the local dataset. External geocoding is not needed or enabled."),
      row("Monitoring / logs","LOCAL","Standard server logs are local; no Sentry service is required."),
      row("Database persistence (SQLite)","CONFIGURED" if c.get("database")=="postgresql" else "LOCAL",("PostgreSQL is configured." if c.get("database")=="postgresql" else "Local SQLite database file is active."),"None for local use; AUTONEXUS_DB_URL is optional if you later choose PostgreSQL."),
      row("Owner authentication","LOCAL" if c.get("owner_auth_configured") else "OFFLINE","Local JWT + hashed password.","OWNER_EMAIL and OWNER_PASSWORD_HASH")]}

@app.get("/mock/telemetry/v1/snapshot")
def mock_telemetry_snapshot():
    snapshot=dashboard_data()
    snapshot["label"]="SYNTHETIC MOCK TELEMETRY"
    snapshot["source"]={
        **snapshot["source"],
        "kind":"local_mock",
        "provenance":"synthetic",
        "external_feed_status":"mock_only",
    }
    snapshot["feed"]={
        "id":"autonexus-local-mock",
        "schema_version":"1.0",
        "read_only":True,
    }
    return snapshot

# ---- living world (backend-driven) ----
import asyncio
from .world import World
WORLD=World()
async def _world_loop():
    while True:
        await asyncio.sleep(.1); WORLD.tick(.1)
@app.get("/world/state")
def w_state(): return WORLD.state()
@app.get("/world/federated")
def w_fed():
    from .world import federated_summary
    return federated_summary()
@app.post("/world/configure")
def world_configure(destination:str,part:str,required_qty:int|None=None,
                    source:str|None=None):
    result=WORLD.configure(destination,part,required_qty,source)
    if not result["ok"]:
        raise HTTPException(422,result["error"])
    return result
@app.post("/world/approve")
def world_approve(u=Depends(user)):
    result=WORLD.approve(u["role"])
    if not result["ok"]:
        raise HTTPException(409,result["error"])
    return result
@app.post("/world/reject")
def world_reject(u=Depends(user)):
    result=WORLD.reject(u["role"])
    if not result["ok"]:
        raise HTTPException(409,result["error"])
    return result
@app.post("/world/{cmd}")
def w_cmd(cmd:str):
    if cmd=="start":
        result=WORLD.start()
        if not result["ok"]:
            raise HTTPException(409,result["error"])
        return result
    if cmd=="block":
        result=WORLD.block()
        if not result["ok"]:
            raise HTTPException(409,result["error"])
        return result
    if cmd=="reset":
        WORLD.reset()
        return {"ok":True,"scenario":WORLD.scn}
    raise HTTPException(404,"unknown command")
@app.websocket("/ws/world")
async def ws_world(w:WebSocket):
    await w.accept()
    try:
        while True:
            await w.send_json(WORLD.state()); await asyncio.sleep(.1)
    except WebSocketDisconnect:
        return
@app.get("/world",response_class=HTMLResponse)
def world_page(): return (Path(_UI)/"world.html").read_text(encoding="utf-8")

# ---- unified platform capability and integration transparency ----
from . import platform as platform_status

@app.get("/platform/status")
def platform_status_endpoint():
    """Truthful engine, data provenance and provider configuration overview."""
    return platform_status.status()

@app.get("/platform/integrations")
def platform_integrations_endpoint():
    """Integration disposition for the uploaded reference repositories."""
    return platform_status.integrations()

# ---- shared operational core (database-backed engines, approvals, audit, events) ----
from .core import api_v1 as _core_v1
app.include_router(_core_v1.router)
@app.get("/command",response_class=HTMLResponse)
def command_page(): return (Path(_UI)/"command.html").read_text(encoding="utf-8")
