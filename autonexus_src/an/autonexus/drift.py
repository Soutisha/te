import numpy as np
def psi(ref,cur,bins=10):
    e=np.histogram_bin_edges(ref,bins); a=np.histogram(ref,e)[0]/len(ref)+1e-6; b=np.histogram(cur,e)[0]/len(cur)+1e-6
    return float(((b-a)*np.log(b/a)).sum())
def status(v): return "stable" if v<.1 else "moderate" if v<.25 else "significant drift"
