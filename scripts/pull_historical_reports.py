from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta
from html import unescape
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "historical-reports"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) HeadlineUnderTheHood/0.1"


@dataclass(frozen=True)
class PullResult:
    report_type: str
    source: str
    status: str
    records: int = 0
    files: list[str] | None = None
    note: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "report_type": self.report_type,
            "source": self.source,
            "status": self.status,
            "records": self.records,
            "files": self.files or [],
            "note": self.note,
        }


BLS_SERIES = {
    "nonfarm-payrolls": {
        "report_type": "Nonfarm Payrolls",
        "series_id": "CES0000000001",
        "source": "BLS",
        "unit": "thousands of jobs",
        "archive_url": "https://www.bls.gov/bls/news-release/empsit.htm",
        "archive_prefix": "empsit",
    },
    "consumer-price-index": {
        "report_type": "Consumer Price Index",
        "series_id": "CUSR0000SA0",
        "source": "BLS",
        "unit": "index",
        "archive_url": "https://www.bls.gov/bls/news-release/cpi.htm",
        "archive_prefix": "cpi",
    },
    "producer-price-index": {
        "report_type": "Producer Price Index",
        "series_id": "WPUFD4",
        "source": "BLS",
        "unit": "index",
        "archive_url": "https://www.bls.gov/bls/news-release/ppi.htm",
        "archive_prefix": "ppi",
    },
    "jolts": {
        "report_type": "JOLTS",
        "series_id": "JTS000000000000000JOL",
        "source": "BLS",
        "unit": "thousands",
        "archive_url": "https://www.bls.gov/bls/news-release/jolts.htm",
        "archive_prefix": "jolts",
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Pull official historical economic reports and data.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--monthly-count", type=int, default=12)
    parser.add_argument("--quarterly-count", type=int, default=4)
    args = parser.parse_args()

    output = args.output
    output.mkdir(parents=True, exist_ok=True)

    results: list[PullResult] = []
    for slug, config in BLS_SERIES.items():
        results.append(run_pull(lambda: pull_bls_series(slug, config, output, args.monthly_count), config["report_type"], config["source"]))
        results.append(run_pull(lambda: pull_bls_archives(slug, config, output, args.monthly_count), config["report_type"], config["source"]))

    results.append(run_pull(lambda: pull_census_retail_sales(output, args.monthly_count), "Retail Sales", "Census"))
    results.append(run_pull(lambda: pull_dol_claims(output), "Initial Jobless Claims", "DOL"))
    results.append(run_pull(lambda: pull_adp_reports(output, args.monthly_count), "ADP Employment", "ADP"))
    for bea_pull in pull_bea_reports(output, args.monthly_count, args.quarterly_count):
        results.append(bea_pull)
    results.append(
        PullResult(
            report_type="ISM Manufacturing PMI",
            source="ISM",
            status="skipped",
            note="ISM report pages are protected by CAPTCHA in this environment; no bypass attempted.",
        )
    )

    manifest = {
        "generated_at": date.today().isoformat(),
        "output_root": str(output.relative_to(ROOT) if output.is_relative_to(ROOT) else output).replace("\\", "/"),
        "monthly_target_count": args.monthly_count,
        "quarterly_target_count": args.quarterly_count,
        "results": [result.as_dict() for result in results],
    }
    write_json(output / "manifest.json", manifest)
    print(json.dumps(manifest, indent=2))
    return 0 if any(result.status == "ok" for result in results) else 1


def run_pull(fn, report_type: str, source: str) -> PullResult:
    try:
        return fn()
    except Exception as exc:
        return PullResult(report_type, source, "error", note=f"{exc.__class__.__name__}: {exc}")


def pull_bls_series(slug: str, config: dict[str, str], output: Path, count: int) -> PullResult:
    current_year = date.today().year
    years = [str(current_year - 1), str(current_year)]
    url = (
        f"https://api.bls.gov/publicAPI/v2/timeseries/data/{config['series_id']}"
        f"?startyear={years[0]}&endyear={years[-1]}"
    )
    folder = output / "bls" / slug / "data"
    folder.mkdir(parents=True, exist_ok=True)
    raw = fetch_json(url)
    write_json(folder / "raw-series.json", raw)

    series = raw.get("Results", {}).get("series", [{}])[0].get("data", [])
    rows = []
    for item in series:
        period = item.get("period", "")
        if not re.fullmatch(r"M\d{2}", period):
            continue
        rows.append(
            {
                "source": config["source"],
                "report_type": config["report_type"],
                "series_id": config["series_id"],
                "reference_month": f"{item['year']}-{period[1:]}",
                "period_name": item.get("periodName"),
                "value": item.get("value"),
                "unit": config["unit"],
                "latest": item.get("latest") == "true",
            }
        )
    rows = sorted(rows, key=lambda row: row["reference_month"], reverse=True)[:count]
    write_json(folder / "latest-12-months.json", rows)
    write_csv(folder / "latest-12-months.csv", rows)
    return PullResult(config["report_type"], config["source"], "ok", len(rows), rels([folder / "raw-series.json", folder / "latest-12-months.json", folder / "latest-12-months.csv"]))


def pull_bls_archives(slug: str, config: dict[str, str], output: Path, count: int) -> PullResult:
    folder = output / "bls" / slug / "reports"
    folder.mkdir(parents=True, exist_ok=True)
    page = fetch_text(config["archive_url"])
    (folder / "archive-index.html").write_text(page, encoding="utf-8")
    links = bls_archive_links(page, config["archive_prefix"])[:count]
    files = [folder / "archive-index.html"]
    records = []
    for link in links:
        url = urllib.parse.urljoin(config["archive_url"], link)
        name = Path(urllib.parse.urlparse(url).path).name
        html_path = folder / name
        text_path = folder / f"{html_path.stem}.txt"
        html = fetch_text(url)
        html_path.write_text(html, encoding="utf-8")
        text_path.write_text(html_to_text(html), encoding="utf-8")
        files.extend([html_path, text_path])
        records.append({"url": url, "html_file": rel(html_path), "text_file": rel(text_path)})
    write_json(folder / "downloaded-reports.json", records)
    files.append(folder / "downloaded-reports.json")
    return PullResult(config["report_type"], config["source"], "ok", len(records), rels(files))


def pull_census_retail_sales(output: Path, count: int) -> PullResult:
    folder = output / "census" / "retail-sales" / "data"
    folder.mkdir(parents=True, exist_ok=True)
    current_year = date.today().year
    rows: list[dict[str, Any]] = []
    raw_files = []
    for year in [current_year - 1, current_year]:
        url = (
            "https://api.census.gov/data/timeseries/eits/marts"
            "?get=data_type_code,seasonally_adj,category_code,cell_value,error_data"
            f"&time={year}&data_type_code=SM&seasonally_adj=yes&category_code=44X72"
        )
        data = fetch_json_array(url)
        raw_path = folder / f"raw-{year}.json"
        write_json(raw_path, data)
        raw_files.append(raw_path)
        header, values = data[0], data[1:]
        for value in values:
            item = dict(zip(header, value))
            rows.append(
                {
                    "source": "Census",
                    "report_type": "Retail Sales",
                    "reference_month": item["time"],
                    "value": item["cell_value"],
                    "unit": "millions of dollars",
                    "category_code": item["category_code"],
                    "seasonally_adjusted": item["seasonally_adj"] == "yes",
                }
            )
    rows = sorted(rows, key=lambda row: row["reference_month"], reverse=True)[:count]
    write_json(folder / "latest-12-months.json", rows)
    write_csv(folder / "latest-12-months.csv", rows)
    return PullResult("Retail Sales", "Census", "ok", len(rows), rels(raw_files + [folder / "latest-12-months.json", folder / "latest-12-months.csv"]))


def pull_dol_claims(output: Path) -> PullResult:
    folder = output / "dol" / "initial-jobless-claims" / "data"
    folder.mkdir(parents=True, exist_ok=True)
    current_year = date.today().year
    payload = urllib.parse.urlencode(
        {
            "level": "us",
            "strtdate": str(current_year - 1),
            "enddate": str(current_year),
            "filetype": "xls",
            "submit": "Submit",
        }
    ).encode("utf-8")
    url = "https://oui.doleta.gov/unemploy/wkclaims/report.asp"
    raw = fetch_bytes(url, data=payload, content_type="application/x-www-form-urlencoded")
    path = folder / f"weekly-claims-{current_year - 1}-{current_year}.xls"
    path.write_bytes(raw)
    return PullResult("Initial Jobless Claims", "DOL", "ok", 1, [rel(path)], "DOL publishes claims weekly; this pull stores the last two calendar years for roughly 12 months of weekly history.")


def pull_adp_reports(output: Path, count: int) -> PullResult:
    folder = output / "adp" / "adp-employment" / "reports"
    folder.mkdir(parents=True, exist_ok=True)
    files = []
    records = []
    for report_month in completed_months(count):
        release_month = add_months(report_month, 1)
        url = find_adp_pdf_url(report_month, release_month)
        if not url:
            records.append({"reference_month": month_key(report_month), "status": "missing"})
            continue
        pdf_path = folder / f"adp-national-employment-report-{month_key(report_month)}.pdf"
        pdf_path.write_bytes(fetch_bytes(url))
        files.append(pdf_path)
        records.append({"reference_month": month_key(report_month), "url": url, "file": rel(pdf_path), "status": "ok"})
    write_json(folder / "downloaded-reports.json", records)
    files.append(folder / "downloaded-reports.json")
    ok_count = sum(1 for record in records if record["status"] == "ok")
    status = "ok" if ok_count else "skipped"
    return PullResult("ADP Employment", "ADP", status, ok_count, rels(files), "ADP URLs are probed from their public static PDF pattern.")


def pull_bea_reports(output: Path, monthly_count: int, quarterly_count: int) -> list[PullResult]:
    results = [
        pull_bea_pce_reports(output, monthly_count),
        pull_bea_gdp_reports(output, quarterly_count),
    ]
    api_key = os.getenv("BEA_API_KEY")
    if not api_key:
        note = "BEA requires a valid API key. Set BEA_API_KEY and rerun this script to pull PCE and GDP tables from BEA."
        results.extend(
            [
                PullResult("PCE Price Index data table", "BEA", "skipped", note=note),
                PullResult("Gross Domestic Product data table", "BEA", "skipped", note=note),
            ]
        )
        return results
    results.extend(
        [
            pull_bea_table("pce-price-index", "PCE Price Index data table", "T20804", "M", monthly_count, output, api_key),
            pull_bea_table("gross-domestic-product", "Gross Domestic Product data table", "T10101", "Q", quarterly_count, output, api_key),
        ]
    )
    return results


def pull_bea_pce_reports(output: Path, count: int) -> PullResult:
    folder = output / "bea" / "pce-price-index" / "reports"
    folder.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    records = []
    first_of_month = date.today().replace(day=1)
    for offset in range(1, 20):
        if len(records) >= count:
            break
        report_month = add_months(first_of_month, -offset)
        month_name = report_month.strftime("%B").lower()
        release_year = add_months(report_month, 1).year
        url = first_existing_url(
            [
                f"https://www.bea.gov/news/{release_year}/personal-income-and-outlays-{month_name}-{report_month.year}",
                f"https://www.bea.gov/news/{report_month.year}/personal-income-and-outlays-{month_name}-{report_month.year}",
            ]
        )
        if not url_exists(url):
            continue
        html = fetch_text(url)
        stem = f"personal-income-and-outlays-{month_key(report_month)}"
        html_path = folder / f"{stem}.html"
        text_path = folder / f"{stem}.txt"
        html_path.write_text(html, encoding="utf-8")
        text_path.write_text(html_to_text(html), encoding="utf-8")
        files.extend([html_path, text_path])
        pdfs = download_linked_pdfs(html, url, folder, stem)
        files.extend(pdfs)
        records.append({"reference_month": month_key(report_month), "url": url, "html_file": rel(html_path), "text_file": rel(text_path), "pdf_files": rels(pdfs)})
    write_json(folder / "downloaded-reports.json", records)
    files.append(folder / "downloaded-reports.json")
    return PullResult("PCE Price Index", "BEA", "ok" if records else "skipped", len(records), rels(files))


def pull_bea_gdp_reports(output: Path, count: int) -> PullResult:
    folder = output / "bea" / "gross-domestic-product" / "reports"
    folder.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    records = []
    urls = bea_gdp_links_from_index(count)
    for index, url in enumerate(urls, start=1):
        html = fetch_text(url)
        stem = f"gdp-report-{index:02d}-{Path(urllib.parse.urlparse(url).path).name}"
        html_path = folder / f"{stem}.html"
        text_path = folder / f"{stem}.txt"
        html_path.write_text(html, encoding="utf-8")
        text_path.write_text(html_to_text(html), encoding="utf-8")
        files.extend([html_path, text_path])
        pdfs = download_linked_pdfs(html, url, folder, stem)
        files.extend(pdfs)
        records.append({"url": url, "html_file": rel(html_path), "text_file": rel(text_path), "pdf_files": rels(pdfs)})
    write_json(folder / "downloaded-reports.json", records)
    files.append(folder / "downloaded-reports.json")
    return PullResult("Gross Domestic Product", "BEA", "ok" if records else "skipped", len(records), rels(files))


def bea_gdp_links_from_index(count: int) -> list[str]:
    links: list[str] = []
    for page_number in range(4):
        suffix = "" if page_number == 0 else f"?page={page_number}"
        index_url = f"https://www.bea.gov/taxonomy/term/451{suffix}"
        html = fetch_text(index_url)
        for href in re.findall(r'href=["\']((?:https?://[^"\']+)?/news/\d{4}/[^"\']+)["\']', html):
            url = urllib.parse.urljoin(index_url, href)
            slug = Path(urllib.parse.urlparse(url).path).name.lower()
            if "gdp" not in slug and "gross-domestic-product" not in slug:
                continue
            if "quarter" not in slug:
                continue
            if url not in links:
                links.append(url)
            if len(links) >= count:
                return links
    return links


def pull_bea_table(slug: str, report_type: str, table: str, frequency: str, count: int, output: Path, api_key: str) -> PullResult:
    folder = output / "bea" / slug / "data"
    folder.mkdir(parents=True, exist_ok=True)
    year = date.today().year
    url = (
        "https://apps.bea.gov/api/data"
        f"?UserID={urllib.parse.quote(api_key)}&method=GetData&datasetname=NIPA"
        f"&TableName={table}&Frequency={frequency}&Year=X&ResultFormat=JSON"
    )
    raw = fetch_json(url)
    write_json(folder / "raw-table.json", raw)
    data = raw.get("BEAAPI", {}).get("Results", {}).get("Data", [])
    rows = [
        row
        for row in data
        if row.get("LineNumber") == "1" and re.search(r"\d", row.get("TimePeriod", ""))
    ]
    rows = sorted(rows, key=lambda row: row["TimePeriod"], reverse=True)[:count]
    write_json(folder / f"latest-{count}.json", rows)
    write_csv(folder / f"latest-{count}.csv", rows)
    return PullResult(report_type, "BEA", "ok", len(rows), rels([folder / "raw-table.json", folder / f"latest-{count}.json", folder / f"latest-{count}.csv"]))


def bls_archive_links(html: str, prefix: str) -> list[str]:
    matches = re.findall(r'href=["\']([^"\']*/news\.release/archives/' + re.escape(prefix) + r'_\d{8}\.htm)["\']', html)
    seen = set()
    links = []
    for match in matches:
        if match in seen:
            continue
        seen.add(match)
        links.append(match)
    return links


def find_adp_pdf_url(report_month: date, release_month: date) -> str | None:
    year_month = f"{report_month.year}_{report_month.month:02d}"
    for day in range(1, 11):
        release_date = date(release_month.year, release_month.month, day)
        release_key = release_date.strftime("%Y%m%d")
        quoted_name = f"ADP_NATIONAL_EMPLOYMENT_REPORT_Press_Release_{year_month}%20FINAL.pdf"
        url = f"https://adp-ri-nrip-static.adp.com/artifacts/us_ner/{release_key}/{quoted_name}"
        if url_exists(url):
            return url
    return None


def completed_months(count: int) -> list[date]:
    first_of_this_month = date.today().replace(day=1)
    latest = add_months(first_of_this_month, -1)
    return [add_months(latest, -offset) for offset in range(count)]


def latest_completed_quarter() -> tuple[int, int]:
    today = date.today()
    current_quarter = (today.month - 1) // 3 + 1
    return add_quarters(today.year, current_quarter, -1)


def add_quarters(year: int, quarter: int, quarters: int) -> tuple[int, int]:
    quarter_index = year * 4 + quarter - 1 + quarters
    return quarter_index // 4, quarter_index % 4 + 1


def add_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    return date(month_index // 12, month_index % 12 + 1, 1)


def month_key(value: date) -> str:
    return f"{value.year}-{value.month:02d}"


def fetch_json(url: str) -> dict[str, Any]:
    return json.loads(fetch_text(url))


def fetch_json_array(url: str) -> list[list[str]]:
    return json.loads(fetch_text(url))


def fetch_text(url: str) -> str:
    return fetch_bytes(url).decode("utf-8", errors="replace")


def fetch_bytes(url: str, data: bytes | None = None, content_type: str | None = None) -> bytes:
    headers = {"User-Agent": USER_AGENT}
    if content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


def url_exists(url: str) -> bool:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="HEAD")
        with urllib.request.urlopen(request, timeout=12) as response:
            return response.status == 200
    except Exception:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=12) as response:
                return response.status == 200
        except Exception:
            return False


def first_existing_url(urls: list[str]) -> str:
    for url in urls:
        if url_exists(url):
            return url
    return urls[0]


def download_linked_pdfs(html: str, base_url: str, folder: Path, stem: str) -> list[Path]:
    pdf_links = re.findall(r'href=["\']([^"\']+\.pdf)["\']', html, flags=re.IGNORECASE)
    files = []
    for index, link in enumerate(dict.fromkeys(pdf_links), start=1):
        url = urllib.parse.urljoin(base_url, link)
        try:
            path = folder / f"{stem}-{index}.pdf"
            path.write_bytes(fetch_bytes(url))
            files.append(path)
        except Exception:
            continue
    return files


def html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    html = unescape(html)
    return re.sub(r"\s+", " ", html).strip()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def rels(paths: list[Path]) -> list[str]:
    return [rel(path) for path in paths]


if __name__ == "__main__":
    sys.exit(main())
