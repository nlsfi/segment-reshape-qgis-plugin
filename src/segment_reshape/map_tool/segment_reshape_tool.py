#  Copyright (C) 2022 National Land Survey of Finland
#  (https://www.maanmittauslaitos.fi/en).
#
#
#  This file is part of segment-reshape-qgis-plugin.
#
#  segment-reshape-qgis-plugin is free software: you can redistribute it and/or
#  modify it under the terms of the GNU General Public License as published
#  by the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  segment-reshape-qgis-plugin is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied warranty
#  of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with segment-reshape-qgis-plugin. If not, see <https://www.gnu.org/licenses/>.

import logging
from enum import Enum
from typing import Optional, Tuple

from qgis.core import QgsGeometry, QgsLineString, QgsPointXY, QgsVectorLayer
from qgis.gui import (
    QgsMapCanvas,
    QgsMapMouseEvent,
    QgsMapToolEdit,
    QgsMapToolIdentify,
    QgsRubberBand,
    QgsSnapIndicator,
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QKeyEvent
from qgis.utils import iface
from qgis_plugin_tools.tools.i18n import tr
from qgis_plugin_tools.tools.messages import MsgBar

from segment_reshape.geometry import reshape
from segment_reshape.topology import find_related

LOGGER = logging.getLogger(__name__)


class ToolMode(Enum):
    PICK_SEGMENT = "pick_segment"
    RESHAPE = "reshape"


class SegmentReshapeTool(QgsMapToolEdit):
    def __init__(self, canvas: QgsMapCanvas) -> None:
        super().__init__(canvas)
        self.tool_mode = ToolMode.PICK_SEGMENT

        self.old_segment_rubber_band = QgsRubberBand(canvas)
        self.old_segment_rubber_band.setStrokeColor(QColor(10, 20, 150))
        self.old_segment_rubber_band.setWidth(10)

        self.new_segment_rubber_band = QgsRubberBand(canvas)
        self.new_segment_rubber_band.setStrokeColor(QColor(200, 50, 50))
        self.new_segment_rubber_band.setWidth(3)

        self.temporary_new_segment_rubber_band = QgsRubberBand(canvas)
        self.temporary_new_segment_rubber_band.setStrokeColor(QColor(200, 50, 50))
        self.temporary_new_segment_rubber_band.setLineStyle(Qt.PenStyle.DotLine)

        self.find_segment_results = find_related.CommonGeometriesResult(None, [], [])
        self.start_point = QgsPointXY()
        self.cursor_point = QgsPointXY()

        self.deactivated.connect(self._change_to_pick_location_mode)

        self._identify_tool = QgsMapToolIdentify(canvas)
        self.snap_indicator = QgsSnapIndicator(canvas)
        self.snapping_utils = canvas.snappingUtils()

    def _change_to_pick_location_mode(self) -> None:
        self.tool_mode = ToolMode.PICK_SEGMENT

        self.old_segment_rubber_band.reset()
        self.new_segment_rubber_band.reset()
        self.temporary_new_segment_rubber_band.reset()

        self.find_segment_results = find_related.CommonGeometriesResult(None, [], [])

        self.snap_indicator.setVisible(False)

    def _change_to_reshape_mode(self) -> None:
        self.tool_mode = ToolMode.RESHAPE

    def keyPressEvent(self, key_event: QKeyEvent) -> None:  # noqa: N802
        # If not ignored, event drains through to super
        key_event.ignore()
        self._handle_key_event(key_event.key())

    def canvasReleaseEvent(self, mouse_event: QgsMapMouseEvent) -> None:  # noqa: N802
        location = self.toMapCoordinates(mouse_event.pos())
        self.cursor_point = location
        self._handle_mouse_click_event(location, mouse_event.button())

    def _handle_mouse_click_event(
        self, location: QgsPointXY, mouse_button: Qt.MouseButton
    ) -> None:
        if self.tool_mode == ToolMode.PICK_SEGMENT and mouse_button == Qt.LeftButton:
            self._handle_pick_segment_left_click(location)
        elif self.tool_mode == ToolMode.RESHAPE:
            if mouse_button == Qt.LeftButton:
                self._handle_reshape_left_click(location)
            elif mouse_button == Qt.RightButton:
                self._handle_reshape_right_click()

    def _handle_pick_segment_left_click(self, location: QgsPointXY) -> None:
        common_segment, layer = self._find_common_segment(location)

        # No active layer or active layer feature found
        if layer is None:
            return

            # No common segment found
        if common_segment is None:
            MsgBar.info(
                tr("No common segment found at location"),
                tr(
                    "Features are not topologically connected "
                    "or a single vertex was clicked"
                ),
            )
        else:
            MsgBar.info(
                tr("Common segment found, changing to reshape mode"),
                success=True,
            )
            self.start_point = common_segment.startPoint()
            self._change_to_reshape_mode()
            self.old_segment_rubber_band.setToGeometry(
                QgsGeometry(common_segment), layer
            )
            self.temporary_new_segment_rubber_band.addPoint(
                QgsPointXY(self.start_point), True
            )

    def _handle_reshape_left_click(self, location: QgsPointXY) -> None:
        if self.snap_indicator.isVisible():
            location = self.snap_indicator.match().point()
            self.cursor_point = location

        self.new_segment_rubber_band.addPoint(location, True)
        self.temporary_new_segment_rubber_band.reset()
        self.temporary_new_segment_rubber_band.addPoint(location, True)

    def _handle_reshape_right_click(self) -> None:
        new_geometry = self.new_segment_rubber_band.asGeometry()

        # Reshape cancelled
        if (
            new_geometry.isEmpty()
            or self.new_segment_rubber_band.numberOfVertices() <= 1
        ):
            self._change_to_pick_location_mode()
            return

        reshape.make_reshape_edits(
            self.find_segment_results.common_parts,
            self.find_segment_results.edges,
            QgsLineString(list(new_geometry.vertices())),
        )

        self._change_to_pick_location_mode()
        self.canvas().refresh()

        MsgBar.info(
            tr("Features reshaped"),
            success=True,
        )

    def canvasMoveEvent(self, mouse_event: QgsMapMouseEvent) -> None:  # noqa: N802
        if self.tool_mode == ToolMode.RESHAPE:
            snap_match = self.snapping_utils.snapToMap(mouse_event.pos())
            self.snap_indicator.setMatch(snap_match)

        location = self.toMapCoordinates(mouse_event.pos())
        self.cursor_point = location
        self._handle_mouse_move_event(location)

    def _handle_key_event(self, key: Qt.Key) -> None:
        if self.tool_mode == ToolMode.RESHAPE:
            if key == Qt.Key_Escape:
                self._abort_reshape()
            elif key in (Qt.Key_Backspace, Qt.Key_Delete):
                self._undo_last_vertex()

    def _handle_mouse_move_event(self, location: QgsPointXY) -> None:
        if self.tool_mode == ToolMode.RESHAPE:
            if self.snap_indicator.isVisible():
                location = self.snap_indicator.match().point()
                self.cursor_point = location
            self.temporary_new_segment_rubber_band.removeLastPoint(0, True)
            self.temporary_new_segment_rubber_band.addPoint(location, True)

    def _abort_reshape(self) -> None:
        self.new_segment_rubber_band.reset()
        self.temporary_new_segment_rubber_band.reset()
        self._change_to_pick_location_mode()

        return

    def _undo_last_vertex(self) -> None:
        self.temporary_new_segment_rubber_band.reset()
        if self.new_segment_rubber_band.numberOfVertices() > 1:
            self.new_segment_rubber_band.removeLastPoint(0, True)
            self.temporary_new_segment_rubber_band.addPoint(
                self.new_segment_rubber_band.getPoint(
                    0, self.new_segment_rubber_band.numberOfVertices() - 1
                )
            )
            self.temporary_new_segment_rubber_band.addPoint(self.cursor_point)
        else:
            self.new_segment_rubber_band.reset()
            self.temporary_new_segment_rubber_band.addPoint(
                QgsPointXY(self.start_point), True
            )
            self.temporary_new_segment_rubber_band.addPoint(self.cursor_point)

    def _find_common_segment(
        self, location: QgsPointXY
    ) -> Tuple[Optional[QgsLineString], Optional[QgsVectorLayer]]:
        LOGGER.info("Calculating common segment")

        active_layer = iface.activeLayer()
        if active_layer is None:
            MsgBar.warning(tr("No active layer found"), tr("Activate a layer first"))
            return None, None

        identify_results = self._identify_tool.identify(
            geometry=QgsGeometry.fromPointXY(location),
            mode=QgsMapToolIdentify.ActiveLayer,
            layerType=QgsMapToolIdentify.VectorLayer,
        )

        feature = next((result.mFeature for result in identify_results), None)
        if not feature:
            MsgBar.warning(
                tr("Did not find any active layer feature at mouse location")
            )
            return None, None

        (
            *_,
            next_vertex_index,
            _,
        ) = feature.geometry().closestSegmentWithContext(location)

        self.find_segment_results = find_related.find_segment_to_reshape(
            active_layer, feature, (next_vertex_index - 1, next_vertex_index)
        )

        return self.find_segment_results.segment, active_layer
