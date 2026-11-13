import random
NODES={"DealerA":(0,0),"DealerB":(30,10),"DealerC":(20,40),"DealerD":(60,30),"DealerE":(50,-20),"WH1":(35,-5),"WH2":(10,25)}
def edges(nodes=NODES):
    import math
    pairs=[("DealerA","DealerB"),("DealerA","WH2"),("DealerA","WH1"),("DealerB","WH1"),("DealerB","DealerD"),("DealerC","WH2"),("DealerC","DealerB"),("DealerD","DealerE"),("WH1","DealerE"),("DealerC","DealerD")]
    return {(a,b):round(math.dist(nodes[a],nodes[b])*1.2,2) for a,b in pairs}
def seed(rs=42):
    r=random.Random(rs)
    sites=[k for k in NODES]
    parts=[{"id":f"P{i:03d}","name":n,"fits":["sedan","suv"] if i%2 else ["suv"]} for i,n in enumerate(["BrakePad"]*1+["Filter","Rotor","Battery","Wiper"]*30)]
    parts[0]["name"]="BrakePad"; parts[0]["fits"]=["sedan","suv"]
    stock={s:{p["id"]:r.randint(0,30) for p in parts} for s in sites}
    stock["DealerA"]["P000"]=2; stock["DealerB"]["P000"]=25; stock["DealerC"]["P000"]=18; stock["WH1"]["P000"]=40
    vendors={"V1":{"name":"AutoSupply","reliability":.93,"restricted":False,"limit":5000},
             "V2":{"name":"FastParts","reliability":.71,"restricted":True,"limit":2000},
             "V3":{"name":"PrimeOEM","reliability":.88,"restricted":False,"limit":8000}}
    ros=[{"id":f"RO{i:04d}","dealer":r.choice(sites[:5]),"part":"P000" if i<5 else r.choice(parts)["id"],"qty":2,"vehicle":"sedan","status":"open","priority":r.randint(1,5)} for i in range(200)]
    for ro in ros[:5]: ro["dealer"]="DealerA"
    return {"parts":parts,"stock":stock,"vendors":vendors,"ros":ros,"closed":set(),"po":{"PO-1":{"vendor":"V1","lines":{"P000":80}}}}
