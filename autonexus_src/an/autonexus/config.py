import os
def load_env(path=".env"):
    if os.path.exists(path):
        for l in open(path):
            l=l.strip()
            if l and not l.startswith("#") and "=" in l:
                k,v=l.split("=",1); v=v.split(" #")[0].split("\t#")[0].strip()
                if v: os.environ.setdefault(k.strip(),v)
load_env()
def get(k,d=""): return os.environ.get(k,d)
def status():
    """Report configuration without exposing credentials or implying unused adapters work."""
    database_url=get("AUTONEXUS_DB_URL", "sqlite:///autonexus_core.db")
    offline=get("OFFLINE_MODE","1")=="1"
    osrm_configured=bool(get("OSRM_URL")) and not offline
    return {
        "LLM":"not_implemented",
        "routing":"osrm" if osrm_configured else "offline_graph",
        "osrm_endpoint_configured":osrm_configured,
        "database":"postgresql" if database_url.startswith(("postgresql://", "postgresql+")) else "sqlite",
        "offline_mode":offline,
        "owner_auth_configured":bool(get("OWNER_EMAIL") and get("OWNER_PASSWORD_HASH")),
        "telemetry_source":"csv_directory",
        "external_telemetry_adapter":"external" if get("TELEMETRY_URL") else "synthetic_feed",
    }
