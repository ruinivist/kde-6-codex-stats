// Verifies the panel abbreviations, exact popup counts, and unavailable states.
// Run by Qt's test runner through make check.

import QtQuick
import QtTest
import "../package/contents/ui/Format.js" as Format

TestCase {
    name: "TokenFormatting"

    // ---------- Display checks ----------

    function test_compact_data() {
        return [
            { tag: "zero", value: 0, expected: "0" },
            { tag: "small", value: 999, expected: "999" },
            { tag: "k", value: 1000, expected: "1K" },
            { tag: "decimal", value: 1250, expected: "1.3K" },
            { tag: "rounding", value: 999950, expected: "1Mil" },
            { tag: "million", value: 1300000, expected: "1.3Mil" },
            { tag: "billion", value: 1000000000, expected: "1Bil" },
            { tag: "trillion", value: 1000000000000, expected: "1Tri" },
            { tag: "unavailable", value: null, expected: "--" }
        ];
    }

    function test_compact(data) {
        compare(Format.compact(data.value), data.expected);
    }

    function test_popup() {
        compare(Format.grouped(1300000), "1,300,000");
        compare(Format.grouped(0), "0");
        compare(Format.grouped(null), "--");
        compare(Format.dollars(2.87), "$2.87");
        compare(Format.dollars(0), "$0.00");
        compare(Format.dollars(null), "--");
        compare(Format.compact(undefined), "--");
        compare(Format.dollars(undefined), "--");
    }

}
