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

from typing import Callable, List, Tuple
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture
from pytest_qgis import QgisInterface
from qgis.core import (
    QgsFeature,
    QgsGeometry,
    QgsLineString,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
)
from qgis.gui import QgsMapToolIdentify
from qgis.PyQt.QtCore import Qt

from segment_reshape.geometry import reshape
from segment_reshape.map_tool.segment_reshape_tool import SegmentReshapeTool

MOUSE_LOCATION = QgsPointXY(1.5, 1.5)


def _create_identify_result(
    identified_features: List[Tuple[QgsFeature, QgsVectorLayer]]
) -> List[QgsMapToolIdentify.IdentifyResult]:
    results = []

    for feature, layer in identified_features:
        # using the actual QgsMapToolIdentify.IdentifyResult causes
        # fatal exceptions, mock probably is sufficient for testing
        results.append(
            MagicMock(**{"mLayer": layer, "mFeature": feature})  # noqa: PIE804
        )

    return results


@pytest.fixture()
def map_tool(qgis_iface: QgisInterface, qgis_new_project: None) -> SegmentReshapeTool:
    return SegmentReshapeTool(qgis_iface.mapCanvas())


def test_change_to_pick_location_mode_resets_rubberbands(map_tool: SegmentReshapeTool):
    map_tool.old_segment_rubber_band.setToGeometry(
        QgsGeometry.fromWkt("LINESTRING(0 0, 1 1)")
    )
    map_tool.new_segment_rubber_band.setToGeometry(
        QgsGeometry.fromWkt("LINESTRING(0 0, 1 1)")
    )
    map_tool.temporary_new_segment_rubber_band.setToGeometry(
        QgsGeometry.fromWkt("LINESTRING(0 0, 1 1)")
    )
    map_tool.pick_location_mode = False
    map_tool.reshape_mode = True

    map_tool._change_to_pick_location_mode()

    assert map_tool.pick_location_mode is True
    assert map_tool.reshape_mode is False
    assert map_tool.old_segment_rubber_band.asGeometry().isEmpty()
    assert map_tool.new_segment_rubber_band.asGeometry().isEmpty()
    assert map_tool.temporary_new_segment_rubber_band.asGeometry().isEmpty()


def test_pressing_esc_in_reshape_mode_aborts_reshape(map_tool: SegmentReshapeTool):
    map_tool.old_segment_rubber_band.setToGeometry(
        QgsGeometry.fromWkt("LINESTRING(0 0, 1 1, 2 2, 3 3, 4 4, 5 5)")
    )
    map_tool.new_segment_rubber_band.setToGeometry(
        QgsGeometry.fromWkt("LINESTRING(0 0, 1 1, 2 2, 3 3, 4 4, 5 5)")
    )
    map_tool.temporary_new_segment_rubber_band.setToGeometry(
        QgsGeometry.fromWkt("LINESTRING(0 0, 1 1, 2 2, 3 3, 4 4, 5 5)")
    )
    map_tool.pick_location_mode = False
    map_tool.reshape_mode = True

    map_tool._handle_key_event(Qt.Key_Escape)

    assert map_tool.pick_location_mode is True
    assert map_tool.reshape_mode is False
    assert map_tool.old_segment_rubber_band.asGeometry().isEmpty()
    assert map_tool.new_segment_rubber_band.asGeometry().isEmpty()
    assert map_tool.temporary_new_segment_rubber_band.asGeometry().isEmpty()


def test_pressing_esc_in_reshape_mode_with_empty_rubberbands_aborts_reshape(
    map_tool: SegmentReshapeTool,
):
    map_tool.old_segment_rubber_band.reset()
    map_tool.new_segment_rubber_band.reset()
    map_tool.temporary_new_segment_rubber_band.reset()
    map_tool.pick_location_mode = False
    map_tool.reshape_mode = True

    map_tool._handle_key_event(Qt.Key_Escape)

    assert map_tool.old_segment_rubber_band.asGeometry().isEmpty()
    assert map_tool.new_segment_rubber_band.asGeometry().isEmpty()
    assert map_tool.temporary_new_segment_rubber_band.asGeometry().isEmpty()


def test_change_to_change_to_reshape_mode_toggles_pick_mode_off(
    map_tool: SegmentReshapeTool,
):
    map_tool.pick_location_mode = True
    map_tool.reshape_mode = False

    map_tool._change_to_reshape_mode()

    assert map_tool.pick_location_mode is False
    assert map_tool.reshape_mode is True


def test_left_mouse_click_in_pick_mode_does_nothing_if_active_layer_or_feature_not_found(
    map_tool: SegmentReshapeTool,
    mocker: MockerFixture,
):
    map_tool._change_to_pick_location_mode()

    m_find_common_segment = mocker.patch.object(
        map_tool, "_find_common_segment", return_value=(None, None), autospec=True
    )

    map_tool._handle_mouse_click_event(MOUSE_LOCATION, Qt.LeftButton)

    m_find_common_segment.assert_called_once()
    assert map_tool.pick_location_mode is True
    assert map_tool.reshape_mode is False


def test_left_mouse_click_in_pick_mode_does_nothing_if_common_segment_not_found(
    map_tool: SegmentReshapeTool,
    mocker: MockerFixture,
):
    map_tool._change_to_pick_location_mode()

    m_find_common_segment = mocker.patch.object(
        map_tool,
        "_find_common_segment",
        return_value=(None, QgsVectorLayer("test")),
        autospec=True,
    )

    map_tool._handle_mouse_click_event(MOUSE_LOCATION, Qt.LeftButton)

    m_find_common_segment.assert_called_once()
    assert map_tool.pick_location_mode is True
    assert map_tool.reshape_mode is False


def test_left_mouse_click_in_pick_mode_starts_reshape_mode_if_common_segment_is_found(
    map_tool: SegmentReshapeTool,
    mocker: MockerFixture,
):
    map_tool._change_to_pick_location_mode()
    assert map_tool.old_segment_rubber_band.asGeometry().isEmpty()
    assert map_tool.temporary_new_segment_rubber_band.asGeometry().isEmpty()

    m_find_common_segment = mocker.patch.object(
        map_tool,
        "_find_common_segment",
        return_value=(QgsLineString([(0, 0), (1, 1)]), QgsVectorLayer("test")),
        autospec=True,
    )

    map_tool._handle_mouse_click_event(MOUSE_LOCATION, Qt.LeftButton)

    m_find_common_segment.assert_called_once()
    assert map_tool.pick_location_mode is False
    assert map_tool.reshape_mode is True

    assert map_tool.old_segment_rubber_band.asGeometry().isGeosEqual(
        QgsGeometry.fromWkt("LineString (0 0, 1 1)")
    )
    assert (
        map_tool.temporary_new_segment_rubber_band.asGeometry().asWkt()
        == "LineString (0 0, 0 0)"
    )


def test_left_mouse_click_in_reshape_mode_adds_points_to_rubberbands(
    map_tool: SegmentReshapeTool,
    mocker: MockerFixture,
):
    map_tool._change_to_reshape_mode()

    m_make_reshape_edits = mocker.patch.object(
        reshape, "make_reshape_edits", autospec=True
    )

    map_tool._handle_mouse_click_event(MOUSE_LOCATION, Qt.LeftButton)

    assert not map_tool.new_segment_rubber_band.asGeometry().isEmpty()
    assert not map_tool.temporary_new_segment_rubber_band.asGeometry().isEmpty()

    m_make_reshape_edits.assert_not_called()


def test_pressing_backspace_in_reshape_mode_removes_point_from_rubberband(
    map_tool: SegmentReshapeTool,
):
    map_tool.old_segment_rubber_band.setToGeometry(
        QgsGeometry.fromWkt("LINESTRING(0 0, 1 1, 2 2, 3 3, 4 4, 5 5)")
    )
    map_tool.new_segment_rubber_band.setToGeometry(
        QgsGeometry.fromWkt("LINESTRING(0 0, 1 1, 2 2, 3 3, 4 4, 5 5)")
    )
    map_tool.temporary_new_segment_rubber_band.setToGeometry(
        QgsGeometry.fromWkt("LINESTRING(0 0, 1 1, 2 2, 3 3, 4 4, 5 5)")
    )
    map_tool.pick_location_mode = False
    map_tool.reshape_mode = True

    map_tool._handle_key_event(Qt.Key_Backspace)

    assert map_tool.pick_location_mode is False
    assert map_tool.reshape_mode is True
    assert (
        map_tool.new_segment_rubber_band.asGeometry().asWkt()
        == "LineString (0 0, 1 1, 2 2, 3 3, 4 4)"
    )
    assert not map_tool.old_segment_rubber_band.asGeometry().isEmpty()
    assert not map_tool.temporary_new_segment_rubber_band.asGeometry().isEmpty()


def test_pressing_backspace_twice_in_reshape_mode_removes_points_from_rubberband(
    map_tool: SegmentReshapeTool,
):
    map_tool.new_segment_rubber_band.setToGeometry(
        QgsGeometry.fromWkt("LINESTRING(0 0, 1 1, 2 2, 3 3, 4 4, 5 5)")
    )
    map_tool.pick_location_mode = False
    map_tool.reshape_mode = True

    map_tool._handle_key_event(Qt.Key_Backspace)
    map_tool._handle_key_event(Qt.Key_Backspace)

    assert (
        map_tool.new_segment_rubber_band.asGeometry().asWkt()
        == "LineString (0 0, 1 1, 2 2, 3 3)"
    )


def test_pressing_backspace_in_reshape_mode_with_only_one_point_in_rubberband(
    map_tool: SegmentReshapeTool,
):
    map_tool.temporary_new_segment_rubber_band.reset()
    map_tool.new_segment_rubber_band.setToGeometry(QgsGeometry.fromWkt("POINT(1 1)"))
    map_tool.pick_location_mode = False
    map_tool.reshape_mode = True

    map_tool._handle_key_event(Qt.Key_Backspace)

    assert map_tool.new_segment_rubber_band.asGeometry().isEmpty()
    assert not map_tool.temporary_new_segment_rubber_band.asGeometry().isEmpty()


def test_pressing_backspace_in_reshape_mode_with_no_points_in_rubberband(
    map_tool: SegmentReshapeTool,
):
    map_tool.new_segment_rubber_band.reset()
    map_tool.temporary_new_segment_rubber_band.reset()
    map_tool.pick_location_mode = False
    map_tool.reshape_mode = True

    map_tool._handle_key_event(Qt.Key_Backspace)

    assert map_tool.new_segment_rubber_band.asGeometry().isEmpty()
    assert not map_tool.temporary_new_segment_rubber_band.asGeometry().isEmpty()


def test_right_mouse_click_in_reshape_mode_changes_only_to_pick_mode_if_edited_geometry_is_empty(
    map_tool: SegmentReshapeTool,
    mocker: MockerFixture,
):
    map_tool._change_to_reshape_mode()

    m_change_to_pick_location_mode = mocker.patch.object(
        map_tool, "_change_to_pick_location_mode", autospec=True
    )

    m_make_reshape_edits = mocker.patch.object(
        reshape, "make_reshape_edits", autospec=True
    )

    map_tool._handle_mouse_click_event(MOUSE_LOCATION, Qt.RightButton)

    m_change_to_pick_location_mode.assert_called_once()
    m_make_reshape_edits.assert_not_called()


def test_right_mouse_click_in_reshape_mode_calls_reshape_if_edited_geometry_is_not_empty(
    map_tool: SegmentReshapeTool,
    mocker: MockerFixture,
):
    map_tool._change_to_reshape_mode()

    m_change_to_pick_location_mode = mocker.patch.object(
        map_tool, "_change_to_pick_location_mode", autospec=True
    )
    m_make_reshape_edits = mocker.patch.object(
        reshape, "make_reshape_edits", autospec=True
    )

    # Add point to rubberband
    map_tool._handle_mouse_click_event(QgsPointXY(1, 1), Qt.LeftButton)

    # Test
    map_tool._handle_mouse_click_event(MOUSE_LOCATION, Qt.RightButton)

    m_change_to_pick_location_mode.assert_called_once()
    m_make_reshape_edits.assert_called_once()


@pytest.mark.usefixtures("use_topological_editing")
def test_find_common_segment_should_return_shared_segment(
    qgis_iface: QgisInterface,
    map_tool: SegmentReshapeTool,
    mocker: MockerFixture,
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
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
