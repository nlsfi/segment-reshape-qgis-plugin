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
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from enum import Enum, IntEnum
from typing import (
    TYPE_CHECKING,
    Optional,
    Union,
    cast,
    overload,
)

from qgis.core import (
    QgsApplication,
    QgsGeometry,
    QgsLineString,
    QgsPoint,
    QgsPointLocator,
    QgsPointXY,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.gui import (
    QgisInterface,
    QgsAbstractMapToolHandler,
    QgsMapCanvas,
    QgsMapMouseEvent,
    QgsMapToolCapture,
    QgsMapToolIdentify,
    QgsRubberBand,
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QKeyEvent
from qgis.PyQt.QtWidgets import QApplication
from qgis.utils import iface as iface_
from qgis_plugin_tools.tools.decorations import log_if_fails
from qgis_plugin_tools.tools.i18n import tr
from qgis_plugin_tools.tools.messages import MsgBar

from segment_reshape.geometry import reshape
from segment_reshape.topology import find_related

if TYPE_CHECKING:
    from qgis.core import QgsMapLayer
    from qgis.PyQt.QtWidgets import QAction

iface = cast(QgisInterface, iface_)

LOGGER = logging.getLogger(__name__)


class CoordinateTransformationError(Exception):
    ...


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


@contextmanager
def override_cursor(cursor: Qt.CursorShape) -> Generator[None, None, None]:
    QApplication.setOverrideCursor(cursor)
    try:
        yield
    finally:
        QApplication.restoreOverrideCursor()


COLOR_BLUE = QColor(10, 20, 150)
COLOR_GREY = QColor(211, 211, 211)


class ToolMode(Enum):
    PICK_SEGMENT = "pick_segment"
    RESHAPE = "reshape"


class AddVertexReturn(IntEnum):
    Success = 0
    TransformationError = 2


class SegmentReshapeToolHandler(QgsAbstractMapToolHandler):
    def __init__(self, tool: "SegmentReshapeTool", action: "QAction") -> None:
        super().__init__(tool, action)

    def isCompatibleWithLayer(  # noqa: N802
        self, layer: "QgsMapLayer", context: QgsAbstractMapToolHandler.Context
    ) -> bool:
        return isinstance(layer, QgsVectorLayer) and layer.geometryType() in (
            QgsWkbTypes.GeometryType.PolygonGeometry,
            QgsWkbTypes.GeometryType.LineGeometry,
        )


class SegmentReshapeTool(QgsMapToolCapture):
    _tool_mode: ToolMode

    def __init__(self, canvas: QgsMapCanvas) -> None:
        super().__init__(
            canvas, iface.cadDockWidget(), QgsMapToolCapture.CaptureMode.CaptureLine
        )

        self.old_segment_rubber_band = QgsRubberBand(canvas)
        self.old_segment_rubber_band.setStrokeColor(COLOR_BLUE)
        self.old_segment_rubber_band.setWidth(10)

        self.start_point_indicator_rubber_band = QgsRubberBand(canvas)
        self.start_point_indicator_rubber_band.setStrokeColor(COLOR_GREY)
        self.start_point_indicator_rubber_band.setLineStyle(Qt.PenStyle.DotLine)

        self.find_segment_results = find_related.CommonGeometriesResult(None, [], [])

        self._identify_tool = QgsMapToolIdentify(canvas)

    def activate(self) -> None:
        self._change_to_pick_location_mode()
        super().activate()

    def deactivate(self) -> None:
        self.old_segment_rubber_band.hide()
        self.start_point_indicator_rubber_band.hide()

        return super().deactivate()

    def _change_to_pick_location_mode(self) -> None:
        self._tool_mode = ToolMode.PICK_SEGMENT
        self.setCursor(Qt.CrossCursor)
        self.setAutoSnapEnabled(False)
        self.setAdvancedDigitizingAllowed(False)

        self.old_segment_rubber_band.reset()
        self.start_point_indicator_rubber_band.reset()

        self.find_segment_results = find_related.CommonGeometriesResult(None, [], [])

    def _change_to_reshape_mode_for_geom(
        self, old_geom: QgsGeometry, layer: Optional[QgsVectorLayer] = None
    ) -> None:
        self._tool_mode = ToolMode.RESHAPE
        self.setCursor(
            QgsApplication.getThemeCursor(QgsApplication.Cursor.CapturePoint)
        )
        self.setAutoSnapEnabled(True)
        self.setAdvancedDigitizingAllowed(True)

        self._common_segment_to_reshape = old_geom
        self._active_layer = layer

        self.old_segment_rubber_band.setToGeometry(old_geom, layer)

        self.start_point_indicator_rubber_band.reset()
        self.start_point_indicator_rubber_band.show()
        start_point = self.old_segment_rubber_band.getPoint(0, 0)
        self.start_point_indicator_rubber_band.addPoint(start_point, True)

    def keyPressEvent(self, key_event: QKeyEvent) -> None:  # noqa: N802
        point_count = self.size()
        super().keyPressEvent(key_event)  # handle normal undo and cancel procedures
        if self._tool_mode == ToolMode.RESHAPE:
            if key_event.key() == Qt.Key_Escape:
                self._change_to_pick_location_mode()
            elif (
                key_event.key() in (Qt.Key_Delete, Qt.Key_Backspace)
                and point_count == 1
            ):
                # self.undo() resists to undo the first point so force back to initial
                # reshape mode
                self.stopCapturing()
                self._change_to_reshape_mode_for_geom(
                    self._common_segment_to_reshape, self._active_layer
                )

    @overload
    def addVertex(self, point: QgsPointXY) -> int:
        ...

    @overload
    def addVertex(
        self, mapPoint: QgsPointXY, match: QgsPointLocator.Match  # noqa: N803
    ) -> int:
        ...

    def addVertex(self, *args, **kwargs) -> int:  # noqa: N802
        result = super().addVertex(*args, **kwargs)
        self.start_point_indicator_rubber_band.hide()
        return result

    @log_if_fails
    def canvasReleaseEvent(self, mouse_event: QgsMapMouseEvent) -> None:  # noqa: N802
        if self._tool_mode == ToolMode.PICK_SEGMENT:
            if mouse_event.button() == Qt.LeftButton:
                self._handle_pick_segment_left_click(mouse_event.mapPoint())
            return
        super().canvasReleaseEvent(mouse_event)

    def cadCanvasReleaseEvent(  # noqa: N802
        self, mouse_event: QgsMapMouseEvent
    ) -> None:
        """Override of the QgsMapToolAdvancedDigitizing.cadCanvasReleaseEvent

        This will receive adapted events from the cad system whenever a
        canvasReleaseEvent is triggered and it's not hidden by the cad's
        construction mode.

        Args:
            mouse_event (QgsMapMouseEvent): Mouse events prepared by the cad system
        """

        if self._tool_mode == ToolMode.RESHAPE:
            if mouse_event.button() == Qt.LeftButton:
                result = self.addVertex(
                    mouse_event.mapPoint(), mouse_event.mapPointMatch()
                )
                if result == AddVertexReturn.TransformationError:
                    MsgBar.warning(
                        tr("Cannot transform the point to the layers coordinate system")
                    )
                    return
                self.startCapturing()
            elif mouse_event.button() == Qt.RightButton:
                self._handle_reshape_right_click()

    def cadCanvasMoveEvent(self, mouse_event: QgsMapMouseEvent) -> None:  # noqa: N802
        if self._tool_mode == ToolMode.RESHAPE and self.size() == 0:
            self.start_point_indicator_rubber_band.movePoint(mouse_event.mapPoint())
        return super().cadCanvasMoveEvent(mouse_event)

    def _handle_pick_segment_left_click(self, location: QgsPointXY) -> None:
        with override_cursor(Qt.WaitCursor):
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

    def _handle_reshape_right_click(self) -> None:
        with override_cursor(Qt.WaitCursor):
            new_geometry = self.captureCurve().curveToLine()
            self.stopCapturing()

            if new_geometry.isEmpty():
                self._change_to_pick_location_mode()
                return

            new_geometry.addZValue(self.defaultZValue())
            reshape_geom: Union[QgsPoint, QgsLineString] = new_geometry
            if new_geometry.numPoints() == 1:
                reshape_geom = new_geometry.pointN(0)

            reshape.make_reshape_edits(
                self.find_segment_results.common_parts,
                self.find_segment_results.edges,
                reshape_geom,
            )

            self._change_to_pick_location_mode()
            self.canvas().refresh()

    def _find_common_segment(
        self, location: QgsPointXY
    ) -> tuple[Optional[QgsLineString], Optional[QgsVectorLayer]]:
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
