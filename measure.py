"""
LeadQualify AI — reference measurement harness.

Runs the qualification rubric (the same logic encoded in claude/qualify-prompt.md)
over the labeled sample set and reports accuracy + a confusion matrix.

NOTE ON HONESTY: this is a deterministic reference implementation of the rubric,
used to measure the routing logic reproducibly WITHOUT spending API tokens. In
production the same rubric runs inside Claude (see qualify-prompt.md + schema.json).
The numbers this prints are the numbers cited in the case study, and anyone can
re-run this file to reproduce them.

Usage:  python measure.py
"""
import csv
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(HERE, "sample-leads.csv")
OUT = os.path.join(HERE, "results.json")

SPAM_PATTERNS = [
    r"you won", r"congratulat", r"claim your", r"free free", r"click here",
    r"click the link", r"bit\.ly", r"no credit check", r"guaranteed",
    r"crypto", r"\$\d[\d,]*\s*(reward|loan|prize)", r"limited time",
    r"act now", r"buy \d", r"verified email", r"lorem ipsum", r"asdf",
    r"test test", r"increase your sales", r"win big", r"iphone \d+ now",
]
SPAM_DOMAINS = (".info", ".biz", ".ru", ".xyz")
URGENT = [r"asap", r"this week", r"end of month", r"start now", r"urgent",
          r"right now", r"immediately", r"within \d+ (day|week)", r"ready to (move|begin|pay|start)"]
QUARTER = [r"next month", r"next quarter", r"in a few weeks", r"this month",
           r"in \d+ weeks", r"few weeks"]
BUDGET_NUM = [r"\$\s?\d", r"\d[\d,]*\s?k\b", r"\d[\d,]{2,}"]
BUDGET_IMPLIED = [r"budget (approved|confirmed|flexible|set aside)",
                  r"ready to pay", r"budget confirmed", r"have budget", r"serious budget"]
INTENT_STRONG = [r"want to start", r"ready to", r"hire", r"jump on a call",
                 r"let'?s (talk|scope)", r"start (now|this|within)", r"can we talk",
                 r"want this live", r"need to (start|begin)", r"hoping to start"]
INTENT_WARM = [r"exploring", r"considering", r"comparing", r"would like a proposal",
               r"learn more", r"gathering info", r"understand (your|the|pricing|our)",
               r"interested in (learning|a lead|automating)", r"looking into",
               r"curious (about|if)", r"might want", r"would need", r"see a demo",
               r"check with", r"like a proposal", r"understand pricing",
               r"proposal to review", r"open to a conversation"]
OFFTOPIC = [r"social media", r"instagram", r"interview you", r"for (a|my) (class|blog)",
            r"researching", r"student", r"looking for subcontract", r"not a client",
            r"just (looking|wondering)", r"e-commerce chatbot", r"probably not a fit",
            r"website looks nice", r"not really automation", r"not looking to buy",
            r"do you do social", r"how much does it cost\? *thats all"]


def has(patterns, text):
    return any(re.search(p, text) for p in patterns)


def qualify(row):
    text = (row["message"] or "").lower()
    email = (row["email"] or "").lower()

    # --- spam gate ---
    spam_hits = has(SPAM_PATTERNS, text)
    bad_domain = email.endswith(SPAM_DOMAINS)
    no_company = not (row["company"] or "").strip()
    placeholder_email = email in ("test@test.com",) or email.startswith(("asdf@", "noreply@", "promo@", "claim@", "winner@", "fastcash@", "noname@"))
    is_spam = spam_hits or (bad_domain and (spam_hits or no_company)) or (placeholder_email and (spam_hits or no_company))

    if is_spam:
        return dict(score=0, intent="cold", is_spam=True, budget_signal="none",
                    timeline_signal="none", pipeline_stage="disqualified",
                    recommended_action="no-action", confidence=0.9)

    # --- signals ---
    budget = "stated" if has(BUDGET_NUM, text) else ("implied" if has(BUDGET_IMPLIED, text) else "none")
    timeline = "urgent" if has(URGENT, text) else ("this_quarter" if has(QUARTER, text) else "none")
    offtopic = has(OFFTOPIC, text)
    strong_intent = has(INTENT_STRONG, text)
    warm_intent = has(INTENT_WARM, text)

    # --- score ---
    score = 0
    if offtopic:
        score += 5
    elif strong_intent:
        score += 34
    elif warm_intent:
        score += 28  # genuine evaluator: interested, not yet ready to buy
    else:
        score += 18  # generic interest
    score += {"stated": 25, "implied": 16, "none": 0}[budget]
    score += {"urgent": 20, "this_quarter": 11, "none": 0}[timeline]
    score += 3 if offtopic else 12  # fit/specificity

    if offtopic:
        score = min(score, 35)

    # --- intent mapping ---
    if score >= 70 and budget in ("stated", "implied") and timeline in ("urgent", "this_quarter"):
        intent = "hot"
    elif score >= 40 and not offtopic:
        intent = "warm"
    else:
        intent = "cold"

    stage = {"hot": "new-hot", "warm": "new-warm", "cold": "nurture"}[intent]
    action = {"hot": "alert-sales-now", "warm": "auto-nurture", "cold": "no-action"}[intent]
    confidence = 0.85 if (len(text) > 40) else 0.5

    return dict(score=score, intent=intent, is_spam=False, budget_signal=budget,
                timeline_signal=timeline, pipeline_stage=stage,
                recommended_action=action, confidence=round(confidence, 2))


def predicted_label(q):
    return "spam" if q["is_spam"] else q["intent"]


def main():
    rows = list(csv.DictReader(open(SAMPLE, encoding="utf-8")))
    labels = ["hot", "warm", "cold", "spam"]
    confusion = {a: {b: 0 for b in labels} for a in labels}
    results = []
    correct = 0
    spam_tp = spam_fp = spam_fn = 0

    for row in rows:
        q = qualify(row)
        pred = predicted_label(q)
        truth = row["ground_truth"]
        confusion[truth][pred] += 1
        if pred == truth:
            correct += 1
        if truth == "spam" and pred == "spam":
            spam_tp += 1
        if truth != "spam" and pred == "spam":
            spam_fp += 1
        if truth == "spam" and pred != "spam":
            spam_fn += 1
        results.append(dict(lead_id=row["lead_id"], truth=truth, pred=pred, **q))

    n = len(rows)
    acc = correct / n
    # "would a hot lead reach sales?" — recall on hot
    hot_total = sum(1 for r in rows if r["ground_truth"] == "hot")
    hot_caught = sum(1 for r in results if r["truth"] == "hot" and r["pred"] == "hot")
    spam_total = sum(1 for r in rows if r["ground_truth"] == "spam")
    metrics = {
        "n_leads": n,
        "overall_accuracy": round(acc, 3),
        "hot_recall": round(hot_caught / hot_total, 3) if hot_total else None,
        "spam_precision": round(spam_tp / (spam_tp + spam_fp), 3) if (spam_tp + spam_fp) else None,
        "spam_recall": round(spam_tp / spam_total, 3) if spam_total else None,
        "false_hot_to_sales": sum(1 for r in results if r["pred"] == "hot" and r["truth"] != "hot"),
        "spam_leaked_to_sales": sum(1 for r in results if r["pred"] != "spam" and r["truth"] == "spam" and r["pred"] == "hot"),
        "confusion_matrix": confusion,
    }
    json.dump({"metrics": metrics, "results": results}, open(OUT, "w"), indent=2)

    print(f"Leads scored:        {n}")
    print(f"Overall accuracy:    {acc:.1%}")
    print(f"Hot-lead recall:     {metrics['hot_recall']:.1%}  (hot leads that reach sales)")
    print(f"Spam precision:      {metrics['spam_precision']:.1%}  (of flagged spam, share truly spam)")
    print(f"Spam recall:         {metrics['spam_recall']:.1%}  (of real spam, share caught)")
    print(f"Spam leaked as hot:  {metrics['spam_leaked_to_sales']}")
    print("\nConfusion matrix (rows = truth, cols = predicted):")
    header = "        " + "".join(f"{l:>7}" for l in labels)
    print(header)
    for a in labels:
        print(f"{a:>7} " + "".join(f"{confusion[a][b]:>7}" for b in labels))
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
