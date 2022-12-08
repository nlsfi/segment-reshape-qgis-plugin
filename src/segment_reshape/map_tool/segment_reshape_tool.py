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
from contextlib import contextmanager
from enum import Enum
from typing import Iterator, Optional, Tuple, cast

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
from qgis_plugin_tools.tools.decorations import log_if_fails
from qgis_plugin_tools.tools.i18n import tr
from qgis_plugin_tools.tools.messages import MsgBar

from segment_reshape.geometry import reshape
from segment_reshape.topology import find_related

LOGGER = logging.getLogger(__name__)


@contextmanager
def _optional_identify_tool(
    tool: Optional[QgsMapToolIdentify] = None,
) -> Iterator[QgsMapToolIdentify]:
    if tool:
        yield tool
    else:
        tool = QgsMapToolIdentify(iface.mapCanvas())
        try:
            yield tool
        finally:
            tool.deleteLater()


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

    def _change_to_reshape_mode_for_geom(
        self, old_geom: QgsGeometry, layer: Optional[QgsVectorLayer] = None
    ) -> None:
        self.tool_mode = ToolMode.RESHAPE

        self.old_segment_rubber_band.setToGeometry(old_geom, layer)

        self.new_segment_rubber_band.reset()
        self.is_new_segment_reset = True

        self.temporary_new_segment_rubber_band.reset()
        start_point = self.old_segment_rubber_band.getPoint(0, 0)
        self.temporary_new_segment_rubber_band.addPoint(start_point, True)

    def keyPressEvent(self, key_event: QKeyEvent) -> None:  # noqa: N802
        # If not ignored, event drains through to super
        key_event.ignore()
        self._handle_key_event(key_event.key())

    def canvasReleaseEvent(self, mouse_event: QgsMapMouseEvent) -> None:  # noqa: N802
        location = self.toMapCoordinates(mouse_event.pos())
        self._handle_mouse_click_event(location, mouse_event.button())

    @log_if_fails
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

        if common_segment is None:
            MsgBar.info(
                tr("No common segment found at location"),
                tr(
                    "Features are not topologically connected "
                    "or a single vertex was clicked"
                ),
            )
            return

        MsgBar.info(
            tr("Common segment found, changing to reshape mode"),
            success=True,
        )
        self._change_to_reshape_mode_for_geom(QgsGeometry(common_segment), layer)

    def _handle_reshape_left_click(self, location: QgsPointXY) -> None:
        if self.snap_indicator.isVisible():
            location = self.snap_indicator.match().point()

        self.new_segment_rubber_band.addPoint(location, True)
        if self.is_new_segment_reset:
            # Adding a point to new rubberband adds actually 2 points.
            # Remove the second since it messes the undo logic
            self.new_segment_rubber_band.removeLastPoint()
        self.is_new_segment_reset = False

        # Move only the first point of the temp rubber band
        self.temporary_new_segment_rubber_band.movePoint(0, location)

    def _handle_reshape_right_click(self) -> None:
        # No points digitized => Cancel reshape
        if self.new_segment_rubber_band.numberOfVertices() == 0:
            self._change_to_pick_location_mode()
            return

        new_geometry = self.new_segment_rubber_band.asGeometry()
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

            # Set the last point of temp rubber band to track cursor location
            self.temporary_new_segment_rubber_band.movePoint(location)

    def _abort_reshape(self) -> None:
        self._change_to_pick_location_mode()

    def _undo_last_vertex(self) -> None:
        self.new_segment_rubber_band.removeLastPoint()
        number_of_vertices = self.new_segment_rubber_band.numberOfVertices()
        if number_of_vertices >= 1:
            previous_point = self.new_segment_rubber_band.getPoint(
                0, number_of_vertices - 1
            )
        else:
            previous_point = self.old_segment_rubber_band.getPoint(0, 0)

        # Move the first point of the temp rubber band
        self.temporary_new_segment_rubber_band.movePoint(0, previous_point)

    def _find_common_segment(
        self, location: QgsPointXY
    ) -> Tuple[Optional[QgsLineString], Optional[QgsVectorLayer]]:
        LOGGER.info("Calculating common segment")

        active_layer = iface.activeLayer()
        if active_layer is None:
            MsgBar.warning(tr("No active layer found"), tr("Activate a layer first"))
            return None, None

        results = SegmentReshapeTool.find_common_segment_at_location(
            location, self._identify_tool
        )

        if results is None:
            MsgBar.warning(
                tr("Did not find any active layer feature at mouse location")
            )
            return None, None

        self.find_segment_results = results

        return self.find_segment_results.segment, active_layer

    @staticmethod
    def find_common_segment_at_location(
        location: QgsPointXY, identify_tool: Optional[QgsMapToolIdentify] = None
    ) -> Optional[find_related.CommonGeometriesResult]:
        with _optional_identify_tool(identify_tool) as tool:
            identify_results = tool.identify(
                geometry=QgsGeometry.fromPointXY(location),
                mode=QgsMapToolIdentify.IdentifyMode.ActiveLayer,
                layerType=QgsMapToolIdentify.Type.VectorLayer,
            )

        if len(identify_results) < 1:
            return None

        identify_result = identify_results[0]
        layer, feature = (
            cast(QgsVectorLayer, identify_result.mLayer),
            identify_result.mFeature,
        )

        (
            *_,
            next_vertex_index,
            _,
        ) = feature.geometry().closestSegmentWithContext(location)

        return find_related.find_segment_to_reshape(
            layer, feature, (next_vertex_index - 1, next_vertex_index)
        )
