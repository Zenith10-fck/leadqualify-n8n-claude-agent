# LeadQualify AI: Lead Qualification and CRM Routing

Inbound lead qualification and CRM routing agent. **n8n + Claude + GoHighLevel.**
Claude scores each lead, classifies intent (hot, warm, cold, spam) and returns one validated
JSON object. The workflow then upserts the contact in the CRM, alerts sales on hot leads, and
logs and drops spam. Reference build on a labeled synthetic test set.

## Files

| File | What it is |
|---|---|
| `workflow.json` | The n8n workflow (import into n8n; swap credentials + channel IDs). |
| `claude/qualify-prompt.md` | System prompt + reliability contract for the Claude node. |
| `claude/schema.json` | Strict JSON schema the model output is validated against. |
| `sample-leads.csv` | 40 labeled test leads (hot / warm / cold / spam). |
| `live_measure.py` | Live measurement: sends every lead to Claude, scores the answers. |
| `results-live.json` | Output of `live_measure.py`. |
| `measure.py` | Rule-based reference of the rubric (no API calls). |
| `results.json` | Output of `measure.py`. |
| `crm-payload.md` | Field/tag mapping onto GoHighLevel (or any CRM). |
| `case-study.md` | Write-up of the build and its measured results. |
| `case-study.html` | Case-study page. |

## Results

Live run: all 40 sample leads sent to Claude (`claude-sonnet-5`) with `claude/qualify-prompt.md` and
`claude/schema.json`. Output in `results-live.json`.

| Metric | Result |
|---|---|
| Overall accuracy | 85% (34 of 40) |
| Hot-lead recall | 91% (10 of 11) |
| Valid structured output | 40 of 40 |
| Spam caught | 100% (8 of 8) |
| Non-hot leads sent to sales as hot | 0 |

Errors: 4 warm leads rated cold, 1 hot rated warm, 1 cold flagged as spam. One run per lead, so
treat it as a controlled demo.

```bash
python live_measure.py            # needs the Claude Code CLI (`claude -p`) and Git Bash on Windows
```

`measure.py` is something else: a rule-based reference implementation of the same rubric (no API
calls, 90% on this set). Its patterns were written while looking at these leads, so it is not
evidence of how Claude performs. Use `live_measure.py` for that.

## Honesty note

This is a **reference/demo build**, not a paid client engagement. Metrics come
from the self-built labeled test set and are reproducible. No client names,
logos, or testimonials are implied.

