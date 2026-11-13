import random, math, itertools, time, statistics
from .algorithms import hungarian
from .data import NODES
def ga_order(stops,start,iters=200,seed=1):
    """Genetic algorithm for multi-stop ordering (min tour length)."""
    r=random.Random(seed); P={s:NODES[s] for s in stops+[start]}
    def L(o): 
        pts=[start]+o; return sum(math.dist(P[a],P[b]) for a,b in zip(pts,pts[1:]))
    pop=[r.sample(stops,len(stops)) for _ in range(30)]
    for _ in range(iters):
        pop.sort(key=L); nxt=pop[:6]
        while len(nxt)<30:
            a,b=r.sample(pop[:15],2); i,j=sorted(r.sample(range(len(a)),2)) if len(a)>1 else (0,0)
            c=a[i:j]+[x for x in b if x not in a[i:j]]
            if r.random()<.2 and len(c)>1: x,y=r.sample(range(len(c)),2); c[x],c[y]=c[y],c[x]
            nxt.append(c)
        pop=nxt
    pop.sort(key=L); return pop[0],L(pop[0])
def route_baseline(stops,start): 
    pts=[start]+stops; return sum(math.dist(NODES[a],NODES[b]) for a,b in zip(pts,pts[1:]))
def vrp(depot,stops,demand,cap):
    """Capacity-constrained routing. Uses OR-Tools if installed (untested here), else nearest-neighbour + capacity split."""
    routes=[];cur=[];load=0;left=list(stops);pos=depot
    while left:
        n=min(left,key=lambda s:math.dist(NODES[pos],NODES[s]))
        if load+demand[n]>cap: routes.append(cur);cur=[];load=0;pos=depot;continue
        cur.append(n);load+=demand[n];left.remove(n);pos=n
    if cur: routes.append(cur)
    return routes
def assign(techs,jobs):
    """techs: {name:set(skills)}, jobs:[(id,skill,priority)]. Hungarian; skill mismatch cost 1000; unfilled -> dummy."""
    T=list(techs); n=max(len(T),len(jobs)); BIG=1000
    c=[[0]*n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i<len(T) and j<len(jobs): c[i][j]=(0 if jobs[j][1] in techs[T[i]] else BIG)+(6-jobs[j][2])
    a,_=hungarian(c); res={}
    for i,j in enumerate(a):
        if i<len(T) and j<len(jobs) and jobs[j][1] in techs[T[i]]: res[jobs[j][0]]=T[i]
    return res
def monte_carlo(base_hours,delay_mean,runs=500,seed=3):
    r=random.Random(seed); s=sorted(base_hours+r.expovariate(1/delay_mean) for _ in range(runs))
    return {"mean":statistics.mean(s),"p50":s[runs//2],"p95":s[int(runs*.95)]}

def vrp_ortools(depot,stops,demand,cap,vehicles=3):
    """OR-Tools CVRP (integer-scaled distances)."""
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    nodes=[depot]+stops; n=len(nodes); D=[[int(math.dist(NODES[a],NODES[b])*100) for b in nodes] for a in nodes]
    m=pywrapcp.RoutingIndexManager(n,vehicles,0); R=pywrapcp.RoutingModel(m)
    t=R.RegisterTransitCallback(lambda i,j:D[m.IndexToNode(i)][m.IndexToNode(j)]); R.SetArcCostEvaluatorOfAllVehicles(t)
    dm=R.RegisterUnaryTransitCallback(lambda i:0 if m.IndexToNode(i)==0 else demand[nodes[m.IndexToNode(i)]])
    R.AddDimensionWithVehicleCapacity(dm,0,[cap]*vehicles,True,"cap")
    p=pywrapcp.DefaultRoutingSearchParameters(); p.first_solution_strategy=routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    s=R.SolveWithParameters(p)
    if not s: return None
    out=[]
    for v in range(vehicles):
        i=R.Start(v); r=[]
        while not R.IsEnd(i):
            nd=m.IndexToNode(i)
            if nd: r.append(nodes[nd])
            i=s.Value(R.NextVar(i))
        if r: out.append(r)
    return out
