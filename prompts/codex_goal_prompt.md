# Codex Goal Prompt

Build a local MVP for a financial/economic release analysis site.

The site should compare a reported news headline against the details inside an official monthly or quarterly release. The first target use case is Nonfarm Payrolls: if the headline says payrolls rose by 150k versus a 65k estimate, the backend should inspect the report for details like revisions, part-time work, multiple jobholders, industry concentration, government/private split, labor-force participation, and household survey divergence.

Use a local-first architecture now, but keep the shape compatible with a later Supabase backend:

- FastAPI API/web server
- SQLite metadata database for local MVP
- local file storage under `data/`
- Temporal workflow orchestration in Python
- optional OpenAI structured-output analysis
- deterministic fallback analysis when no model key is configured

The MVP should include:

- a web form for submitting a headline and report text
- local storage of the raw report
- a Temporal workflow that analyzes the report
- a report list and result view
- structured output showing verdict, score, supporting factors, contradicting factors, caveats, citations, and model used
- documentation for running locally with or without Temporal
