"""Baseline vs integrated, identical scenario inputs. SYNTHETIC SIMULATION, not real-world validation."""
import random, statistics
from .data import NODES
from .algorithms import graph, astar
def one(seed,blocked=()):
    r=random.Random(seed); g=graph(blocked); sites=["DealerB","DealerC","WH1"]; r.shuffle(sites)
    speed=40; proc_h=r.uniform(2,6)
    def hrs(s): c=astar(g,s,"DealerA")["cost"]; return c/speed*60 if c!=float("inf") else None
    # baseline: manual -> calls sites in arbitrary order, 2h per call until stock found (first feasible), emergency order cost
    base=0
    for s in sites:
        base+=r.uniform(1,3); h=hrs(s)
        if h is not None: base+=h; bc=astar(g,s,"DealerA")["cost"]*1.5; break
    # integrated: parallel search, best route
    best=min((hrs(s),s) for s in sites if hrs(s) is not None); ours=.25+best[0]; oc=astar(g,best[1],"DealerA")["cost"]
    return base,ours,bc,oc
def compare(runs=30):
    R=[one(i) for i in range(runs)]; col=lambda k:[x[k] for x in R]
    f=lambda a:{"mean":round(statistics.mean(a),2),"sd":round(statistics.pstdev(a),2)}
    b,o,bc,oc=map(col,range(4))
    return {"label":"SYNTHETIC SIMULATION","runs":runs,"resolution_hours":{"baseline":f(b),"autonexus":f(o),"improvement_pct":round((statistics.mean(b)-statistics.mean(o))/statistics.mean(b)*100,1)},
            "route_cost":{"baseline":f(bc),"autonexus":f(oc),"improvement_pct":round((statistics.mean(bc)-statistics.mean(oc))/statistics.mean(bc)*100,1)},
            "formula":"(baseline-autonexus)/baseline*100","limitations":["Synthetic inputs","Baseline modelled, not measured from real dealers"]}
