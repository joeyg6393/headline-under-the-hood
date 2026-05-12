from app.analyzer import ReportContext, analyze_report
from app.config import get_settings


def test_local_analysis_flags_payroll_quality_caveats(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()

    result = analyze_report(
        ReportContext(
            source="BLS",
            report_type="Nonfarm Payrolls",
            release_date="2026-05-08",
            headline="Payrolls jump by 150k, crushing the 65k estimate",
            report_text=(
                "Total nonfarm payroll employment increased by 150,000 in April. "
                "The prior two months were revised down by 57,000 in total. "
                "The number of persons employed part time for economic reasons increased by 42,000. "
                "Multiple jobholders also increased by 25,000 over the month. "
                "The household survey showed civilian employment was roughly flat."
            ),
        )
    )

    assert result.model_used == "local-heuristic-v0"
    assert result.score < 75
    assert any(component.label == "Multiple jobholders" for component in result.score_components)
    assert any(component.math == "reported month change = +25,000" for component in result.score_components)
    assert any(metric.key == "revision_adjusted_headline" for metric in result.metrics)
    assert any("25,000" in factor for factor in result.contradicting_factors)


def test_local_analysis_handles_percentage_macro_releases(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()

    result = analyze_report(
        ReportContext(
            source="BLS",
            report_type="Consumer Price Index",
            release_date="2026-05-12",
            headline="CPI heats up 0.4% month over month vs 0.3% expected",
            report_text=(
                "The Consumer Price Index increased 0.4 percent in April. "
                "Core CPI, excluding food and energy, rose 0.3 percent. "
                "Shelter costs increased 0.5 percent and energy prices increased 1.1 percent."
            ),
        )
    )

    assert result.model_used == "local-heuristic-v0"
    assert any(metric.key == "headline_release_read" for metric in result.metrics)
    assert any(metric.key == "consensus_percent_estimate" for metric in result.metrics)
    assert any(metric.key == "core_inflation" for metric in result.metrics)
    assert any(component.label == "Estimate surprise" for component in result.score_components)
    assert result.supporting_factors
