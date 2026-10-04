# Codex Token Stats

A minimal KDE Plasma 6 widget base. It currently shows a panel icon and a
placeholder popup; token stats will come next.

## Development

Requires KDE Plasma 6, Plasma SDK (`plasmoidviewer`), Qt 6 QML tools, Python 3,
Make, and zip.

```sh
make check
make dev
make install
```

Add **Codex Token Stats** from Plasma's widget picker. `make install` also
upgrades an existing installation. Remove it with `make uninstall`.

Use `make format` to format QML, `make package` to build
`build/de.ruiny.codextokenstats.plasmoid`, and `make clean` to remove the build.
Qt tools default to `/usr/lib/qt6/bin`; override `QMLLINT` or `QMLFORMAT` if needed.

## Publishing

For local uploads, install `uv`, copy `.env.example` to `.env`, fill in your
Pling project ID and credentials, then run `make pling-upload`.

For GitHub releases, set repository variable `PLING_PROJECT_ID` and secrets
`PLING_USERNAME` and `PLING_PASSWORD`. Pushing a `release*` tag calls the starter's
shared upload workflow. Keep the changelog entry in sync with the metadata version.

Uploads replace all existing files on the configured Pling project.

Based on [kde-6-widget-starter](https://github.com/ruinivist/kde-6-widget-starter),
with the small project structure of `kde6-codex-limits`. Licensed under MIT.
