# LeadQualify AI: Inbound Lead Qualification and CRM Routing (n8n + Claude + GoHighLevel)

**Role:** AI Automation Engineer
**Stack:** n8n, Claude API (structured output), GoHighLevel CRM, Slack
**Type:** Reference build and demonstration (portfolio project, not a paid engagement)

## The problem

Most small businesses that run ads or forms have the same bottleneck: leads
arrive faster than a human can read them. So hot buyers sit in an inbox for
hours, junk and spam eat the team's attention, and "warm but not ready" leads
get no follow-up at all. The cost is not a crash. It is quiet lost revenue.

## What I built

An AI agent that reads every inbound lead the moment it arrives and decides what
happens next, end to end:

1. **Intake.** An n8n webhook catches the lead from a web form or inbound email.
2. **Qualify with Claude.** Claude scores the lead 0 to 100, classifies intent as
   hot, warm, or cold, extracts budget and timeline signals, and flags spam. It
   is forced to answer as one validated JSON object, never free text.
3. **Route to the CRM.** The agent upserts the contact in GoHighLevel with the
   right tags and pipeline stage. Hot leads also fire an instant Slack alert to
   sales. Spam is logged and dropped. It never reaches the pipeline.
4. **Fail loudly, never silently.** If Claude's output ever drifts from the
   schema, or confidence is low, the lead is sent to a human-review branch with
   an alert. A malformed AI response can never create a half-shaped contact or
   silently swallow a real lead.

## The reliability layer (why this is different)

Most AI integrations work fine on the first fifty runs, then start returning JSON
in a slightly different shape and break downstream without anyone noticing. I
build against exactly that failure mode. Every Claude response is validated
against a strict JSON schema (types, enums, ranges, required fields). On drift the
workflow re-prompts once with the validation error, and if it still fails it
routes to a human with a Slack alert. That is the difference between a demo and
something a business can leave running.

## Results (live Claude run on a 40-lead labeled test set)

I built a labeled set of 40 realistic inbound leads (hot, warm, cold, and spam) and sent each one
to Claude (`claude-sonnet-5`) with the prompt and schema in `claude/`. The numbers come from
`results-live.json`, written by `live_measure.py`, and anyone can re-run it.

| Metric | Result | Why it matters |
|---|---|---|
| Overall classification accuracy | **85%** (34 of 40) | The agent agrees with the label on 17 of 20 leads. |
| Hot-lead recall | **91%** (10 of 11) | Genuine buyers that correctly reach sales fast. |
| Valid structured output | **40 of 40** | Every answer passed the schema check. |
| Spam caught | **100%** (8 of 8) | No spam reached the sales pipeline. |
| Non-hot leads sent to sales as hot | **0** | Sales time is never wasted on false alarms. |

Where it was wrong: 4 warm leads rated cold (wording such as "no firm timeline"), 1 hot lead rated
warm, and 1 cold lead flagged as spam. One run per lead on 40 synthetic leads, so treat the numbers
as a controlled demo, not a benchmark.

Operational impact (modeled from these results, typical small-business volume):

| Before | After |
|---|---|
| Every lead read by hand, roughly 3 to 4 minutes each | Auto-triaged in seconds, human reads only qualified leads |
| Hot leads answered in hours | Hot leads alerted to sales in seconds |
| Spam mixed into the sales queue | Spam filtered out before it reaches anyone |

## What a client gets

- The n8n workflow, imported and connected to their CRM and Slack
- The Claude qualification prompt and schema, tuned to their business and their
  definition of a good lead
- The reliability layer so it does not fail silently
- A short Loom walkthrough and a one-page maintenance doc so their team can own it

## Want the same for your inbound leads?

Send me how leads reach you today (a form, an inbox, a screenshot) and I will tell
you exactly what a build looks like for your business.
