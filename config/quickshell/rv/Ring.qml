import QtQuick
import QtQuick.Shapes

// Small progress ring with the value in the middle.
Item {
    id: root

    property real value: 0          // 0..1
    property string label: Math.round(value * 100)
    property color colour: value > 0.9 ? Config.bad : value > 0.7 ? Config.warn : Config.accent
    property real thickness: 2.5

    implicitWidth: Config.barWidth - 18
    implicitHeight: implicitWidth

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            strokeColor: Config.alpha(Config.text, 0.1)
            strokeWidth: root.thickness
            fillColor: "transparent"
            PathAngleArc {
                centerX: root.width / 2; centerY: root.height / 2
                radiusX: root.width / 2 - root.thickness; radiusY: radiusX
                startAngle: 0; sweepAngle: 360
            }
        }
        ShapePath {
            strokeColor: root.colour
            strokeWidth: root.thickness
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            PathAngleArc {
                centerX: root.width / 2; centerY: root.height / 2
                radiusX: root.width / 2 - root.thickness; radiusY: radiusX
                startAngle: -90
                sweepAngle: Math.max(0.01, Math.min(1, root.value)) * 360
                Behavior on sweepAngle { NumberAnimation { duration: 400; easing.type: Easing.OutCubic } }
            }
        }
    }

    Text {
        anchors.centerIn: parent
        text: root.label
        color: Config.text
        font.family: Config.font
        font.pixelSize: Math.round(root.width * 0.34)
        font.bold: true
    }
}
