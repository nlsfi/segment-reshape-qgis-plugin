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
from qgis.PyQt.QtGui import QColor
from qgis.utils import iface
from qgis_plugin_tools.tools.i18n import tr
from qgis_plugin_tools.tools.messages import MsgBar

from segment_reshape.geometry import reshape
from segment_reshape.topology import find_related

LOGGER = logging.getLogger(__name__)


class SegmentReshapeTool(QgsMapToolEdit):
    def __init__(self, canvas: QgsMapCanvas) -> None:
        super().__init__(canvas)
        self.pick_location_mode = True
        self.reshape_mode = False

        self.old_segment_rubber_band = QgsRubberBand(canvas)
        self.old_segment_rubber_band.setStrokeColor(QColor(10, 20, 150))
        self.old_segment_rubber_band.setWidth(10)

        self.new_segment_rubber_band = QgsRubberBand(canvas)
        self.new_segment_rubber_band.setStrokeColor(QColor(200, 50, 50))
        self.new_segment_rubber_band.setWidth(3)

        self.temporary_new_segment_rubber_band = QgsRubberBand(canvas)
        self.temporary_new_segment_rubber_band.setStrokeColor(QColor(200, 50, 50))
        self.temporary_new_segment_rubber_band.setLineStyle(Qt.PenStyle.DotLine)

        self.find_segment_results: find_related.CommonGeometriesResult = (None, [], [])

        self.deactivated.connect(self._change_to_pick_location_mode)

        self._identify_tool = QgsMapToolIdentify(canvas)
        self.snap_indicator = QgsSnapIndicator(canvas)
        self.snapping_utils = canvas.snappingUtils()

    def _change_to_pick_location_mode(self) -> None:
        self.pick_location_mode = True
        self.reshape_mode = False

        self.old_segment_rubber_band.reset()
        self.new_segment_rubber_band.reset()
        self.temporary_new_segment_rubber_band.reset()

        self.find_segment_results = (None, [], [])

        self.snap_indicator.setVisible(False)

    def _change_to_reshape_mode(self) -> None:
        self.pick_location_mode = False
        self.reshape_mode = True

    def canvasReleaseEvent(self, mouse_event: QgsMapMouseEvent) -> None:  # noqa: N802
        location = self.toMapCoordinates(mouse_event.pos())
        self._handle_mouse_click_event(location, mouse_event.button())

    def canvasMoveEvent(self, mouse_event: QgsMapMouseEvent) -> None:  # noqa: N802
        if self.reshape_mode:
            snap_match = self.snapping_utils.snapToMap(mouse_event.pos())
            self.snap_indicator.setMatch(snap_match)

        location = self.toMapCoordinates(mouse_event.pos())
        self._handle_mouse_move_event(location)

    def _handle_mouse_click_event(
        self, location: QgsPointXY, mouse_button: Qt.MouseButton
    ) -> None:
        if mouse_button == Qt.LeftButton and self.pick_location_mode is True:
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
                start_point = common_segment.startPoint()
                self._change_to_reshape_mode()
                self.old_segment_rubber_band.setToGeometry(
                    QgsGeometry(common_segment), layer
                )
                self.temporary_new_segment_rubber_band.addPoint(
                    QgsPointXY(start_point), True
                )

        elif mouse_button == Qt.LeftButton and self.reshape_mode is True:
            if self.snap_indicator.isVisible():
                location = self.snap_indicator.match().point()

            self.new_segment_rubber_band.addPoint(location, True)
            self.temporary_new_segment_rubber_band.reset()
            self.temporary_new_segment_rubber_band.addPoint(location, True)

        elif mouse_button == Qt.RightButton and self.reshape_mode is True:
            new_geometry = self.new_segment_rubber_band.asGeometry()

            # Reshape cancelled
            if new_geometry.isEmpty():
                self._change_to_pick_location_mode()
                return

            _, common_parts, edges = self.find_segment_results

            reshape.make_reshape_edits(
                common_parts, edges, QgsLineString(list(new_geometry.vertices()))
            )

            self._change_to_pick_location_mode()
            self.canvas().refresh()

            MsgBar.info(
                tr("Features reshaped"),
                success=True,
            )

    def _handle_mouse_move_event(self, location: QgsPointXY) -> None:
        if self.reshape_mode is True:
            if self.snap_indicator.isVisible():
                location = self.snap_indicator.match().point()
            self.temporary_new_segment_rubber_band.removeLastPoint(0, True)
            self.temporary_new_segment_rubber_band.addPoint(location, True)

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

        try:
            feature = [result.mFeature for result in identify_results][0]
        except IndexError:
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
            active_layer, feature, (next_vertex_index, next_vertex_index - 1)
        )

        return self.find_segment_results[0], active_layer
