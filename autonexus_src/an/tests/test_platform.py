from autonexus import platform


def test_platform_status_is_explicit_about_prototype_data():
    result = platform.status()
    assert result["product"] == "AUTONEXUS AI 2.0"
    assert result["status"] == "prototype"
    assert result["data"]["csv_files"] >= 1
    assert result["data"]["source_type"] in {"synthetic", "imported", "operational"}
    assert result["providers"]["erpnext_connected"] is False


def test_integration_catalog_covers_uploaded_sources():
    result = platform.integrations()
    ids = {item["id"] for item in result["integrations"]}
    assert "flower" in ids
    assert "erpnext" in ids
    assert "optimap" in ids
