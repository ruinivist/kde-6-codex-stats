# Codex Token Stats

A compact KDE Plasma 6 panel widget for locally saved Codex tokens over the last 24 hours:

```text
1.3Mil (1.1Mil / 200K) | $2.87
```

Click to open **Codex Token Stats**, with exact grouped counts and estimated
costs for total, input, uncached input, cache reads, cache writes, output, and
reasoning. Reasoning is included in output; its row shows a subset of the output
cost. The popup contains only its title and table, with no hover tooltips.
The panel uses the white icon, monospace text, and compact spacing of
`kde6-codex-limits`.

## Usage and coverage

The bundled Python standard-library reader scans `$CODEX_HOME` (default
`~/.codex`), including `sessions` and `archived_sessions`. It counts CLI, IDE/app,
and subagent activity saved in those directories. It selects files modified
within the window, then filters per-response `token_usage_record` timestamps
from 24 hours ago through the current time. Sessions started earlier are included
when resumed within that window. Response IDs prevent copied or forked histories from counting
again. Cumulative `token_count` entries never contribute to totals.

The widget refreshes at startup, every 30 seconds, and when the popup opens.
Reads cannot overlap. Older responses leave the totals on the next refresh
after they pass the 24-hour cutoff. The window uses elapsed time in UTC, so
timezones, midnight, and daylight-saving changes do not reset it. Counts use
decimal K, Mil, Bil, and Tri units
in the panel, rounded to one decimal without trailing zeros.

Codex 0.160.0 supplies the required per-response fields. The reader skips
unsupported or malformed records and unfinished trailing log lines. Reader
diagnostics remain available in its JSON output.
`--` indicates unavailable data or cost; a complete window with no activity shows
zero counts and `$0.00`.

## Estimated costs

Costs are **API-equivalent token estimates in USD**, excluding subscription
payments and additional tool charges. Codex does not provide a usable daily
dollar breakdown for this account. These estimates are not account charges.

[Official OpenAI API prices](https://developers.openai.com/api/docs/pricing)
are bundled in `package/contents/core/prices.json`, checked on October 4, 2026,
for public models in the installed catalog: GPT-6 Astra, GPT-6.1 Sol, GPT-6 Sol,
GPT-6 Luna, GPT-5.6 Sol/Terra/Luna, and GPT-5.5. The widget needs no network
access. The bundled snapshot requires an update when published rates change.

Each response uses its recorded model and service tier, with Standard for an
unspecified tier (`default` is Standard; `priority` is Fast). Published Batch,
Flex, Fast, and Ultrafast rates are included where available. Long-context
rates apply above 272,000 input tokens per response, before window aggregation.
Uncached input is input minus cache reads and cache writes. Reasoning is never
charged twice. Unknown models, unsupported tiers, missing token fields, or
unpublished rates preserve available counts and make costs unavailable.

## Development

Requires KDE Plasma 6 with Plasma5Support, Python 3, Make, and zip. Development
checks and previews also require Plasma SDK (`plasmoidviewer`) and Qt 6 QML
tools, including QtTest (`qmltestrunner`). No Python packages or settings are
needed.

```sh
make check
make dev
make install
```

`make check` runs focused Python reader tests, Qt formatting tests, JSON
validation, and QML linting. To inspect the reader's JSON directly:

```sh
python3 package/contents/core/tokens.py
```

Add **Codex Token Stats** from Plasma's widget picker. `make install` also
upgrades an existing installation. Remove it with `make uninstall`.

Use `make format` to format QML, `make package` to build
`build/de.ruiny.codextokenstats.plasmoid`, and `make clean` to remove the build.
Qt tools default to `/usr/lib/qt6/bin`; override `QMLLINT`, `QMLFORMAT`, or
`QMLTESTRUNNER` if needed.

## Publishing

For local uploads, install `uv`, copy `.env.example` to `.env`, fill in your
Pling project ID and credentials, then run `make pling-upload`.

For GitHub releases, set repository variable `PLING_PROJECT_ID` and secrets
`PLING_USERNAME` and `PLING_PASSWORD`. Pushing a `release*` tag calls the starter's
shared upload workflow. Keep the changelog entry in sync with the metadata version.

Uploads replace all existing files on the configured Pling project.

Based on [kde-6-widget-starter](https://github.com/ruinivist/kde-6-widget-starter),
with the small project structure of `kde6-codex-limits`. Licensed under MIT.
