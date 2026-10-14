"""
LeadQualify AI: live measurement.

Sends every lead in sample-leads.csv to Claude (headless Claude Code, no tools) with the system
prompt from claude/qualify-prompt.md and the schema from claude/schema.json, then scores the
answers against the labels in sample-leads.csv. Unlike measure.py (a rule-based reference), this
measures what Claude actually returns.

Usage:  python live_measure.py [--limit N] [--workers 4] [--model sonnet]
Writes: results-live.json
"""
import argparse, csv, json, os, re, shutil, subprocess, tempfile, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results-live.json")


def load_system_prompt():
    text = open(os.path.join(HERE, "claude", "qualify-prompt.md"), encoding="utf-8").read()
    after = text.split("## System prompt", 1)[1]
    prompt = re.search(r"```\n(.*?)\n```", after, re.S).group(1).strip()
    # In n8n the answer comes back as a tool call. Here it comes back as structured output.
    return prompt.replace("emit the lead_qualification tool call", "return the lead_qualification structured output")


def user_message(row):
    return (f"Source: {row['source']}\nName: {row['name']}\nEmail: {row['email']}\n"
            f"Company: {row['company']}\nMessage:\n{row['message']}")


def check_schema(obj, schema):
    """Minimal strict-schema check: required keys, no extra keys, types, enums, ranges."""
    errs = []
    props = schema["properties"]
    for k in schema["required"]:
        if k not in obj:
            errs.append(f"missing {k}")
    for k, v in obj.items():
        if k not in props:
            errs.append(f"extra {k}")
            continue
        p = props[k]
        t = p.get("type")
        if t == "integer" and not (isinstance(v, int) and not isinstance(v, bool)):
            errs.append(f"{k} not integer")
        elif t == "boolean" and not isinstance(v, bool):
            errs.append(f"{k} not boolean")
        elif t == "string" and not isinstance(v, str):
            errs.append(f"{k} not string")
        elif t == "array" and not isinstance(v, list):
            errs.append(f"{k} not array")
        if "enum" in p and v not in p["enum"]:
            errs.append(f"{k} not in enum")
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            if "minimum" in p and v < p["minimum"]: errs.append(f"{k} below min")
            if "maximum" in p and v > p["maximum"]: errs.append(f"{k} above max")
        if isinstance(v, str) and "maxLength" in p and len(v) > p["maxLength"]:
            errs.append(f"{k} too long")
        if isinstance(v, list) and "maxItems" in p and len(v) > p["maxItems"]:
            errs.append(f"{k} too many items")
    return errs


def ask(row, system, schema, model, wd):
    # On Windows the `claude` shim breaks JSON passed as an argument, so the values go through
    # environment variables and a bash one-liner (Git Bash). On macOS/Linux bash is already there.
    git_bash = r"C:\Program Files\Git\bin\bash.exe"  # not the WSL bash, which drops env vars
    cmd = [git_bash if os.path.exists(git_bash) else "bash", "-c",
           'claude -p --output-format json --model "$LQ_MODEL" --system-prompt "$LQ_SYSTEM" --tools "" '
           '--strict-mcp-config --no-session-persistence --json-schema "$LQ_SCHEMA"']
    env = dict(os.environ, LQ_MODEL=model, LQ_SYSTEM=system, LQ_SCHEMA=json.dumps(schema))
    t0 = time.time()
    p = subprocess.run(cmd, cwd=wd, env=env, input=user_message(row), capture_output=True, text=True,
                       timeout=300, encoding="utf-8")
    secs = time.time() - t0
    rec = {"lead_id": row["lead_id"], "seconds": round(secs, 1), "ok": False, "error": None}
    try:
        data = json.loads(p.stdout)
    except Exception:
        rec["error"] = (p.stderr or p.stdout)[:300]
        return rec
    rec["cost_usd"] = data.get("total_cost_usd")
    rec["model"] = list((data.get("modelUsage") or {}).keys())
    out = data.get("structured_output")
    if out is None:
        try:
            out = json.loads(data.get("result", ""))
        except Exception:
            rec["error"] = "no structured output: " + str(data.get("result"))[:200]
            return rec
    rec["output"] = out
    rec["schema_errors"] = check_schema(out, schema)
    rec["ok"] = not rec["schema_errors"]
    return rec


def label(o):
    return "spam" if o.get("is_spam") else o.get("intent")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--model", default="sonnet")
    a = ap.parse_args()
    rows = list(csv.DictReader(open(os.path.join(HERE, "sample-leads.csv"), encoding="utf-8")))
    if a.limit:
        rows = rows[:a.limit]
    system = load_system_prompt()
    schema = json.load(open(os.path.join(HERE, "claude", "schema.json"), encoding="utf-8"))["schema"]
    work = tempfile.mkdtemp(prefix="lq_live_")

    def run(r):
        wd = tempfile.mkdtemp(prefix="lq_", dir=work)
        return ask(r, system, schema, a.model, wd)

    with ThreadPoolExecutor(a.workers) as ex:
        recs = list(ex.map(run, rows))

    truth = {r["lead_id"]: r["ground_truth"] for r in rows}
    labels = ["hot", "warm", "cold", "spam"]
    cm = {t: {p: 0 for p in labels} for t in labels}
    per_lead, valid, correct = [], 0, 0
    for rec in recs:
        lid = rec["lead_id"]
        if rec["ok"]:
            valid += 1
            pred = label(rec["output"])
            cm[truth[lid]][pred] += 1
            correct += pred == truth[lid]
            per_lead.append({"lead_id": lid, "truth": truth[lid], "pred": pred,
                             "score": rec["output"].get("score"), "confidence": rec["output"].get("confidence")})
        else:
            per_lead.append({"lead_id": lid, "truth": truth[lid], "pred": None, "error": rec["error"] or rec.get("schema_errors")})
    n = len(rows)
    hot_t = sum(cm["hot"].values())
    spam_pred = sum(cm[t]["spam"] for t in labels)
    metrics = {
        "n_leads": n,
        "valid_outputs": valid,
        "overall_accuracy": round(correct / n, 3),
        "hot_recall": round(cm["hot"]["hot"] / hot_t, 3) if hot_t else None,
        "spam_precision": round(cm["spam"]["spam"] / spam_pred, 3) if spam_pred else None,
        "spam_recall": round(cm["spam"]["spam"] / max(1, sum(cm["spam"].values())), 3),
        "false_hot_to_sales": sum(cm[t]["hot"] for t in labels if t != "hot"),
        "spam_leaked_to_sales": cm["spam"]["hot"],
        "confusion_matrix": cm,
    }
    res = {"generated_at": time.strftime("%Y-%m-%d %H:%M"), "model": sorted({m for r in recs for m in r.get("model", [])}),
           "metrics": metrics, "total_cost_usd": round(sum(r.get("cost_usd") or 0 for r in recs), 3),
           "avg_seconds": round(sum(r["seconds"] for r in recs) / n, 1), "leads": per_lead}
    json.dump(res, open(OUT, "w", encoding="utf-8"), indent=2)
    print(json.dumps(metrics, indent=2))
    print("cost", res["total_cost_usd"], "avg s", res["avg_seconds"], "model", res["model"])
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
