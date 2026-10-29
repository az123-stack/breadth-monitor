# Market Monitor v2 (prototype)

UI prototype for the v2 redesign (Option B, agreed Oct 28, 2026). Not wired into the daily build yet;
the live page at `/docs` is unchanged.

- `extract_sample.py` freezes a small slice of `docs/data.json` + `docs/story.json` into `sample.json`.
- `app.template.html` is the prototype (6 main tabs with sub-tabs; built: Today, Groups → Themes,
  Setups → All setups, Read → Latest; the rest list what moves there from v1).
- `app.html` = template with `sample.json` embedded. Rebuild:
  `python3 v2/extract_sample.py && python3 -c "from pathlib import Path as P;t=P('v2/app.template.html').read_text();d=P('v2/sample.json').read_text();P('v2/app.html').write_text(t.replace('__DATA__',d.replace('</','<\\/')))"`
- `style-sample.template.html` = the first one-page style sample (superseded by the tabbed app).
