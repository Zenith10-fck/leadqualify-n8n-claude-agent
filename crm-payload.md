# GoHighLevel / CRM Field Mapping

How LeadQualify's validated `lead_qualification` object maps onto a CRM contact.
Written for GoHighLevel (the CRM in the top live jobs), but the same mapping works
for HubSpot / Airtable / any CRM with a contact upsert endpoint — only the field
names change.

## Contact upsert

| CRM field | Source | Notes |
|---|---|---|
| `email` | webhook `email` | Upsert key. If the contact exists, it is updated, not duplicated. |
| `name` | webhook `name` | |
| `companyName` | webhook `company` | |
| `tags` | `qualification.suggested_tags` | e.g. `["hot-lead","has-budget","urgent","hvac"]` |
| custom `lead_score` | `qualification.score` | 0-100, used for list sorting + reporting. |
| custom `pipeline_stage` | `qualification.pipeline_stage` | `new-hot` / `new-warm` / `nurture` / `disqualified` |
| custom `need_summary` | `qualification.need_summary` | Shows sales what the lead wants at a glance. |

## Routing rules (from `recommended_action`)

| Action | Pipeline stage | Side effects |
|---|---|---|
| `alert-sales-now` (hot) | `new-hot` | Upsert contact + instant Slack alert to `#sales-hot-leads`. Optional: Claude drafts a first-touch reply. |
| `auto-nurture` (warm) | `new-warm` | Upsert contact, add to nurture campaign. No human interrupt. |
| `no-action` (cold, non-spam) | `nurture` | Logged only; low-priority nurture list. |
| `no-action` + `is_spam:true` | `disqualified` | Logged and dropped. Never reaches sales or CRM pipeline. |

## Reliability branch (not a CRM write)

If `Validate Structured Output` returns `valid:false` **or** `confidence < 0.6`,
the lead is NOT written to the CRM. It goes to `#automation-alerts` as
"needs human review" with the raw message and the validation errors. This is the
"fails loudly, never silently" guarantee — a malformed AI response can never
create a half-shaped contact or drop a real lead without anyone noticing.

## Tag vocabulary (kept consistent for reporting)

`hot-lead`, `warm-lead`, `has-budget`, `no-budget`, `urgent`, `this-quarter`,
`spam`, plus one industry tag inferred from the message (`hvac`, `dental`,
`roofing`, `legal`, `solar`, `fitness`, `realty`, ...).
