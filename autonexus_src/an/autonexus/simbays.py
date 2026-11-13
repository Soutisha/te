import simpy, random, statistics
def run(bays,jobs=40,seed=1,hours=10):
    r=random.Random(seed); env=simpy.Environment(); res=simpy.Resource(env,bays); busy=[0]; waits=[]
    def job(arr,dur):
        yield env.timeout(arr); t=env.now
        with res.request() as q:
            yield q; waits.append(env.now-t); yield env.timeout(dur); busy[0]+=dur
    for _ in range(jobs): env.process(job(r.uniform(0,hours),r.uniform(.5,2.5)))
    env.run(); T=env.now
    return {"bays":bays,"mean_wait_h":statistics.mean(waits),"utilisation_pct":busy[0]/(bays*T)*100,"makespan_h":T}
