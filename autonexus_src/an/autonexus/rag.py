from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
class RAG:
    """TF-IDF retrieval with role-based access filtering. (pgvector/Chroma not used.)"""
    def __init__(s,docs): s.d=docs; s.v=TfidfVectorizer().fit([x["text"] for x in docs]); s.m=s.v.transform([x["text"] for x in docs])
    def query(s,q,role,k=2):
        sc=cosine_similarity(s.v.transform([q]),s.m)[0]; out=[]
        for i in sc.argsort()[::-1]:
            d=s.d[i]
            if role in d["roles"] or role=="admin": out.append({"id":d["id"],"score":float(sc[i]),"text":d["text"],"untrusted":True})
            if len(out)==k: break
        return out
DOCS=[{"id":"POL-1","text":"Purchases above 5000 require manager approval. Restricted suppliers are prohibited.","roles":["procurement","admin","auditor"]},
      {"id":"MAN-7","text":"Brake pad replacement requires rotor inspection and torque spec.","roles":["technician","admin","procurement"]},
      {"id":"SEC-2","text":"Security incident playbook: lock account and hold transactions.","roles":["admin","security"]}]
class Graph:
    def __init__(s): s.e=[]
    def add(s,a,rel,b): s.e.append((a,rel,b))
    def neighbors(s,n): return [(r,b) for a,r,b in s.e if a==n]+[(r,a) for a,r,b in s.e if b==n]
    def dependency(s,vendor): return sorted({b for a,r,b in s.e if a==vendor and r=="supplies"})
