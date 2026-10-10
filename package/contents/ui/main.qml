// Defines the rolling 24-hour token panel, breakdown popup, and reader lifecycle.
// Plasma loads this root interface and invokes the bundled Python reader.

pragma ComponentBehavior: Bound

// ---------- Imports ----------

import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.plasma5support as Plasma5Support
import org.kde.plasma.plasmoid
import "Format.js" as Format

PlasmoidItem {
    id: root

    // ---------- State ----------

    property var stats: ({})
    property bool reading: false
    property bool refreshPending: false
    readonly property string title: i18n("Codex Token Stats")
    readonly property string scriptPath: decodeURIComponent(Qt.resolvedUrl("../core/tokens.py").toString().replace(/^file:\/\//, ""))
    readonly property string command: "python3 '" + scriptPath.replace(/'/g, "'\\''") + "'"
    readonly property var rows: [
        {
            key: "total",
            label: i18n("Total"),
            child: false
        },
        {
            key: "input",
            label: i18n("Input"),
            child: false
        },
        {
            key: "uncached",
            label: i18n("↳ Uncached"),
            child: true
        },
        {
            key: "cache_read",
            label: i18n("↳ Cache read"),
            child: true
        },
        {
            key: "cache_write",
            label: i18n("↳ Cache write"),
            child: true
        },
        {
            key: "output",
            label: i18n("Output"),
            child: false
        },
        {
            key: "reasoning",
            label: i18n("↳ Reasoning"),
            child: true
        }
    ]

    // ---------- Helpers ----------

    function refresh() {
        if (reading) {
            refreshPending = true;
            return;
        }
        reading = true;
        runner.connectSource(command);
    }

    function count(key) {
        return stats.counts ? stats.counts[key] : null;
    }

    function cost(key) {
        return stats.costs ? stats.costs[key] : null;
    }

    // ---------- Lifecycle ----------

    preferredRepresentation: compactRepresentation
    toolTipMainText: ""
    toolTipSubText: ""
    Component.onCompleted: refresh()
    onExpandedChanged: if (root.expanded)
        refresh()

    Timer {
        interval: 30000
        running: true
        repeat: true
        onTriggered: root.refresh()
    }

    // ---------- Data loading ----------

    Plasma5Support.DataSource {
        id: runner
        engine: "executable"
        onNewData: function (sourceName, data) {
            disconnectSource(sourceName);
            root.reading = false;
            try {
                if (data["exit code"] !== 0)
                    throw new Error(i18n("Unable to run the token reader."));
                root.stats = JSON.parse(data.stdout);
            } catch (error) {
                root.stats = {};
                console.warn(error.message || i18n("Unable to read token usage."));
            }
            if (root.refreshPending) {
                root.refreshPending = false;
                root.refresh();
            }
        }
    }

    // ---------- Representations ----------

    compactRepresentation: RowLayout {
        spacing: Kirigami.Units.smallSpacing
        Layout.minimumWidth: implicitWidth
        Layout.minimumHeight: implicitHeight
        Layout.maximumHeight: implicitHeight
        Accessible.role: Accessible.Button
        Accessible.name: root.title
        Accessible.description: usage.text
        Accessible.onPressAction: root.expanded = !root.expanded

        TapHandler {
            acceptedButtons: Qt.LeftButton
            onTapped: root.expanded = !root.expanded
        }

        Image {
            source: "../images/chatgpt.svg"
            Layout.preferredWidth: usage.implicitHeight
            Layout.preferredHeight: usage.implicitHeight
            Layout.alignment: Qt.AlignVCenter
        }

        PlasmaComponents.Label {
            id: usage
            text: Format.compact(root.count("total")) + " (" + Format.compact(root.count("input")) + " / " + Format.compact(root.count("output")) + ") | " + (root.cost("total") === null ? "--" : Format.dollars(root.cost("total")))
            color: "white"
            font.family: "monospace"
        }
    }

    fullRepresentation: ColumnLayout {
        spacing: Kirigami.Units.smallSpacing
        Layout.minimumWidth: Kirigami.Units.gridUnit * 20
        Layout.minimumHeight: implicitHeight

        PlasmaComponents.Label {
            text: root.title
            font.bold: true
            Layout.bottomMargin: Kirigami.Units.smallSpacing
        }

        GridLayout {
            id: tokenGrid
            columns: 3
            columnSpacing: Kirigami.Units.gridUnit
            rowSpacing: Kirigami.Units.smallSpacing
            Layout.fillWidth: true

            PlasmaComponents.Label {
                text: i18n("Tokens")
                opacity: 0.7
                Layout.fillWidth: true
            }
            PlasmaComponents.Label {
                text: i18n("Count")
                opacity: 0.7
                Layout.alignment: Qt.AlignRight
                horizontalAlignment: Text.AlignRight
            }
            PlasmaComponents.Label {
                text: i18n("Est. cost")
                opacity: 0.7
                Layout.alignment: Qt.AlignRight
                horizontalAlignment: Text.AlignRight
            }

            Repeater {
                model: root.rows.length * 3
                delegate: PlasmaComponents.Label {
                    id: cell
                    required property int index
                    readonly property int column: index % 3
                    readonly property var tokenRow: root.rows[Math.floor(index / 3)]
                    readonly property bool separated: tokenRow.key === "total" || tokenRow.key === "output"
                    text: column === 0 ? tokenRow.label : column === 1 ? Format.grouped(root.count(tokenRow.key)) : Format.dollars(root.cost(tokenRow.key))
                    font.family: column === 0 ? Kirigami.Theme.defaultFont.family : "monospace"
                    font.bold: tokenRow.key === "total"
                    opacity: column === 0 && tokenRow.child ? 0.7 : 1
                    horizontalAlignment: column === 0 ? Text.AlignLeft : Text.AlignRight
                    leftPadding: column === 0 && tokenRow.child ? Kirigami.Units.smallSpacing : 0
                    Layout.fillWidth: true
                    Layout.horizontalStretchFactor: column === 0 ? 1 : 0
                    Layout.alignment: Qt.AlignTop
                    Layout.topMargin: separated ? Kirigami.Units.smallSpacing * 2 : 0

                    Rectangle {
                        visible: cell.separated
                        y: -Kirigami.Units.smallSpacing * 2
                        width: parent.width + (cell.column < 2 ? tokenGrid.columnSpacing : 0)
                        height: 1
                        color: Kirigami.Theme.textColor
                        opacity: 0.12
                    }
                }
            }
        }
    }
}
