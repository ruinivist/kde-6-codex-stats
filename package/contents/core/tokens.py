"""Read rolling 24-hour Codex usage and estimate API-equivalent token costs.
Plasma runs this standard-library reader to populate its panel and popup.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------- Categories and pricing ----------

FIELDS = {
    "input": "input_tokens",
    "cache_read": "cached_input_tokens",
    "cache_write": "cache_write_input_tokens",
    "output": "output_tokens",
    "reasoning": "reasoning_output_tokens",
}
CATEGORIES = ("total", "input", "uncached", "cache_read", "cache_write", "output", "reasoning")


def response_cost(counts, model, tier, prices):
    """Price one response using its actual input size and recorded service tier.
    The usage reader sums these costs; reasoning remains a subset of output.
    """
    tier = {None: "standard", "default": "standard", "priority": "fast"}.get(tier, tier)
    rates = prices["models"].get(model, {}).get(tier)
    if rates is None:
        return None
    rates = rates["long" if counts["input"] > prices["long_context_above"] else "short"]
    costs = {key: 0.0 for key in CATEGORIES}
    for key, rate in zip(prices["rate_order"], rates):
        if rate is None and counts[key]:
            return None
        costs[key] = counts[key] * (rate or 0) / prices["per_tokens"]
    costs["input"] = costs["uncached"] + costs["cache_read"] + costs["cache_write"]
    costs["total"] = costs["input"] + costs["output"]
    costs["reasoning"] = counts["reasoning"] * (rates[3] or 0) / prices["per_tokens"]
    return costs


# ---------- Rolling usage reader ----------

def read_usage(home, now=None):
    """Return counts, category costs, and coverage for the preceding 24 hours.
    Used by the executable entry point and focused reader tests.
    """
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    start = now - timedelta(hours=24)
    counts = dict.fromkeys(CATEGORIES, 0)
    costs = dict.fromkeys(CATEGORIES, 0.0)
    issues = set()
    responses = {}
    complete = True
    pricing_complete = True
    unknown_counts = set()

    def problem(message):
        nonlocal complete
        complete = False
        issues.add(message)

    def walk_error(error):
        problem("Some session directories are unreadable.")

    try:
        prices = json.loads(Path(__file__).with_name("prices.json").read_text())
    except (OSError, ValueError):
        prices = {"models": {}}
        issues.add("Bundled pricing is unreadable.")
        pricing_complete = False

    home = Path(home)
    if not home.is_dir():
        problem("Codex home is missing or unreadable.")
    for directory in (home / "sessions", home / "archived_sessions"):
        try:
            directory.stat()
        except FileNotFoundError:
            continue
        except OSError:
            problem("Some session directories are unreadable.")
            continue

        for parent, _, files in os.walk(directory, onerror=walk_error):
            for filename in sorted(files):
                if not filename.endswith(".jsonl"):
                    continue
                path = Path(parent) / filename
                legacy_turns = set()
                recorded_turns = set()
                context = {}
                contexts = {}
                try:
                    if path.stat().st_mtime < start.timestamp():
                        continue
                    with path.open("rb") as source:
                        for line in source:
                            # A writer may still be appending the final JSON line.
                            if not line.endswith(b"\n"):
                                break
                            try:
                                record = json.loads(line)
                                if not isinstance(record, dict):
                                    raise ValueError
                                payload = record.get("payload", {})
                                if not isinstance(payload, dict):
                                    raise ValueError
                                kind = record.get("type")
                                if kind == "turn_context":
                                    context = payload
                                    contexts[payload.get("turn_id")] = context
                                    continue
                                if kind == "token_usage_record":
                                    recorded_turns.add(payload.get("turn_id"))
                                elif not (kind == "event_msg" and payload.get("type") == "token_count" and payload.get("info")):
                                    continue
                                stamp = datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))
                                if stamp.tzinfo is None:
                                    raise ValueError
                                if not start <= stamp <= now:
                                    continue
                                if kind != "token_usage_record":
                                    legacy_turns.add(context.get("turn_id"))
                                    continue
                                response_id = payload.get("response_id")
                                if not isinstance(response_id, str) or not response_id:
                                    problem("Usage records without response IDs were skipped.")
                                    continue
                                usage = payload.get("usage")
                                if not isinstance(usage, dict):
                                    raise ValueError
                                turn = contexts.get(payload.get("turn_id"), context)
                                model = payload.get("model") or turn.get("model")
                                tier = payload.get("service_tier") or turn.get("service_tier")
                                if model is not None and not isinstance(model, str):
                                    model = None
                                if tier is not None and not isinstance(tier, str):
                                    tier = "unsupported"
                                candidate = (usage, model, tier)
                                previous = responses.get(response_id)
                                if previous and previous[0] != usage:
                                    problem("Conflicting copies of response usage were found.")
                                if previous and any(a is not None and b is not None and a != b
                                                    for a, b in zip(previous[1:], candidate[1:])):
                                    pricing_complete = False
                                    issues.add("Conflicting pricing metadata was found in copied responses.")
                                # A copied history may omit its original turn context.
                                if previous is None:
                                    responses[response_id] = candidate
                                else:
                                    responses[response_id] = (previous[0], previous[1] or model,
                                                              previous[2] or tier)
                            except (ValueError, KeyError, TypeError):
                                problem("Malformed or unsupported session records were skipped.")
                    if legacy_turns - recorded_turns:
                        problem("Older token_count data has no per-response coverage.")
                except OSError:
                    problem("Some session files are unreadable.")

    for usage, model, tier in responses.values():
        response = {}
        valid = True
        for key, field in FIELDS.items():
            value = usage.get(field)
            if type(value) is not int or value < 0:
                problem("Some responses have missing or invalid token fields.")
                value = 0
                valid = False
                unknown_counts.add(key)
            response[key] = value
        response["uncached"] = response["input"] - response["cache_read"] - response["cache_write"]
        response["total"] = response["input"] + response["output"]
        if response["uncached"] < 0 or response["reasoning"] > response["output"]:
            problem("Some responses have inconsistent token categories.")
            response["uncached"] = max(0, response["uncached"])
            valid = False
            if response["cache_read"] + response["cache_write"] > response["input"]:
                unknown_counts.add("uncached")
            if response["reasoning"] > response["output"]:
                unknown_counts.add("reasoning")
        for key in CATEGORIES:
            counts[key] += response[key]
        cost = response_cost(response, model, tier, prices) if valid else None
        if cost is None:
            pricing_complete = False
            issues.add("Cost unavailable for some responses (model, tier, or token fields).")
        else:
            for key in CATEGORIES:
                costs[key] += cost[key]

    if not complete and not responses:
        pricing_complete = False
    if unknown_counts & {"input", "cache_read", "cache_write"}:
        unknown_counts.add("uncached")
    if unknown_counts & {"input", "output"}:
        unknown_counts.add("total")
    for key in unknown_counts:
        counts[key] = None
    return {
        "window_start": start.isoformat(),
        "window_end": now.isoformat(),
        "updated_at": now.isoformat(),
        "counts": counts if complete or responses else dict.fromkeys(CATEGORIES),
        "costs": costs if pricing_complete else dict.fromkeys(CATEGORIES),
        "responses": len(responses),
        "coverage_complete": complete,
        "pricing_complete": pricing_complete,
        "status": "ok" if complete and pricing_complete else "partial" if responses else "unavailable",
        "issues": sorted(issues),
    }


# ---------- Executable bridge ----------

if __name__ == "__main__":
    print(json.dumps(read_usage(os.environ.get("CODEX_HOME", Path.home() / ".codex"))))
