"""Check rolling 24-hour boundaries, coverage, deduplication, and per-response pricing.
Run by make check against temporary Codex homes without touching real logs.
"""

import importlib.util
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

# ---------- Reader and fixtures ----------

READER = Path(__file__).resolve().parents[1] / "package/contents/core/tokens.py"
spec = importlib.util.spec_from_file_location("tokens", READER)
tokens = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tokens)
NOW = datetime(2026, 10, 4, 12, tzinfo=ZoneInfo("Asia/Kolkata"))


def context(model="gpt-6.1-sol", tier=None, turn="turn"):
    return {"type": "turn_context", "payload": {"model": model, "service_tier": tier, "turn_id": turn}}


def response(identity="response", stamp=None, **overrides):
    usage = dict(input_tokens=1100000, cached_input_tokens=700000,
                 cache_write_input_tokens=0, output_tokens=200000,
                 reasoning_output_tokens=60000, total_tokens=1300000)
    usage.update(overrides)
    return {"type": "token_usage_record", "timestamp": (stamp or NOW).isoformat(),
            "payload": {"response_id": identity, "turn_id": "turn", "usage": usage}}


def legacy(stamp=NOW):
    return {"type": "event_msg", "timestamp": stamp.isoformat(),
            "payload": {"type": "token_count", "info": {"total_token_usage": {"total_tokens": 999999}}}}


# ---------- Reader checks ----------

class RollingUsageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)

    def write(self, records, name="sessions/resumed.jsonl", modified=NOW, tail=b""):
        path = self.home / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"".join(json.dumps(r).encode() + b"\n" for r in records) + tail)
        os.utime(path, (modified.timestamp(), modified.timestamp()))
        return path

    def read(self):
        return tokens.read_usage(self.home, NOW)

    def test_window_boundaries_resumed_session_and_modified_filter(self):
        start = NOW - timedelta(hours=24)
        self.write([context(), response("old", start - timedelta(microseconds=1)),
                    response("start", start), response("now", NOW),
                    response("future", NOW + timedelta(microseconds=1)),
                    response("yesterday", NOW - timedelta(hours=18))])
        self.write([context(), response("unmodified")], "sessions/old.jsonl", modified=start - timedelta(seconds=1))
        result = self.read()
        self.assertEqual(result["responses"], 3)
        self.assertEqual(result["counts"]["total"], 3900000)
        self.assertTrue(result["coverage_complete"])
        self.assertEqual(datetime.fromisoformat(result["window_start"]), start)
        self.assertEqual(datetime.fromisoformat(result["window_end"]), NOW)

    def test_usage_expires_as_window_moves(self):
        start = NOW - timedelta(hours=24)
        self.write([context(), response("expiring", start + timedelta(seconds=1))])
        self.assertEqual(self.read()["responses"], 1)
        result = tokens.read_usage(self.home, NOW + timedelta(seconds=2))
        self.assertEqual(result["counts"]["total"], 0)
        self.assertEqual(result["costs"]["total"], 0)
        self.assertEqual(result["status"], "ok")

    def test_midnight_does_not_reset_usage(self):
        midnight = NOW.replace(hour=0)
        self.write([context(), response(stamp=midnight - timedelta(hours=1))])
        before = tokens.read_usage(self.home, midnight - timedelta(seconds=1))
        after = tokens.read_usage(self.home, midnight + timedelta(seconds=1))
        self.assertEqual(before["counts"], after["counts"])
        self.assertEqual(after["counts"]["total"], 1300000)

    def test_dst_transitions_keep_exactly_24_elapsed_hours(self):
        zone = ZoneInfo("America/New_York")
        for month, day in [(3, 8), (11, 1)]:
            with self.subTest(month=month):
                now = datetime(2026, month, day, 12, tzinfo=zone)
                start = now.astimezone(ZoneInfo("UTC")) - timedelta(hours=24)
                self.write([context(), response("outside", start - timedelta(seconds=1)),
                            response("inside", start + timedelta(seconds=1)),
                            response("now", now)], modified=now)
                result = tokens.read_usage(self.home, now)
                self.assertEqual(result["responses"], 2)
                duration = datetime.fromisoformat(result["window_end"]) - datetime.fromisoformat(result["window_start"])
                self.assertEqual(duration.total_seconds(), 86400)
        now = datetime(2026, 11, 1, 12, tzinfo=zone)
        self.write([context(), response("first", datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=0)),
                    response("second", datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=1))], modified=now)
        self.assertEqual(tokens.read_usage(self.home, now)["responses"], 2)

    def test_archived_subagents_copied_histories_and_cumulative_ignored(self):
        self.write([context(), response(), legacy()])
        self.write([response()], "archived_sessions/copy.jsonl")
        self.write([context(), response("child")], "sessions/subagent/child.jsonl")
        result = self.read()
        self.assertEqual(result["responses"], 2)
        self.assertEqual(result["counts"]["total"], 2600000)
        self.assertTrue(result["coverage_complete"])
        self.assertTrue(result["pricing_complete"])

    def test_caching_reasoning_and_mockup_costs(self):
        self.write([context()] + [response(str(index), input_tokens=110000, cached_input_tokens=70000,
                                          output_tokens=20000, reasoning_output_tokens=6000) for index in range(10)])
        result = self.read()
        self.assertEqual(result["counts"]["total"], 1300000)
        self.assertEqual(result["counts"]["uncached"], 400000)
        self.assertAlmostEqual(result["costs"]["total"], 2.87)
        self.assertAlmostEqual(result["costs"]["input"], 0.87)
        self.assertAlmostEqual(result["costs"]["reasoning"], 0.60)
        self.assertAlmostEqual(result["costs"]["total"], result["costs"]["input"] + result["costs"]["output"])

    def test_cache_writes_have_separate_rate(self):
        self.write([context(), response(input_tokens=100000, cached_input_tokens=20000,
                                        cache_write_input_tokens=30000, output_tokens=1000,
                                        reasoning_output_tokens=0)])
        result = self.read()
        self.assertEqual(result["counts"]["uncached"], 50000)
        self.assertAlmostEqual(result["costs"]["cache_write"], 0.075)
        self.assertAlmostEqual(result["costs"]["total"], 0.187)

    def test_models_tiers_and_context_priced_before_aggregation(self):
        self.write([context(), response("sol", input_tokens=272000, cached_input_tokens=0, output_tokens=1000, reasoning_output_tokens=0),
                    context("gpt-6-luna", "priority"), response("luna", input_tokens=272001, cached_input_tokens=0, output_tokens=1000, reasoning_output_tokens=0),
                    context("gpt-6-astra", "flex"), response("astra", input_tokens=1000, cached_input_tokens=0, output_tokens=1000, reasoning_output_tokens=0)])
        result = self.read()
        self.assertAlmostEqual(result["costs"]["total"], 0.554 + 0.1103004 + 0.03)
        self.assertEqual(result["status"], "ok")

    def test_terra_pricing_with_sol_across_tiers_and_contexts(self):
        for tier, multiplier in [(None, 1), ("fast", 2), ("priority", 2), ("batch", 0.5), ("flex", 0.5)]:
            for size, terra_cost in [(272000, 0.2655), (272001, 0.528502)]:
                with self.subTest(tier=tier, input_tokens=size):
                    self.write([context(), response("sol", input_tokens=1000, cached_input_tokens=0,
                                                   output_tokens=1000, reasoning_output_tokens=0),
                                context("gpt-6.1-terra", tier),
                                response("terra", input_tokens=size, cached_input_tokens=20000,
                                         cache_write_input_tokens=30000, output_tokens=1000,
                                         reasoning_output_tokens=0)])
                    result = self.read()
                    self.assertEqual(result["status"], "ok")
                    self.assertTrue(result["pricing_complete"])
                    self.assertEqual(result["counts"]["total"], size + 3000)
                    self.assertAlmostEqual(result["costs"]["total"], 0.012 + terra_cost * multiplier)

    def test_explicit_response_metadata_overrides_turn(self):
        record = response(input_tokens=1000, cached_input_tokens=0, output_tokens=1000, reasoning_output_tokens=0)
        record["payload"].update(model="gpt-6-astra", service_tier="ultrafast")
        self.write([context(), record])
        self.assertAlmostEqual(self.read()["costs"]["total"], 0.36)

    def test_unknown_model_tier_and_unpriced_cache_preserve_counts(self):
        for model, tier, writes in [("gpt-reserve", None, 0), ("gpt-6.1-sol", "unknown", 0), ("gpt-5.5", None, 1)]:
            with self.subTest(model=model, tier=tier):
                self.write([context(model, tier), response(cache_write_input_tokens=writes)])
                result = self.read()
                self.assertEqual(result["counts"]["total"], 1300000)
                self.assertTrue(result["coverage_complete"])
                self.assertIsNone(result["costs"]["total"])
                self.assertEqual(result["status"], "partial")

    def test_missing_fields_preserve_available_counts_and_warn(self):
        record = response()
        del record["payload"]["usage"]["reasoning_output_tokens"]
        self.write([context(), record])
        result = self.read()
        self.assertEqual(result["counts"]["input"], 1100000)
        self.assertIsNone(result["counts"]["reasoning"])
        self.assertFalse(result["coverage_complete"])
        self.assertIsNone(result["costs"]["total"])
        record = response()
        del record["payload"]["usage"]["cached_input_tokens"]
        self.write([context(), record])
        self.assertIsNone(self.read()["counts"]["uncached"])

    def test_bad_categories_and_missing_id_report_incomplete(self):
        for overrides in [dict(cached_input_tokens=2000000), dict(reasoning_output_tokens=300000), dict(output_tokens=-1), dict(input_tokens=True)]:
            with self.subTest(overrides=overrides):
                self.write([context(), response(**overrides)])
                self.assertFalse(self.read()["coverage_complete"])
        record = response()
        del record["payload"]["response_id"]
        self.write([record])
        self.assertIsNone(self.read()["counts"]["total"])

    def test_legacy_only_and_mixed_schema_report_unsupported(self):
        self.write([context(), legacy()])
        self.assertEqual(self.read()["status"], "unavailable")
        self.assertIsNone(self.read()["counts"]["total"])
        self.write([context(), response(), context(turn="old-turn"), legacy()])
        result = self.read()
        self.assertFalse(result["coverage_complete"])
        self.assertEqual(result["counts"]["total"], 1300000)
        self.assertTrue(result["pricing_complete"])
        self.assertAlmostEqual(result["costs"]["total"], 4.74)
        self.assertEqual(result["status"], "partial")

    def test_unfinished_tail_ignored_but_complete_bad_lines_reported(self):
        self.write([context(), response()], tail=b'{"type":"token_usage_record"')
        self.assertEqual(self.read()["status"], "ok")
        self.write([context(), response()], tail=b'not json\n')
        result = self.read()
        self.assertFalse(result["coverage_complete"])
        self.assertTrue(result["pricing_complete"])
        self.assertAlmostEqual(result["costs"]["total"], 4.74)
        self.write([], tail=b'not json\n')
        self.assertIsNone(self.read()["costs"]["total"])

    def test_unreadable_files_are_reported(self):
        path = self.write([context(), response()])
        original = Path.open
        def open_file(p, *args, **kwargs):
            if p == path:
                raise PermissionError
            return original(p, *args, **kwargs)
        with patch.object(Path, "open", open_file):
            self.assertEqual(self.read()["status"], "unavailable")

    def test_empty_and_missing_home(self):
        self.assertEqual(self.read()["counts"]["total"], 0)
        self.assertEqual(self.read()["costs"]["total"], 0)
        self.assertEqual(tokens.read_usage(self.home / "absent", NOW)["status"], "unavailable")

    def test_conflicting_duplicates_report_partial(self):
        self.write([context(), response()])
        self.write([context(), response(output_tokens=200001)], "archived_sessions/copy.jsonl")
        self.assertFalse(self.read()["coverage_complete"])
        self.assertEqual(self.read()["responses"], 1)

    def test_copied_pricing_metadata_is_merged_or_reported(self):
        self.write([response()], "sessions/copy.jsonl")
        self.write([context(tier="priority"), response()], "archived_sessions/original.jsonl")
        self.assertTrue(self.read()["pricing_complete"])
        self.assertAlmostEqual(self.read()["costs"]["total"], 9.48)
        self.write([context("gpt-6-astra"), response()], "sessions/copy.jsonl")
        result = self.read()
        self.assertTrue(result["coverage_complete"])
        self.assertFalse(result["pricing_complete"])

    def test_timezone_does_not_change_window_or_counts(self):
        self.write([context(), response(stamp=NOW - timedelta(hours=23))])
        expected = self.read()
        for name in ("UTC", "Asia/Kolkata", "America/New_York"):
            with self.subTest(timezone=name), patch.dict(os.environ, {"TZ": name}):
                actual = tokens.read_usage(self.home, NOW.astimezone(ZoneInfo(name)))
                self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
