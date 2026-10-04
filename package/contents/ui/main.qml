// Provides the token stats widget's placeholder panel icon and full view.
// Loaded by Plasma as the applet's root interface.

pragma ComponentBehavior: Bound

// ---------- Imports ----------

import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.plasmoid

PlasmoidItem {
    id: root

    // ---------- Widget setup ----------

    toolTipMainText: "Codex Token Stats"
    toolTipSubText: "Ready to build."

    // ---------- Representations ----------

    compactRepresentation: PlasmaComponents.ToolButton {
        icon.name: "view-statistics"
        Accessible.name: root.toolTipMainText
        onClicked: root.expanded = !root.expanded
    }

    fullRepresentation: ColumnLayout {
        spacing: Kirigami.Units.smallSpacing
        Layout.minimumWidth: Kirigami.Units.gridUnit * 12
        Layout.minimumHeight: Kirigami.Units.gridUnit * 4

        PlasmaComponents.Label {
            text: root.toolTipMainText
            font.bold: true
            Layout.alignment: Qt.AlignHCenter
        }

        PlasmaComponents.Label {
            text: root.toolTipSubText
            Layout.alignment: Qt.AlignHCenter
        }
    }
}
