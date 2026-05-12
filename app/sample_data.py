from __future__ import annotations

from app.schemas import ReportCreate


MAJOR_RELEASE_SAMPLES: list[ReportCreate] = [
    ReportCreate(
        source="BLS",
        report_type="Nonfarm Payrolls",
        release_date="2026-05-08",
        headline="Payrolls jump by 150k, crushing the 65k estimate",
        report_text=(
            "Total nonfarm payroll employment increased by 150,000 in April. "
            "The change in total nonfarm payroll employment for February was revised down by 35,000 "
            "and the change for March was revised down by 22,000. "
            "The number of persons employed part time for economic reasons increased by 42,000. "
            "Multiple jobholders also increased by 25,000 over the month. "
            "Government employment increased by 38,000. "
            "The labor force participation rate was little changed, and the household survey showed "
            "civilian employment was roughly flat."
        ),
    ),
    ReportCreate(
        source="ADP",
        report_type="ADP Employment",
        release_date="2026-05-06",
        headline="ADP private payrolls rise 105k vs 130k expected",
        report_text=(
            "Private employers added 105,000 jobs in April. "
            "Small businesses shed 12,000 jobs while service-providing firms added 91,000. "
            "Annual pay was up 4.6 percent for job stayers, a slower pace than the prior month."
        ),
    ),
    ReportCreate(
        source="BLS",
        report_type="Consumer Price Index",
        release_date="2026-05-12",
        headline="CPI heats up 0.4% month over month vs 0.3% expected",
        report_text=(
            "The Consumer Price Index increased 0.4 percent in April after rising 0.2 percent in March. "
            "Over the last 12 months, the all items index increased 3.4 percent. "
            "Core CPI, excluding food and energy, rose 0.3 percent. "
            "Shelter costs increased 0.5 percent and accounted for a large share of the monthly gain. "
            "Energy prices increased 1.1 percent."
        ),
    ),
    ReportCreate(
        source="BLS",
        report_type="Producer Price Index",
        release_date="2026-05-14",
        headline="PPI rises 0.2% vs 0.3% expected as goods prices cool",
        report_text=(
            "The Producer Price Index for final demand increased 0.2 percent in April. "
            "Final demand goods were unchanged, and final demand services increased 0.3 percent. "
            "Core PPI excluding food, energy, and trade services rose 0.1 percent. "
            "The index for final demand advanced 2.6 percent over the 12 months ended in April."
        ),
    ),
    ReportCreate(
        source="BEA",
        report_type="PCE Price Index",
        release_date="2026-05-29",
        headline="Core PCE rises 0.3% as annual inflation holds near 2.8%",
        report_text=(
            "Personal consumption expenditures increased 0.4 percent in April. "
            "The PCE price index increased 0.2 percent. "
            "Excluding food and energy, the PCE price index increased 0.3 percent. "
            "From the same month one year ago, the PCE price index increased 2.6 percent and core PCE increased 2.8 percent. "
            "Personal income increased 0.5 percent and real disposable personal income increased 0.2 percent."
        ),
    ),
    ReportCreate(
        source="Census",
        report_type="Retail Sales",
        release_date="2026-05-15",
        headline="Retail sales increase 0.1% vs 0.4% expected",
        report_text=(
            "Advance estimates of U.S. retail and food services sales increased 0.1 percent in April. "
            "Sales excluding motor vehicles and parts decreased 0.2 percent. "
            "The control group, which feeds into consumer spending estimates, was unchanged. "
            "Gasoline station sales increased 0.8 percent."
        ),
    ),
    ReportCreate(
        source="BEA",
        report_type="Gross Domestic Product",
        release_date="2026-04-30",
        headline="GDP grows 1.4% as consumer spending slows",
        report_text=(
            "Real gross domestic product increased at an annual rate of 1.4 percent in the first quarter. "
            "Consumer spending increased 1.2 percent, down from the prior quarter. "
            "Private inventory investment subtracted from growth, while imports increased. "
            "The price index for gross domestic purchases increased 3.0 percent."
        ),
    ),
    ReportCreate(
        source="ISM",
        report_type="ISM Manufacturing PMI",
        release_date="2026-05-01",
        headline="ISM manufacturing contracts at 48.6 as new orders weaken",
        report_text=(
            "The Manufacturing PMI registered 48.6 percent in April. "
            "The New Orders Index registered 47.2 percent and remained in contraction. "
            "The Employment Index registered 49.0 percent. "
            "The Prices Index registered 58.4 percent, indicating higher input costs."
        ),
    ),
    ReportCreate(
        source="DOL",
        report_type="Initial Jobless Claims",
        release_date="2026-05-07",
        headline="Jobless claims rise to 238k, above 220k expected",
        report_text=(
            "In the week ending May 2, initial claims for unemployment insurance were 238,000. "
            "The previous week's level was revised up by 4,000. "
            "The four-week moving average increased by 6,500 to 229,000. "
            "Continuing claims increased by 31,000."
        ),
    ),
    ReportCreate(
        source="BLS",
        report_type="JOLTS",
        release_date="2026-04-29",
        headline="JOLTS openings fall to 7.3 million as quits soften",
        report_text=(
            "Job openings decreased to 7.3 million on the last business day of March. "
            "Hires changed little at 5.4 million. "
            "Quits decreased to 3.1 million, while layoffs and discharges were little changed. "
            "The job openings rate decreased to 4.4 percent."
        ),
    ),
    ReportCreate(
        source="FOMC",
        report_type="Fed Rate Decision",
        release_date="2026-04-29",
        headline="Fed holds rates steady and keeps inflation risks in focus",
        report_text=(
            "The Committee decided to maintain the target range for the federal funds rate. "
            "Recent indicators suggest that economic activity has continued to expand at a solid pace. "
            "Inflation remains somewhat elevated. "
            "The Committee is attentive to the risks to both sides of its dual mandate."
        ),
    ),
    ReportCreate(
        source="BLS",
        report_type="Consumer Price Index",
        release_date="2026-04-10",
        headline="CPI cools to 0.2% vs 0.3% expected",
        report_text=(
            "The Consumer Price Index increased 0.2 percent in March. "
            "Over the last 12 months, the all items index increased 3.1 percent. "
            "Core CPI increased 0.2 percent. "
            "Shelter increased 0.3 percent, while energy declined 0.5 percent."
        ),
    ),
    ReportCreate(
        source="BEA",
        report_type="PCE Price Index",
        release_date="2026-03-27",
        headline="PCE prices rise 0.2% with core inflation at 2.7% year over year",
        report_text=(
            "The PCE price index increased 0.2 percent in February. "
            "Excluding food and energy, the PCE price index increased 0.2 percent. "
            "From the same month one year ago, the PCE price index increased 2.5 percent and core PCE increased 2.7 percent. "
            "Personal spending increased 0.3 percent."
        ),
    ),
    ReportCreate(
        source="BLS",
        report_type="Nonfarm Payrolls",
        release_date="2026-04-03",
        headline="Payrolls rise 95k vs 120k expected as labor market cools",
        report_text=(
            "Total nonfarm payroll employment increased by 95,000 in March. "
            "The change for January was revised up by 12,000 and the change for February was revised down by 18,000. "
            "Multiple jobholders decreased by 9,000 over the month. "
            "The number of persons employed part time for economic reasons increased by 16,000. "
            "Temporary help services declined by 7,000. "
            "The household survey showed civilian employment increased by 41,000."
        ),
    ),
]


REPORT_PRESETS = [
    {
        "source": sample.source,
        "report_type": sample.report_type,
        "headline": sample.headline,
        "report_text": sample.report_text,
    }
    for sample in MAJOR_RELEASE_SAMPLES[:10]
]
