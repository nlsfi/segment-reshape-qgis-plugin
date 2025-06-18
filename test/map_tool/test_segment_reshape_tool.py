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

from typing import TYPE_CHECKING, Callable, Optional
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture
from pytest_qgis import QgisInterface, QgsMapCanvas
from qgis.core import (
    QgsAnnotationLayer,
    QgsFeature,
    QgsGeometry,
    QgsLineString,
    QgsPointLocator,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
)
from qgis.gui import QgsMapMouseEvent, QgsMapToolIdentify
from qgis.PyQt.QtCore import QEvent, QPoint, Qt
from qgis.PyQt.QtGui import QKeyEvent
from segment_reshape.geometry import reshape
from segment_reshape.map_tool.segment_reshape_tool import SegmentReshapeTool, ToolMode

if TYPE_CHECKING:
    from typing import Protocol

    class MouseEventFactoryType(Protocol):
        def __call__(
            self,
            location: QgsPointXY,
            mouse_event_type: QEvent.Type,
            mouse_button: Optional[Qt.MouseButton] = Qt.NoButton,
        ) -> QgsMapMouseEvent:
            ...


MOUSE_LOCATION = QgsPointXY(1.5, 1.5)


@pytest.fixture()
def mouse_event_factory(
    qgis_canvas: QgsMapCanvas,
) -> "MouseEventFactoryType":
    def mouse_event_for_location(
        location: QgsPointXY,
        mouse_event_type: QEvent.Type,
        mouse_button: Optional[Qt.MouseButton] = None,
    ) -> QgsMapMouseEvent:
        mouse_button = mouse_button or Qt.NoButton
        event = QgsMapMouseEvent(
            qgis_canvas,
            mouse_event_type,
            QPoint(0, 0),
            mouse_button,
        )
        event.mapPoint = lambda: location  # type: ignore[method-assign]
        event.mapPointMatch = lambda: QgsPointLocator.Match()  # type: ignore[method-assign]
        return event

    return mouse_event_for_location


@pytest.fixture()
def _add_layer(
    qgis_canvas: QgsMapCanvas,
) -> None:
    layer = QgsAnnotationLayer(
        "test",
        QgsAnnotationLayer.LayerOptions(QgsProject.instance().transformContext()),
    )
    QgsProject.instance().addMapLayers([layer])
    qgis_canvas.setLayers([layer])
    qgis_canvas.setCurrentLayer(layer)


def _create_identify_result(
    identified_features: list[tuple[QgsFeature, QgsVectorLayer]]
) -> list[QgsMapToolIdentify.IdentifyResult]:
    results = []

    for feature, layer in identified_features:
        # using the actual QgsMapToolIdentify.IdentifyResult causes
        # fatal exceptions, mock probably is sufficient for testing
        results.append(
            MagicMock(**{"mLayer": layer, "mFeature": feature})  # noqa: PIE804
        )

    return results


@pytest.fixture()
def map_tool(qgis_canvas: QgsMapCanvas, qgis_new_project: None) -> SegmentReshapeTool:
    tool = SegmentReshapeTool(qgis_canvas)
    qgis_canvas.setMapTool(tool)
    return tool


def test_change_to_pick_location_mode_resets_rubberbands(map_tool: SegmentReshapeTool):
    map_tool._change_to_reshape_mode_for_geom(
        QgsGeometry.fromWkt("LINESTRING(0 0, 1 1)")
    )

    map_tool._change_to_pick_location_mode()

    assert map_tool._tool_mode == ToolMode.PICK_SEGMENT
    assert map_tool.old_segment_rubber_band.asGeometry().isEmpty()
    assert map_tool.start_point_indicator_rubber_band.asGeometry().isEmpty()


def test_pressing_esc_in_reshape_mode_aborts_reshape(map_tool: SegmentReshapeTool):
    map_tool._change_to_reshape_mode_for_geom(
        QgsGeometry.fromWkt("LINESTRING(0 0, 1 1, 2 2, 3 3, 4 4, 5 5)"), None
    )
    assert map_tool._tool_mode == ToolMode.RESHAPE

    escape_press = QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
    map_tool.keyPressEvent(escape_press)

    assert map_tool._tool_mode == ToolMode.PICK_SEGMENT
    assert map_tool.old_segment_rubber_band.asGeometry().isEmpty()
    assert map_tool.start_point_indicator_rubber_band.asGeometry().isEmpty()


def test_change_to_change_to_reshape_mode_toggles_pick_mode_off(
    map_tool: SegmentReshapeTool,
):
    map_tool._tool_mode = ToolMode.PICK_SEGMENT

    old_geom = QgsGeometry.fromWkt("LINESTRING(0 0, 1 1)")
    map_tool._change_to_reshape_mode_for_geom(old_geom)

    assert map_tool._tool_mode == ToolMode.RESHAPE


def test_left_mouse_click_in_pick_mode_does_nothing_if_active_layer_or_feature_not_found(
    map_tool: SegmentReshapeTool,
    mocker: MockerFixture,
    mouse_event_factory: "MouseEventFactoryType",
):
    map_tool._change_to_pick_location_mode()
    m_find_common_segment = mocker.patch.object(
        map_tool, "_find_common_segment", return_value=(None, None), autospec=True
    )

    map_release = mouse_event_factory(
        MOUSE_LOCATION,
        QEvent.MouseButtonRelease,
        Qt.LeftButton,
    )
    map_tool.canvasReleaseEvent(map_release)

    m_find_common_segment.assert_called_once()
    assert map_tool._tool_mode == ToolMode.PICK_SEGMENT


def test_left_mouse_click_in_pick_mode_does_nothing_if_common_segment_not_found(
    map_tool: SegmentReshapeTool,
    mocker: MockerFixture,
    mouse_event_factory: "MouseEventFactoryType",
):
    map_tool._change_to_pick_location_mode()

    m_find_common_segment = mocker.patch.object(
        map_tool,
        "_find_common_segment",
        return_value=(None, QgsVectorLayer("test")),
        autospec=True,
    )

    map_release = mouse_event_factory(
        MOUSE_LOCATION,
        QEvent.MouseButtonRelease,
        Qt.LeftButton,
    )
    map_tool.canvasReleaseEvent(map_release)

    m_find_common_segment.assert_called_once()

    assert map_tool._tool_mode == ToolMode.PICK_SEGMENT


def test_left_mouse_click_in_pick_mode_starts_reshape_mode_if_common_segment_is_found(
    map_tool: SegmentReshapeTool,
    mocker: MockerFixture,
    mouse_event_factory: "MouseEventFactoryType",
):
    map_tool._change_to_pick_location_mode()
    assert map_tool.old_segment_rubber_band.asGeometry().isEmpty()
    assert map_tool.start_point_indicator_rubber_band.asGeometry().isEmpty()

    m_find_common_segment = mocker.patch.object(
        map_tool,
        "_find_common_segment",
        return_value=(QgsLineString([(0, 0), (1, 1)]), QgsVectorLayer("test")),
        autospec=True,
    )

    map_release = mouse_event_factory(
        MOUSE_LOCATION,
        QEvent.MouseButtonRelease,
        Qt.LeftButton,
    )
    map_tool.canvasReleaseEvent(map_release)

    m_find_common_segment.assert_called_once()

    assert map_tool._tool_mode == ToolMode.RESHAPE

    assert map_tool.old_segment_rubber_band.asGeometry().isGeosEqual(
        QgsGeometry.fromWkt("LineString (0 0, 1 1)")
    )
    assert (
        map_tool.start_point_indicator_rubber_band.asGeometry().asWkt()
        == "LineString (0 0, 0 0)"
    )


@pytest.mark.usefixtures("_add_layer")
def test_left_mouse_click_in_reshape_mode_adds_points_to_maptool(
    mocker: MockerFixture,
    qgis_canvas: QgsMapCanvas,
    mouse_event_factory: "MouseEventFactoryType",
):
    m_make_reshape_edits = mocker.patch.object(
        reshape, "make_reshape_edits", autospec=True
    )

    map_tool = SegmentReshapeTool(qgis_canvas)
    qgis_canvas.setMapTool(map_tool)

    old_geom = QgsGeometry.fromWkt("LINESTRING(0 0, 1 1)")
    map_tool._change_to_reshape_mode_for_geom(old_geom)

    map_release = mouse_event_factory(
        MOUSE_LOCATION,
        QEvent.MouseButtonRelease,
        Qt.LeftButton,
    )
    map_tool.canvasReleaseEvent(map_release)

    assert map_tool.captureCurve().curveToLine().asWkt() == "LineString (1.5 1.5)"

    m_make_reshape_edits.assert_not_called()


@pytest.mark.usefixtures("_add_layer")
@pytest.mark.parametrize(
    ("points_to_remove", "expected_new"),
    [
        (1, "LineString (0 0, 1 1)"),
        (2, "LineString (0 0)"),
        (3, "LineString EMPTY"),
        (6, "LineString EMPTY"),
    ],
    ids=[
        "undo-few-last",
        "undo-so-that-one-left",
        "undo-first-point_temp-should-change-to-old_geom-start",
        "undo-when-no-points-left_temp-should-change-to-old_geom-start",
    ],
)
def test_undo_add_vertex_should_update_new(
    # map_tool: SegmentReshapeTool,
    qgis_canvas: QgsMapCanvas,
    mouse_event_factory: "MouseEventFactoryType",
    points_to_remove: int,
    expected_new: str,
):
    map_tool = SegmentReshapeTool(qgis_canvas)
    qgis_canvas.setMapTool(map_tool)
    old_geom = QgsGeometry.fromWkt("LINESTRING(1 0, 2 0, 3 0)")
    map_tool._change_to_reshape_mode_for_geom(old_geom)

    # Add new line
    for new_point in [(0, 0), (1, 1), (2, 2)]:
        map_tool.addVertex(QgsPointXY(*new_point))

    assert map_tool.captureCurve().curveToLine().asWkt() == "LineString (0 0, 1 1, 2 2)"

    # Undo n times
    undo_key_event = QKeyEvent(QEvent.KeyPress, Qt.Key_Backspace, Qt.NoModifier)
    for _ in range(points_to_remove):
        map_tool.keyPressEvent(undo_key_event)

    assert map_tool._tool_mode == ToolMode.RESHAPE
    assert map_tool.captureCurve().curveToLine().asWkt() == expected_new
    assert map_tool.old_segment_rubber_band.asGeometry().asWkt() == old_geom.asWkt()


def test_start_point_indicator_rubberband(
    # map_tool: SegmentReshapeTool,
    qgis_canvas: QgsMapCanvas,
    mouse_event_factory: "MouseEventFactoryType",
):
    map_tool = SegmentReshapeTool(qgis_canvas)
    qgis_canvas.setMapTool(map_tool)
    old_geom = QgsGeometry.fromWkt("LINESTRING(1 0, 2 0, 3 0)")
    map_tool._change_to_reshape_mode_for_geom(old_geom)

    # Move cursor to move temp rubberband end point
    mouse_move_event = mouse_event_factory(QgsPointXY(2, 3), QEvent.MouseMove)
    map_tool.canvasMoveEvent(mouse_move_event)

    assert map_tool.start_point_indicator_rubber_band.isVisible()
    assert (
        map_tool.start_point_indicator_rubber_band.asGeometry().asWkt()
        == "LineString (1 0, 2 3)"
    )

    map_tool.addVertex(QgsPointXY(1, 1))

    assert not map_tool.start_point_indicator_rubber_band.isVisible()

    undo_key_event = QKeyEvent(QEvent.KeyPress, Qt.Key_Backspace, Qt.NoModifier)
    map_tool.keyPressEvent(undo_key_event)

    mouse_move_event = mouse_event_factory(QgsPointXY(4, 3), QEvent.MouseMove)
    map_tool.canvasMoveEvent(mouse_move_event)
    assert map_tool.start_point_indicator_rubber_band.isVisible()
    assert (
        map_tool.start_point_indicator_rubber_band.asGeometry().asWkt()
        == "LineString (1 0, 4 3)"
    )


def test_right_mouse_click_in_reshape_mode_changes_only_to_pick_mode_if_edited_geometry_is_empty(
    map_tool: SegmentReshapeTool,
    mocker: MockerFixture,
    mouse_event_factory: "MouseEventFactoryType",
):
    old_geom = QgsGeometry.fromWkt("LINESTRING(0 0, 1 1)")
    map_tool._change_to_reshape_mode_for_geom(old_geom)

    m_change_to_pick_location_mode = mocker.patch.object(
        map_tool, "_change_to_pick_location_mode", autospec=True
    )

    m_make_reshape_edits = mocker.patch.object(
        reshape, "make_reshape_edits", autospec=True
    )

    right_click = mouse_event_factory(
        QgsPointXY(1, 1), QEvent.MouseButtonRelease, Qt.RightButton
    )
    map_tool.cadCanvasReleaseEvent(right_click)

    m_change_to_pick_location_mode.assert_called_once()
    m_make_reshape_edits.assert_not_called()


def test_right_mouse_click_in_reshape_mode_calls_reshape_if_edited_geometry_is_not_empty(
    map_tool: SegmentReshapeTool,
    mocker: MockerFixture,
    mouse_event_factory: "MouseEventFactoryType",
):
    old_geom = QgsGeometry.fromWkt("LINESTRING(0 0, 1 1)")
    map_tool._change_to_reshape_mode_for_geom(old_geom)

    m_change_to_pick_location_mode = mocker.patch.object(
        map_tool, "_change_to_pick_location_mode", autospec=True
    )
    m_make_reshape_edits = mocker.patch.object(
        reshape, "make_reshape_edits", autospec=True
    )

    left_click = mouse_event_factory(
        QgsPointXY(1, 1), QEvent.MouseButtonRelease, Qt.LeftButton
    )
    # Add point to rubberband
    map_tool.canvasReleaseEvent(left_click)

    # Test
    right_click = mouse_event_factory(
        QgsPointXY(1, 1), QEvent.MouseButtonRelease, Qt.RightButton
    )
    map_tool.cadCanvasReleaseEvent(right_click)

    m_change_to_pick_location_mode.assert_called_once()
    m_make_reshape_edits.assert_called_once()


@pytest.mark.usefixtures("_use_topological_editing")
def test_find_common_segment_should_return_shared_segment(
    qgis_iface: QgisInterface,
    map_tool: SegmentReshapeTool,
    mocker: MockerFixture,
    preset_features_layer_factory: Callable[
        [str, list[str]], tuple[QgsVectorLayer, list[QgsFeature]]
    ],
):
    layer, (base_feature, *_) = preset_features_layer_factory(
        "l1",
        [
            "LINESTRING(0 0, 1 1, 2 2, 3 3)",  # base
            "LINESTRING(1 0, 1 1, 2 2, 2 0)",  # partly common
            "LINESTRING(0 2, 2 2, 1 1, 0 1)",  # partly common reversed
            "LINESTRING(0 0, 1 1)",  # edge start
            "LINESTRING(2 2, 3 3)",  # edge end
        ],
    )

    QgsProject.instance().addMapLayer(layer)
    qgis_iface.setActiveLayer(layer)

    results = _create_identify_result(
        [
            (feature, layer)
            for feature in layer.getFeatures()
            if feature.id() != base_feature.id()
        ]
    )
    mocker.patch.object(QgsMapToolIdentify, "identify", return_value=results)

    segment, segment_layer = map_tool._find_common_segment(MOUSE_LOCATION)

    assert segment_layer == layer

    assert QgsGeometry(segment).isGeosEqual(QgsGeometry.fromWkt("LINESTRING(1 1, 2 2)"))


@pytest.mark.usefixtures("_use_topological_editing")
def test_find_common_segment_should_return_shared_segment2(
    qgis_iface: QgisInterface,
    map_tool: SegmentReshapeTool,
    mocker: MockerFixture,
    preset_features_layer_factory: Callable[
        [str, list[str]], tuple[QgsVectorLayer, list[QgsFeature]]
    ],
):
    layer, (base_feature, *_) = preset_features_layer_factory(
        "l1",
        [
            "LINESTRING(0 0, 1 1, 2 2, 3 3)",
        ],
    )

    QgsProject.instance().addMapLayer(layer)
    QgsProject.instance().layerTreeRoot().findLayer(layer).setItemVisibilityChecked(
        False
    )
    qgis_iface.setActiveLayer(layer)

    results = _create_identify_result(
        [
            (feature, layer)
            for feature in layer.getFeatures()
            if feature.id() != base_feature.id()
        ]
    )
    mocker.patch.object(QgsMapToolIdentify, "identify", return_value=results)

    result = map_tool._find_common_segment(MOUSE_LOCATION)
    assert result == (None, None)
