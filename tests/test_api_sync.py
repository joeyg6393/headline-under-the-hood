from fastapi.testclient import TestClient


def test_submit_report_without_temporal_uses_local_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_TEMPORAL", "false")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("OPENAI_API_KEY", "")

    from app.config import get_settings

    get_settings.cache_clear()

    from app.main import app

    with TestClient(app) as client:
        response = client.post(
            "/api/reports",
            json={
                "source": "BLS",
                "report_type": "Nonfarm Payrolls",
                "release_date": "2026-05-08",
                "headline": "Payrolls jump by 150k, crushing the 65k estimate",
                "report_text": (
                    "Total nonfarm payroll employment increased by 150,000 in April. "
                    "The previous months were revised down by 57,000 in total. "
                    "The number of persons employed part time for economic reasons increased by 42,000. "
                    "Multiple jobholders also increased by 25,000."
                ),
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "complete"
    assert body["analysis"]["model_used"] == "local-heuristic-v0"
    assert body["analysis"]["contradicting_factors"]
    assert body["analysis"]["score_components"]
    assert any(metric["key"] == "multiple_jobholders" for metric in body["analysis"]["metrics"])


def test_demo_set_seeds_major_monthly_releases(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_TEMPORAL", "false")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("OPENAI_API_KEY", "")

    from app.config import get_settings

    get_settings.cache_clear()

    from app.main import app

    with TestClient(app) as client:
        response = client.post("/api/reports/demo-set")
        second_response = client.post("/api/reports/demo-set")
        list_response = client.get("/api/reports")
        page_response = client.get("/reports/1")

    assert response.status_code == 200
    assert second_response.status_code == 200
    assert list_response.status_code == 200
    assert page_response.status_code == 200
    assert "Full Analysis" in page_response.text
    body = response.json()
    report_types = {report["report_type"] for report in body}
    assert {"PCE Price Index", "Consumer Price Index", "Producer Price Index", "Nonfarm Payrolls", "ADP Employment"}.issubset(report_types)
    assert len(report_types) >= 10
    assert {report["release_date"][:7] for report in body} >= {"2026-03", "2026-04", "2026-05"}
    assert all(report["status"] == "complete" for report in body)
    assert len(list_response.json()) == len(body)
