"""Truthful capability and integration status for AUTONEXUS.

This module deliberately distinguishes implemented local capabilities from
configured external providers and reference-only integrations. A configured
environment variable is not proof that a provider is reachable.
"""
import os
from pathlib import Path
from . import config

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

ENGINE_CATALOG = [
    {"id": "core", "name": "Shared Operational Core (/api/v1)", "mode": "local", "description": "Database-backed inventory ledger, forecasting, supplier ranking, routing, approvals, audit chain and event log; runs on the provenance-tagged dataset. See /api/v1/platform/provenance and /api/v1/platform/connectors."},
    {"id": "inventory", "name": "Stock Management", "mode": "local", "description": "CSV-backed inventory visibility and recovery planning."},
    {"id": "recovery", "name": "Find Parts for Urgent Jobs", "mode": "local", "description": "Deterministic shortage detection, graph search and transfer planning."},
    {"id": "agents", "name": "Agent Orchestration", "mode": "local_deterministic", "description": "Deterministic multi-step orchestration; not an LLM-powered autonomous agent."},
    {"id": "approvals", "name": "Human Approval", "mode": "local", "description": "Owner-authenticated approval checkpoints for protected operations."},
    {"id": "forecasting", "name": "Predict How Many Parts We Need", "mode": "synthetic_evaluation", "description": "Current evaluation pipeline uses generated demonstration data; operational forecasting is not yet enabled."},
    {"id": "routing", "name": "Delivery Routes", "mode": "local_graph", "description": "Routes are calculated from the included road-network dataset; external routing is not guaranteed."},
    {"id": "workshop", "name": "Workshop Scheduling", "mode": "local_simulation", "description": "Technician and service-bay planning from included sample data."},
    {"id": "cybershield", "name": "CyberShield", "mode": "sample_event_analysis", "description": "Analysis includes sample/simulated security events; this is not connected SIEM telemetry."},
    {"id": "digital_twin", "name": "Living World / Live Operations Map", "mode": "local_simulation", "description": "Three.js world reflects application simulation state, not physical IoT telemetry."},
    {"id": "documents", "name": "Document Intelligence", "mode": "local_extraction", "description": "Local extraction and retrieval capabilities; source coverage depends on uploaded documents."},
    {"id": "federated", "name": "Shared Learning Across Branches (demo)", "mode": "synthetic_or_local_demo", "description": "Demonstration workflow; real multi-dealership federated clients are not configured."},
    {"id": "data_import", "name": "Data Management", "mode": "csv_dataset", "description": "Current operational dataset loader reads the checked-in CSV files."},
    {"id": "erp", "name": "ERP Integration", "mode": "not_connected", "description": "No verified ERPNext connection is implemented in this build."},
]

INTEGRATION_CATALOG = [
    {"id": "shadcn_dashboard", "source": "shadcndashboard", "disposition": "design_reference", "status": "not_runtime_dependency", "reason": "Existing AUTONEXUS interface is retained; compatible patterns can be ported selectively."},
    {"id": "shadcn_admin", "source": "shadcn-admin", "disposition": "component_reference", "status": "not_runtime_dependency", "reason": "Avoid introducing a second application shell or duplicate component system."},
    {"id": "excel_import", "source": "react-excel-import", "disposition": "candidate", "status": "not_integrated", "reason": "Evaluate licensing, dependency compatibility and accessibility before selecting an import component."},
    {"id": "spreadsheet_import", "source": "react-spreadsheet-import", "disposition": "candidate_alternative", "status": "not_integrated", "reason": "Alternative to the Excel import candidate; do not ship both competing import workflows."},
    {"id": "rag_document_qa", "source": "rag-document-qa", "disposition": "retrieval_reference", "status": "not_integrated_as_dependency", "reason": "Existing AUTONEXUS local document capabilities remain canonical pending adapter and security review."},
    {"id": "local_rag_qa", "source": "local-rag-qa", "disposition": "offline_retrieval_reference", "status": "not_integrated_as_dependency", "reason": "Reuse compatible retrieval ideas without duplicating document stores."},
    {"id": "digital_twin_warehouse", "source": "3d-digital-twin-warehouse", "disposition": "3d_reference", "status": "not_integrated_as_dependency", "reason": "Existing Three.js Living World remains canonical; evaluate reusable scene components."},
    {"id": "ware_twin", "source": "WareTwin", "disposition": "digital_twin_reference", "status": "not_integrated_as_dependency", "reason": "Alternative twin stack; avoid maintaining two competing digital twin runtimes."},
    {"id": "flower", "source": "Flower", "disposition": "federated_learning_candidate", "status": "not_connected", "reason": "Requires authenticated participating clients, transport security and model governance."},
    {"id": "supply_chain_forecasting", "source": "supply-chain-forecasting", "disposition": "algorithm_reference", "status": "not_integrated_as_runtime", "reason": "Forecasting concepts require validation on dealership-specific historical demand."},
    {"id": "demandforecast", "source": "demandforecast", "disposition": "algorithm_reference", "status": "not_integrated_as_runtime", "reason": "Candidate intermittent-demand methods require data and backtesting before production use."},
    {"id": "mini_siem", "source": "mini-siem-dashboard", "disposition": "security_reference", "status": "not_connected", "reason": "No external log collector or production SIEM feed is configured."},
    {"id": "langgraph_hitl", "source": "langgraph-hil-approval", "disposition": "workflow_reference", "status": "not_runtime_dependency", "reason": "Existing owner approval flow is retained; LangGraph adoption needs persistence and concurrency validation."},
    {"id": "langgraph_agents", "source": "langgraph-multi-agent", "disposition": "orchestration_reference", "status": "not_runtime_dependency", "reason": "Existing deterministic orchestrator remains canonical until agent tools and checkpoints are production-ready."},
    {"id": "optimap", "source": "optimap-route-optimizer", "disposition": "routing_reference", "status": "not_integrated_as_runtime", "reason": "Current route engine uses local graph data; real routing provider integration needs credentials and live validation."},
    {"id": "erpnext", "source": "erpnext", "disposition": "external_erp_candidate", "status": "not_connected", "reason": "Requires a configured ERPNext instance, credentials, field mapping and synchronization tests."},
]

def _csv_status():
    files = sorted(DATA.glob("*.csv"))
    newest = max((f.stat().st_mtime for f in files), default=None)
    return {
        "source_type": config.get("DATA_PROVENANCE", "synthetic").strip().lower(),
        "source_label": "SYNTHETIC SAMPLE DATA" if config.get("DATA_PROVENANCE", "synthetic").strip().lower() == "synthetic" else "DECLARED OPERATIONAL DATA — NOT INDEPENDENTLY VERIFIED",
        "csv_files": len(files),
        "newest_file_mtime": newest,
        "refresh_mode": "file-backed on request / in-memory simulation",
    }

def status():
    """Return capability metadata without exposing secrets or claiming connectivity."""
    cfg = config.status()
    return {
        "product": "AUTONEXUS AI 2.0",
        "status": "prototype",
        "data": _csv_status(),
        "engines": [
            {**e, "configured": (
                True if e["mode"] in {"local", "local_deterministic", "local_graph", "local_simulation", "sample_event_analysis", "local_extraction", "csv_dataset"}
                else False
            )} for e in ENGINE_CATALOG
        ],
        "providers": {
            "llm_key_present": bool(cfg.get("LLM")),
            "routing_configuration": cfg.get("routing"),
            "telemetry_url_configured": bool(config.get("TELEMETRY_URL")),
            "erpnext_connected": False,
            "flower_clients_connected": False,
            "external_siEM_connected": False,
        },
        "important_note": "Configuration presence does not prove provider reachability. Synthetic, simulated and sample-derived outputs remain explicitly identified.",
    }

def integrations():
    return {"integrations": INTEGRATION_CATALOG, "count": len(INTEGRATION_CATALOG)}
