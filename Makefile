# Provides local development, packaging, and publishing commands.
# Used from the repository root to manage the Plasma widget.

# ---------- Variables ----------

PACKAGE := package
ID := de.ruiny.codextokenstats
BUILD := build/$(ID).plasmoid
QMLLINT ?= /usr/lib/qt6/bin/qmllint
QMLFORMAT ?= /usr/lib/qt6/bin/qmlformat
QMLTESTRUNNER ?= /usr/lib/qt6/bin/qmltestrunner
PLING_UPLOADER := https://raw.githubusercontent.com/ruinivist/kde-6-widget-starter/main/scripts/pling_upload.py

# ---------- Commands ----------

.PHONY: dev check format install uninstall package pling-upload clean

dev:
	plasmoidviewer -a $(PACKAGE)

check:
	python3 -m json.tool $(PACKAGE)/metadata.json >/dev/null
	python3 -m json.tool $(PACKAGE)/contents/core/prices.json >/dev/null
	python3 -m unittest discover -s tests
	QT_QPA_PLATFORM=offscreen $(QMLTESTRUNNER) -input tests
	$(QMLLINT) $(PACKAGE)/contents/ui/main.qml

format:
	$(QMLFORMAT) -i $(PACKAGE)/contents/ui/main.qml

install:
	@if kpackagetool6 --type Plasma/Applet --show $(ID) >/dev/null 2>&1; then \
		kpackagetool6 --type Plasma/Applet --upgrade $(PACKAGE); \
	else \
		kpackagetool6 --type Plasma/Applet --install $(PACKAGE); \
	fi

uninstall:
	kpackagetool6 --type Plasma/Applet --remove $(ID)

package:
	mkdir -p build
	rm -f $(BUILD)
	cd $(PACKAGE) && zip -qr ../$(BUILD) . -x '*/__pycache__/*'

pling-upload: package
	uv run --isolated --env-file .env --with 'niquests>=3.18.5' $(PLING_UPLOADER) -f $(BUILD)

clean:
	rm -rf build
