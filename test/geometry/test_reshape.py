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

import pytest
from pytest_mock import MockerFixture
from qgis.core import QgsFeature, QgsGeometry, QgsLineString, QgsPoint, QgsVectorLayer

from segment_reshape.geometry.reshape import (
    GeometryTransformationError,
    ReshapeCommonPart,
    ReshapeEdge,
    make_reshape_edits,
)


def _normalize_wkt(wkt: str) -> str:
    g = QgsGeometry.fromWkt(wkt)
    g.normalize()
    return g.asWkt()


def _assert_layer_geoms(layer: QgsVectorLayer, expected_geom_wkts: List[str]):
    __tracebackhide__ = True

    layer_wkts = [_normalize_wkt(f.geometry().asWkt()) for f in layer.getFeatures()]
    expected_wkts = [_normalize_wkt(wkt) for wkt in expected_geom_wkts]

    assert layer_wkts == expected_wkts


def test_editing_enabled_for_non_editable_layers(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ]
):
    layer1, features1 = preset_features_layer_factory("l1", ["LINESTRING(0 0, 1 1)"])
    layer2, features2 = preset_features_layer_factory("l2", ["LINESTRING(0 0, 1 1)"])

    assert not layer1.isEditable()
    assert not layer2.isEditable()

    make_reshape_edits(
        [
            ReshapeCommonPart(layer1, features1[0], [0, 1], False),
            ReshapeCommonPart(layer2, features2[0], [0, 1], False),
        ],
        [],
        QgsLineString([(0, 0), (1, 1)]),
    )

    assert layer1.isEditable()
    assert layer2.isEditable()


def test_edits_made_in_single_edit_command_for_each_layer(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ]
):
    layer1, features1 = preset_features_layer_factory(
        "l1", ["LINESTRING(0 0, 1 1)", "LINESTRING(0 0, 1 1)"]
    )
    layer2, features2 = preset_features_layer_factory(
        "l2", ["LINESTRING(0 0, 1 1)", "LINESTRING(0 0, 1 1)"]
    )

    make_reshape_edits(
        [
            ReshapeCommonPart(layer1, features1[0], [0, 1], False),
            ReshapeCommonPart(layer1, features1[1], [0, 1], False),
            ReshapeCommonPart(layer2, features2[0], [0, 1], False),
            ReshapeCommonPart(layer2, features2[1], [0, 1], False),
        ],
        [],
        QgsLineString([(0, 0), (1, 1)]),
    )

    assert not layer1.isEditCommandActive()
    assert layer1.undoStack().count() == 1
    assert not layer2.isEditCommandActive()
    assert layer2.undoStack().count() == 1


def test_existing_edit_command_allowed_without_modifications(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ]
):
    layer1, features1 = preset_features_layer_factory(
        "l1", ["LINESTRING(0 0, 1 1)", "LINESTRING(0 0, 1 1)"]
    )
    layer2, features2 = preset_features_layer_factory(
        "l2", ["LINESTRING(0 0, 1 1)", "LINESTRING(0 0, 1 1"]
    )

    layer1.startEditing()
    layer1.beginEditCommand("undo1")
    layer2.startEditing()
    layer2.beginEditCommand("undo2")

    make_reshape_edits(
        [
            ReshapeCommonPart(layer1, features1[0], [0, 1], False),
            ReshapeCommonPart(layer1, features1[1], [0, 1], False),
            ReshapeCommonPart(layer2, features2[0], [0, 1], False),
            ReshapeCommonPart(layer2, features2[1], [0, 1], False),
        ],
        [],
        QgsLineString([(0, 0), (1, 1)]),
    )

    assert layer1.isEditCommandActive()
    assert layer1.undoStack().text(0) == "undo1"
    assert layer2.isEditCommandActive()
    assert layer2.undoStack().text(0) == "undo2"


def test_edit_commands_for_editable_layers_removed_on_error(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
    mocker: MockerFixture,
):
    layer1, features1 = preset_features_layer_factory(
        "l1", ["LINESTRING(0 0, 1 1)", "LINESTRING(0 0, 1 1)"]
    )
    layer2, features2 = preset_features_layer_factory(
        "l2", ["LINESTRING(0 0, 1 1)", "LINESTRING(0 0, 1 1"]
    )

    layer1.startEditing()
    layer2.startEditing()

    mocker.patch(
        "segment_reshape.geometry.reshape._move_edges",
        side_effect=GeometryTransformationError("mocked error"),
    )

    with pytest.raises(GeometryTransformationError, match="mocked error"):
        make_reshape_edits(
            [
                ReshapeCommonPart(layer1, features1[0], [0, 1], False),
                ReshapeCommonPart(layer1, features1[1], [0, 1], False),
                ReshapeCommonPart(layer2, features2[0], [0, 1], False),
                ReshapeCommonPart(layer2, features2[1], [0, 1], False),
            ],
            [],
            QgsLineString([(0, 0), (1, 1)]),
        )

    assert layer1.isEditable()
    assert not layer1.isEditCommandActive()
    assert layer1.undoStack().count() == 0
    assert layer2.isEditable()
    assert not layer2.isEditCommandActive()
    assert layer2.undoStack().count() == 0


def test_non_editable_layer_rolled_back_on_error(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
    mocker: MockerFixture,
):
    layer1, features1 = preset_features_layer_factory(
        "l1", ["LINESTRING(0 0, 1 1)", "LINESTRING(0 0, 1 1)"]
    )
    layer2, features2 = preset_features_layer_factory(
        "l2", ["LINESTRING(0 0, 1 1)", "LINESTRING(0 0, 1 1"]
    )

    mocker.patch(
        "segment_reshape.geometry.reshape._move_edges",
        side_effect=GeometryTransformationError("mocked error"),
    )

    with pytest.raises(GeometryTransformationError, match="mocked error"):
        make_reshape_edits(
            [
                ReshapeCommonPart(layer1, features1[0], [0, 1], False),
                ReshapeCommonPart(layer1, features1[1], [0, 1], False),
                ReshapeCommonPart(layer2, features2[0], [0, 1], False),
                ReshapeCommonPart(layer2, features2[1], [0, 1], False),
            ],
            [],
            QgsLineString([(0, 0), (1, 1)]),
        )

    assert not layer1.isEditable()
    assert not layer2.isEditable()


def test_existing_edit_command_not_removed_on_error(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
    mocker: MockerFixture,
):
    layer1, features1 = preset_features_layer_factory(
        "l1", ["LINESTRING(0 0, 1 1)", "LINESTRING(0 0, 1 1)"]
    )
    layer2, features2 = preset_features_layer_factory(
        "l2", ["LINESTRING(0 0, 1 1)", "LINESTRING(0 0, 1 1"]
    )

    layer1.startEditing()
    layer1.beginEditCommand("undo1")
    layer2.startEditing()
    layer2.beginEditCommand("undo2")

    mocker.patch(
        "segment_reshape.geometry.reshape._move_edges",
        side_effect=GeometryTransformationError("mocked error"),
    )

    with pytest.raises(GeometryTransformationError, match="mocked error"):
        make_reshape_edits(
            [
                ReshapeCommonPart(layer1, features1[0], [0, 1], False),
                ReshapeCommonPart(layer1, features1[1], [0, 1], False),
                ReshapeCommonPart(layer2, features2[0], [0, 1], False),
                ReshapeCommonPart(layer2, features2[1], [0, 1], False),
            ],
            [],
            QgsLineString([(0, 0), (1, 1)]),
        )

    assert layer1.isEditCommandActive()
    assert layer1.undoStack().text(0) == "undo1"
    assert layer2.isEditCommandActive()
    assert layer2.undoStack().text(0) == "undo2"


def test_edits_applied_to_layer_features(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ]
):
    layer1, features1 = preset_features_layer_factory("l1", ["LINESTRING(0 0, 1 1)"])
    layer2, features2 = preset_features_layer_factory("l2", ["LINESTRING(0 0, 1 1)"])

    make_reshape_edits(
        [
            ReshapeCommonPart(layer1, features1[0], [0, 1], False),
            ReshapeCommonPart(layer2, features2[0], [0, 1], False),
        ],
        [],
        QgsLineString([(2, 2), (3, 3)]),
    )

    _assert_layer_geoms(layer1, ["LINESTRING(2 2, 3 3)"])
    _assert_layer_geoms(layer2, ["LINESTRING(2 2, 3 3)"])


def test_reshape_with_invalid_indices_fails(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ]
):
    layer1, features1 = preset_features_layer_factory("l1", ["LINESTRING(0 0, 1 1)"])

    with pytest.raises(GeometryTransformationError, match="vertex"):
        make_reshape_edits(
            [
                ReshapeCommonPart(layer1, features1[0], [1, 2], False),
            ],
            [],
            QgsLineString([(2, 2), (3, 3)]),
        )


def test_common_point_reshaped(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ]
):
    layer1, features1 = preset_features_layer_factory("l1", ["POINT(0 0)"])

    make_reshape_edits(
        [
            ReshapeCommonPart(layer1, features1[0], [0], False),
        ],
        [],
        QgsPoint(1, 1),
    )

    _assert_layer_geoms(layer1, ["POINT(1 1)"])


def test_common_point_reshaped_by_line_fails(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ]
):
    layer1, features1 = preset_features_layer_factory("l1", ["POINT(0 0)"])

    with pytest.raises(GeometryTransformationError, match="vertex"):
        make_reshape_edits(
            [
                ReshapeCommonPart(layer1, features1[0], [0], False),
            ],
            [],
            QgsLineString([(1, 1), (2, 2)]),
        )


def test_common_multipoint_reshaped(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ]
):
    layer1, features1 = preset_features_layer_factory(
        "l1", ["MULTIPOINT(0 0, 1 1, 2 2)"]
    )

    make_reshape_edits(
        [
            ReshapeCommonPart(layer1, features1[0], [1], False),
        ],
        [],
        QgsPoint(1.5, 1.5),
    )

    _assert_layer_geoms(layer1, ["MULTIPOINT(0 0, 1.5 1.5, 2 2)"])


def test_common_multipoint_reshaped_by_line_from_multiple_vertices(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ]
):
    layer1, features1 = preset_features_layer_factory(
        "l1", ["MULTIPOINT(0 0, 1 1, 2 2, 3 3)"]
    )

    make_reshape_edits(
        [
            ReshapeCommonPart(layer1, features1[0], [1, 2], False),
        ],
        [],
        QgsLineString([(1.5, 1.5), (2.5, 2.5)]),
    )

    _assert_layer_geoms(layer1, ["MULTIPOINT(0 0, 1.5 1.5, 2.5 2.5, 3 3)"])


def test_common_multipoint_reshaped_by_line_from_single_vertex(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ]
):
    layer1, features1 = preset_features_layer_factory(
        "l1", ["MULTIPOINT(0 0, 1 1, 2 2)"]
    )

    make_reshape_edits(
        [
            ReshapeCommonPart(layer1, features1[0], [1], False),
        ],
        [],
        QgsLineString([(1.5, 1.5), (2.5, 2.5)]),
    )

    _assert_layer_geoms(layer1, ["MULTIPOINT(0 0, 1.5 1.5, 2.5 2.5, 2 2)"])


@pytest.mark.parametrize(
    argnames=("input_wkt", "reshape_wkt", "indices", "expected_wkt"),
    argvalues=[
        (
            "LINESTRING(0 0, 1 1, 2 2)",
            "LINESTRING(5 5, 6 6, 7 7)",
            [0, 1, 2],
            "LINESTRING(5 5, 6 6, 7 7)",
        ),
        (
            "LINESTRING(0 0, 1 1, 2 2)",
            "LINESTRING(5 5, 6 6, 7 7, 8 8, 9 9)",
            [0, 1, 2],
            "LINESTRING(5 5, 6 6, 7 7, 8 8, 9 9)",
        ),
        (
            "LINESTRING(0 0, 1 1, 2 2, 3 3, 4 4)",
            "LINESTRING(-1 -1, 0.5 0.5, 1 1)",
            [0, 1, 2],
            "LINESTRING(-1 -1, 0.5 0.5, 1 1, 3 3, 4 4)",
        ),
        (
            "LINESTRING(0 0, 1 1, 2 2, 3 3, 4 4)",
            "LINESTRING(-1 -1, 0.5 0.5)",
            [0, 1, 2],
            "LINESTRING(-1 -1, 0.5 0.5, 3 3, 4 4)",
        ),
        (
            "LINESTRING(0 0, 1 1, 2 2, 3 3, 4 4)",
            "LINESTRING(2 0, 2 2, 3 3)",
            [2, 3, 4],
            "LINESTRING(0 0, 1 1, 2 0, 2 2, 3 3)",
        ),
        (
            "LINESTRING(0 0, 1 1, 2 2, 3 3, 4 4)",
            "LINESTRING(2 0, 2 2)",
            [2, 3, 4],
            "LINESTRING(0 0, 1 1, 2 0, 2 2)",
        ),
        (
            "LINESTRING(0 0, 1 1, 2 2, 3 3, 4 4)",
            "LINESTRING(0.5 1, 1.5 2, 2.5 3)",
            [1, 2, 3],
            "LINESTRING(0 0, 0.5 1, 1.5 2, 2.5 3, 4 4)",
        ),
        (
            "LINESTRING(0 0, 1 1, 2 2, 3 3, 4 4)",
            "LINESTRING(1.5 1.5, 2.1 2.1, 2.2 2.2, 3.5 3.5)",
            [1, 2, 3],
            "LINESTRING(0 0, 1.5 1.5, 2.1 2.1, 2.2 2.2, 3.5 3.5, 4 4)",
        ),
    ],
    ids=[
        "fully-equal-count",
        "fully-different-count",
        "start-equal-count",
        "start-different-count",
        "end-equal-count",
        "end-different-count",
        "mid-equal-count",
        "mid-different-count",
    ],
)
def test_common_line_segment_reshaped(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
    input_wkt: str,
    reshape_wkt: str,
    indices: List[int],
    expected_wkt: str,
):
    layer1, features1 = preset_features_layer_factory("l1", [input_wkt])

    reshape = QgsLineString()
    reshape.fromWkt(reshape_wkt)

    make_reshape_edits(
        [
            ReshapeCommonPart(layer1, features1[0], indices, False),
        ],
        [],
        reshape,
    )

    _assert_layer_geoms(layer1, [expected_wkt])


@pytest.mark.parametrize(
    argnames=("input_wkt", "reshape_wkt", "indices", "expected_wkt"),
    argvalues=[
        (
            "MULTILINESTRING((0 0, 1 1, 2 2), (3 3, 4 4))",
            "LINESTRING(1 0, 2 0, 3 0)",
            [1, 2],
            "MULTILINESTRING((0 0, 1 0, 2 0, 3 0), (3 3, 4 4))",
        ),
        (
            "MULTILINESTRING((0 0, 1 1, 2 2), (3 3, 4 4, 5 5))",
            "LINESTRING(3 0, 4 0, 5 0)",
            [3, 4],
            "MULTILINESTRING((0 0, 1 1, 2 2), (3 0, 4 0, 5 0, 5 5))",
        ),
    ],
    ids=["first-part-end", "second-part-start"],
)
def test_common_multiline_segment_reshaped(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
    input_wkt: str,
    reshape_wkt: str,
    indices: List[int],
    expected_wkt: str,
):
    layer1, features1 = preset_features_layer_factory("l1", [input_wkt])

    reshape = QgsLineString()
    reshape.fromWkt(reshape_wkt)

    make_reshape_edits(
        [
            ReshapeCommonPart(layer1, features1[0], indices, False),
        ],
        [],
        reshape,
    )

    _assert_layer_geoms(layer1, [expected_wkt])


@pytest.mark.parametrize(
    argnames=("input_wkt", "reshape_wkt", "indices", "expected_wkt"),
    argvalues=[
        (
            "POLYGON((0 0, 0 10, 10 10, 10 0, 0 0))",
            "LINESTRING(0 9, 9 9)",
            [1, 2],
            "POLYGON((0 0, 0 9, 9 9, 10 0, 0 0))",
        ),
        (
            "POLYGON((0 0, 0 10, 10 10, 10 0, 0 0))",
            "LINESTRING(10 1, 1 1, 1 10)",
            [0, 1, 3],
            "POLYGON((1 1, 1 10, 10 10, 10 1, 1 1))",
        ),
        (
            "POLYGON((0 0, 0 10, 10 10, 10 0, 0 0))",
            "LINESTRING(0 10, 4 9, 5 9, 6 9, 10 10)",
            [1, 2],
            "POLYGON((0 0, 0 10, 4 9, 5 9, 6 9, 10 10, 10 0, 0 0))",
        ),
        (
            "POLYGON((0 0, 0 10, 10 10, 10 0, 0 0))",
            "LINESTRING(10 1, 6 1, 5 1, 4 1, 1 1, 1 10)",
            [0, 1, 3],
            "POLYGON((1 1, 1 10, 10 10, 10 1, 6 1, 5 1, 4 1, 1 1))",
        ),
        (
            "POLYGON((0 0, 0 10, 10 10, 10 0, 0 0), (4 4, 4 6, 6 6, 6 4, 4 4))",
            "LINESTRING(4 5, 5 5, 5 4)",
            [6, 7, 8],
            "POLYGON((0 0, 0 10, 10 10, 10 0, 0 0), (4 4, 4 5, 5 5, 5 4, 4 4))",
        ),
        (
            "POLYGON((0 0, 0 10, 10 10, 10 0, 0 0), (4 4, 4 6, 6 6, 6 4, 4 4))",
            "LINESTRING(6 5, 5 5, 5 6)",
            [5, 6, 8],
            "POLYGON((0 0, 0 10, 10 10, 10 0, 0 0), (5 5, 5 6, 6 6, 6 5, 5 5))",
        ),
    ],
    ids=[
        "linear-same-count",
        "wraparound-same-count",
        "linear-different-count",
        "wraparound-different-count",
        "ring-linear-same-count",
        "ring-wraparound-same-count",
    ],
)
def test_common_polygon_segment_reshaped(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
    input_wkt: str,
    reshape_wkt: str,
    indices: List[int],
    expected_wkt: str,
):
    layer1, features1 = preset_features_layer_factory("l1", [input_wkt])

    reshape = QgsLineString()
    reshape.fromWkt(reshape_wkt)

    make_reshape_edits(
        [
            ReshapeCommonPart(layer1, features1[0], indices, False),
        ],
        [],
        reshape,
    )

    _assert_layer_geoms(layer1, [expected_wkt])


@pytest.mark.parametrize(
    argnames=("input_wkt", "reshape_wkt", "indices", "expected_wkt"),
    argvalues=[
        (
            "MULTIPOLYGON(((0 0, 0 1, 1 1, 1 0, 0 0)), ((5 5, 5 10, 10 10, 10 5, 5 5), (6 6, 6 9, 9 9, 9 6, 6 6)))",
            "LINESTRING(9 6.1, 6.1 6.1, 6.1 7, 6.1 8, 6.1 9)",
            [10, 11, 13],
            "MULTIPOLYGON(((0 0, 0 1, 1 1, 1 0, 0 0)), ((5 5, 5 10, 10 10, 10 5, 5 5), (6.1 6.1, 6.1 7, 6.1 8, 6.1 9, 9 9, 9 6.1, 6.1 6.1)))",
        ),
    ],
    ids=[
        "part-ring-wraparound-different-count",
    ],
)
def test_common_multipolygon_segment_reshaped(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
    input_wkt: str,
    reshape_wkt: str,
    indices: List[int],
    expected_wkt: str,
):
    layer1, features1 = preset_features_layer_factory("l1", [input_wkt])

    reshape = QgsLineString()
    reshape.fromWkt(reshape_wkt)

    make_reshape_edits(
        [
            ReshapeCommonPart(layer1, features1[0], indices, False),
        ],
        [],
        reshape,
    )

    _assert_layer_geoms(layer1, [expected_wkt])


def test_reversed_common_line_segment_reshaped_in_correct_order(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
):
    layer1, features1 = preset_features_layer_factory(
        "l1", ["LINESTRING(0 0, 1 1, 2 2, 3 3)"]
    )

    make_reshape_edits(
        [
            ReshapeCommonPart(layer1, features1[0], [1, 2], is_reversed=True),
        ],
        [],
        QgsLineString([(2, 3), (1, 2)]),
    )

    _assert_layer_geoms(layer1, ["LINESTRING(0 0, 1 2, 2 3, 3 3)"])


def test_reversed_common_polygon_segment_reshaped_in_correct_order(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
):
    layer1, features1 = preset_features_layer_factory(
        "l1", ["POLYGON((0 0, 1 1, 2 2, 3 3, 3 0, 0 0))"]
    )

    make_reshape_edits(
        [
            ReshapeCommonPart(layer1, features1[0], [1, 2], is_reversed=True),
        ],
        [],
        QgsLineString([(2, 3), (1, 2)]),
    )

    _assert_layer_geoms(layer1, ["POLYGON((0 0, 1 2, 2 3, 3 3, 3 0, 0 0))"])


def test_reversed_common_polygon_segment_reshaped_in_correct_order_with_wraparound(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
):
    layer1, features1 = preset_features_layer_factory(
        "l1", ["POLYGON((0 0, 1 1, 2 2, 3 3, 3 0, 0 0))"]
    )

    make_reshape_edits(
        [
            ReshapeCommonPart(layer1, features1[0], [4, 0, 1], is_reversed=True),
        ],
        [],
        QgsLineString([(1.1, 1.1), (0.1, 0.1), (3.1, 0.1)]),
    )

    _assert_layer_geoms(
        layer1, ["POLYGON((0.1 0.1, 1.1 1.1, 2 2, 3 3, 3.1 0.1, 0.1 0.1))"]
    )


def test_edge_points_moved_to_match_reshape(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
):
    layer1, features1 = preset_features_layer_factory(
        "l1", ["POINT(0 0)", "POINT(3 3)"]
    )

    make_reshape_edits(
        [],
        [
            ReshapeEdge(layer1, features1[0], 0, is_start=True),
            ReshapeEdge(layer1, features1[1], 0, is_start=False),
        ],
        QgsLineString([(2, 0), (0, 2)]),
    )

    _assert_layer_geoms(layer1, ["POINT(2 0)", "POINT(0 2)"])


def test_edge_lines_moved_to_match_reshape(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
):
    layer1, features1 = preset_features_layer_factory(
        "l1", ["LINESTRING(0 0, 1 1)", "LINESTRING(3 3, 4 4)"]
    )

    make_reshape_edits(
        [],
        [
            ReshapeEdge(layer1, features1[0], 1, is_start=True),
            ReshapeEdge(layer1, features1[1], 0, is_start=False),
        ],
        QgsLineString([(2, 0), (0, 2)]),
    )

    _assert_layer_geoms(layer1, ["LINESTRING(0 0, 2 0)", "LINESTRING(0 2, 4 4)"])


def test_closed_line_moved_to_match_reshape(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
):
    layer1, features1 = preset_features_layer_factory(
        "l1", ["LINESTRING(0 0, 1 1, 3 3, 0 0)"]
    )

    make_reshape_edits(
        [],
        [
            ReshapeEdge(layer1, features1[0], 1, is_start=False),
        ],
        QgsLineString([(2, 2)]),
    )

    _assert_layer_geoms(layer1, ["LINESTRING(0 0, 2 2, 3 3, 0 0)"])


def test_edge_polygons_moved_to_match_reshape(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
):
    layer1, features1 = preset_features_layer_factory(
        "l1",
        ["POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))", "POLYGON((2 2, 2 3, 3 3, 3 2, 2 2))"],
    )

    make_reshape_edits(
        [],
        [
            ReshapeEdge(layer1, features1[0], 2, is_start=True),
            ReshapeEdge(layer1, features1[1], 0, is_start=False),
        ],
        QgsLineString([(2, 0), (0, 2)]),
    )

    _assert_layer_geoms(
        layer1,
        ["POLYGON((0 0, 0 1, 2 0, 1 0, 0 0))", "POLYGON((0 2, 2 3, 3 3, 3 2, 0 2))"],
    )


def test_edge_polygon_with_both_start_and_end_moved_to_match_reshape(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
):
    layer1, features1 = preset_features_layer_factory(
        "l1",
        ["POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))"],
    )

    make_reshape_edits(
        [],
        [
            ReshapeEdge(layer1, features1[0], 1, is_start=True),
            ReshapeEdge(layer1, features1[0], 3, is_start=False),
        ],
        QgsLineString([(0, 2), (2, 2), (2, 0)]),
    )

    _assert_layer_geoms(
        layer1,
        ["POLYGON((0 0, 0 2, 1 1, 2 0, 0 0))"],
    )


def test_line_segment_collapsed_to_single_point(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
):
    layer1, features1 = preset_features_layer_factory(
        "l1",
        ["LINESTRING(0 0, 1 1, 2 2, 3 3, 4 4)"],
    )

    reshape = QgsPoint()
    reshape.fromWkt("POINT(2.5 2.5)")

    make_reshape_edits(
        [
            ReshapeCommonPart(layer1, features1[0], [1, 2, 3], False),
        ],
        [],
        reshape,
    )

    _assert_layer_geoms(layer1, ["LINESTRING(0 0, 2.5 2.5, 4 4)"])


def test_polygon_segment_collapsed_to_single_point(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
):
    layer1, features1 = preset_features_layer_factory(
        "l1",
        ["POLYGON((0 0, 1 1, 2 2, 3 3, 4 4, 4 0, 0 0))"],
    )

    reshape = QgsPoint()
    reshape.fromWkt("POINT(2.5 2.5)")

    make_reshape_edits(
        [
            ReshapeCommonPart(layer1, features1[0], [1, 2, 3], False),
        ],
        [],
        reshape,
    )

    _assert_layer_geoms(layer1, ["POLYGON((0 0, 2.5 2.5, 4 4, 4 0, 0 0))"])


def test_polygon_segment_collapsed_to_single_point_with_wraparound(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
):
    layer1, features1 = preset_features_layer_factory(
        "l1",
        ["POLYGON((0 0, 1 1, 2 2, 3 3, 4 4, 4 0, 0 0))"],
    )

    reshape = QgsPoint()
    reshape.fromWkt("POINT(-1 -3)")

    make_reshape_edits(
        [
            ReshapeCommonPart(layer1, features1[0], [4, 5, 0], False),
        ],
        [],
        reshape,
    )

    _assert_layer_geoms(layer1, ["POLYGON((-1 -3, 1 1, 2 2, 3 3, -1 -3))"])


def test_multipolygon_segment_collapsed_to_single_point_with_wraparound(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
):
    layer1, features1 = preset_features_layer_factory(
        "l1",
        ["MULTIPOLYGON(((0 0, 1 0, 0 1, 0 0)), ((5 5, 6 5, 6 6, 5 6, 5 5)))"],
    )

    reshape = QgsPoint()
    reshape.fromWkt("POINT(6 4)")

    make_reshape_edits(
        [
            ReshapeCommonPart(layer1, features1[0], [7, 4], False),
        ],
        [],
        reshape,
    )

    _assert_layer_geoms(
        layer1, ["MULTIPOLYGON(((0 0, 1 0, 0 1, 0 0)), ((6 4, 6 5, 6 6, 6 4)))"]
    )


def test_segment_collaped_to_single_point_edges_joined(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
):
    layer1, features1 = preset_features_layer_factory(
        "l1",
        [
            "LINESTRING(0 0, 1 1, 2 2, 3 3, 4 4)",
            "LINESTRING(1 0, 1 1)",
            "LINESTRING(1 1, 1 2)",
            "LINESTRING(3 0, 3 3)",
            "LINESTRING(3 3, 3 4)",
            "POINT(1 1)",
            "POINT(3 3)",
        ],
    )
    layer2, features2 = preset_features_layer_factory(
        "l2",
        [
            "POINT(1 1)",
            "POINT(3 3)",
        ],
    )

    reshape = QgsPoint()
    reshape.fromWkt("POINT(2.5 2.5)")

    make_reshape_edits(
        [
            ReshapeCommonPart(layer1, features1[0], [1, 2, 3], False),
        ],
        [
            ReshapeEdge(layer1, features1[1], 1, is_start=True),
            ReshapeEdge(layer1, features1[2], 0, is_start=True),
            ReshapeEdge(layer1, features1[3], 1, is_start=False),
            ReshapeEdge(layer1, features1[4], 0, is_start=False),
            ReshapeEdge(layer2, features2[0], 0, is_start=True),
            ReshapeEdge(layer2, features2[1], 0, is_start=False),
        ],
        reshape,
    )

    _assert_layer_geoms(
        layer1,
        [
            "LINESTRING(0 0, 2.5 2.5, 4 4)",
            "LINESTRING(1 0, 2.5 2.5)",
            "LINESTRING(2.5 2.5, 1 2)",
            "LINESTRING(3 0, 2.5 2.5)",
            "LINESTRING(2.5 2.5, 3 4)",
        ],
    )
    _assert_layer_geoms(layer2, ["POINT(2.5 2.5)", "POINT(2.5 2.5)"])


def test_line_segment_expanded_from_single_vertex(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
):
    layer1, features1 = preset_features_layer_factory(
        "l1",
        ["LINESTRING(0 0, 1 1, 2 2)"],
    )

    make_reshape_edits(
        [
            ReshapeCommonPart(layer1, features1[0], [1], False),
        ],
        [],
        QgsLineString([(0.5, 0.5), (1.5, 1.5)]),
    )

    _assert_layer_geoms(layer1, ["LINESTRING(0 0, 0.5 0.5, 1.5 1.5, 2 2)"])


def test_polygon_segment_expanded_from_single_vertex(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
):
    layer1, features1 = preset_features_layer_factory(
        "l1",
        ["POLYGON((0 0, 1 1, 2 2, 3 3, 4 4, 4 0, 0 0))"],
    )

    make_reshape_edits(
        [
            ReshapeCommonPart(layer1, features1[0], [2], False),
        ],
        [],
        QgsLineString([(1.5, 1.5), (2.5, 2.5)]),
    )

    _assert_layer_geoms(
        layer1, ["POLYGON((0 0, 1 1, 1.5 1.5, 2.5 2.5, 3 3, 4 4, 4 0, 0 0))"]
    )


def test_polygon_fully_replaced_by_reshape(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
):
    layer1, features1 = preset_features_layer_factory(
        "l1",
        ["POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))"],
    )

    make_reshape_edits(
        [
            # input can either be from zero and loop back to zero
            ReshapeCommonPart(layer1, features1[0], [0, 1, 2, 3, 0], False),
        ],
        [],
        QgsLineString([(1, 1), (1, 2), (2, 2), (2, 1), (1, 1)]),
    )

    _assert_layer_geoms(layer1, ["POLYGON((1 1, 1 2, 2 2, 2 1, 1 1))"])

    make_reshape_edits(
        [
            # or from last, second and end to last
            ReshapeCommonPart(layer1, features1[0], [4, 1, 2, 3, 4], False),
        ],
        [],
        QgsLineString([(2, 2), (2, 3), (3, 3), (3, 2), (2, 2)]),
    )

    _assert_layer_geoms(layer1, ["POLYGON((2 2, 2 3, 3 3, 3 2, 2 2))"])


def test_full_polygon_partially_replaced_by_reshape_auto_closed(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
):
    layer1, features1 = preset_features_layer_factory(
        "l1",
        ["POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))"],
    )

    make_reshape_edits(
        [
            ReshapeCommonPart(layer1, features1[0], [4, 1, 2, 3, 4], False),
        ],
        [],
        QgsLineString([(1, 1), (1, 2), (2, 2), (2, 1)]),
    )

    _assert_layer_geoms(layer1, ["POLYGON((1 1, 1 2, 2 2, 2 1, 1 1))"])


def test_closed_line_fully_replaced_by_reshape(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
):
    layer1, features1 = preset_features_layer_factory(
        "l1",
        ["LINESTRING(0 0, 0 1, 1 1, 1 0, 0 0)"],
    )

    make_reshape_edits(
        [
            ReshapeCommonPart(layer1, features1[0], [0, 1, 2, 3, 4], False),
        ],
        [],
        QgsLineString([(2, 2), (0, 2), (3, 3), (2, 0), (2, 2)]),
    )

    _assert_layer_geoms(layer1, ["LINESTRING(2 2, 0 2, 3 3, 2 0, 2 2)"])


@pytest.mark.parametrize(
    argnames=("indices", "reshape_wkt"),
    argvalues=[
        ([0, 1, 2, 3, 4], "LINESTRING(2 2, 0 2, 3 3, 2 0, 2 2)"),
        ([4, 1, 2, 3, 4], "LINESTRING(2 2, 0 2, 3 3, 2 0, 2 2)"),
        ([2, 3, 4, 1, 2], "LINESTRING(3 3, 2 0, 2 2, 0 2, 3 3)"),
    ],
    ids=[
        "wraparound-at-origin-no-duplicate",
        "wraparound-at-origin-duplicate-last",
        "wraparound-at-middle",
    ],
)
def test_closed_line_not_drawn_closed_still_closed_by_reshape(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
    indices: List[int],
    reshape_wkt: str,
):
    layer1, features1 = preset_features_layer_factory(
        "l1",
        ["LINESTRING(0 0, 0 1, 1 1, 1 0, 0 0)"],
    )

    reshape_geom = QgsGeometry.fromWkt(reshape_wkt).constGet()

    make_reshape_edits(
        [
            ReshapeCommonPart(layer1, features1[0], indices, False),
        ],
        [],
        reshape_geom,
    )

    _assert_layer_geoms(layer1, [reshape_wkt])


@pytest.mark.parametrize(
    argnames=("original", "indices", "reshape", "result"),
    argvalues=[
        (
            "LINESTRING(0 0, 0 1, 1 1, 1 0, 0 0)",
            [3, 4, 1, 2],
            "LINESTRING(2 0, -1 -1, 0 2, 2 2)",
            "LINESTRING(-1 -1, 0 2, 2 2, 2 0, -1 -1)",
        ),
        (
            "LINESTRING(0 0, 0 1, 1 1, 1 0, 0 0)",
            [4, 1],
            "LINESTRING(-1 -1, 0 2)",
            "LINESTRING(-1 -1, 0 2, 1 1, 1 0, -1 -1)",
        ),
        (
            "LINESTRING(0 0, 0 1, 1 1, 1 0, 0 0)",
            [3, 4, 1, 2],
            "LINESTRING(2 0, 1 0, -1 -1, 0 1, 0 2, 2 2)",
            "LINESTRING(-1 -1, 0 1, 0 2, 2 2, 2 0, 1 0, -1 -1)",
        ),
        (
            "LINESTRING(0 0, 0 1, 1 1, 1 0, 0 0)",
            [4, 1],
            "LINESTRING(-1 -1, 0 1, 0 2)",
            "LINESTRING(-1 -1, 0 1, 0 2, 1 1, 1 0, -1 -1)",
        ),
    ],
    ids=[
        "one-segment-not-common-same-count",
        "one-segment-common-same-count",
        "one-segment-not-common-diffrent-count",
        "one-segment-common-diffrent-count",
    ],
)
def test_wraparound_closed_linestring_partially_reshaped(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
    original: str,
    indices: List[int],
    reshape: str,
    result: str,
):
    layer, (feature,) = preset_features_layer_factory(
        "l1",
        [original],
    )

    reshape_geom = QgsGeometry.fromWkt(reshape).constGet()

    make_reshape_edits(
        [
            ReshapeCommonPart(layer, feature, indices, False),
        ],
        [],
        reshape_geom,
    )

    _assert_layer_geoms(layer, [result])
