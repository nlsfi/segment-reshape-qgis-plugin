from typing import Callable, List, Tuple

import pytest
from pytest_mock import MockerFixture
from qgis.core import (
    QgsFeature,
    QgsFields,
    QgsGeometry,
    QgsLineString,
    QgsMemoryProviderUtils,
    QgsPoint,
    QgsVectorLayer,
    QgsVectorLayerUtils,
    QgsWkbTypes,
)

from segment_reshape.geometry.replace_segment import (
    GeometryTransformationError,
    SegmentCommonPart,
    SegmentEdge,
    make_edits_for_new_segment,
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


@pytest.fixture()
def memory_layer_factory() -> Callable[[str, QgsWkbTypes.Type], QgsVectorLayer]:
    def _factory(name: str, geometry_type: QgsWkbTypes.Type) -> QgsVectorLayer:
        return QgsMemoryProviderUtils.createMemoryLayer(
            name,
            QgsFields(),
            geometry_type,
        )

    return _factory


@pytest.fixture()
def preset_features_layer_factory(
    memory_layer_factory: Callable[[str, QgsWkbTypes.Type], QgsVectorLayer]
) -> Callable[[str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]]:
    def _factory(name: str, wkts: List[str]) -> Tuple[QgsVectorLayer, List[QgsFeature]]:
        geometries = [QgsGeometry.fromWkt(wkt) for wkt in wkts]
        layer = memory_layer_factory(name, geometries[0].wkbType())
        features = [
            QgsVectorLayerUtils.createFeature(layer, geom) for geom in geometries
        ]
        _, added_features = layer.dataProvider().addFeatures(features)
        return layer, added_features

    return _factory


def test_editing_enabled_for_non_editable_layers(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ]
):
    layer1, features1 = preset_features_layer_factory("l1", ["LINESTRING(0 0, 1 1)"])
    layer2, features2 = preset_features_layer_factory("l2", ["LINESTRING(0 0, 1 1)"])

    assert not layer1.isEditable()
    assert not layer2.isEditable()

    make_edits_for_new_segment(
        [
            SegmentCommonPart(layer1, features1[0], [0, 1], False),
            SegmentCommonPart(layer2, features2[0], [0, 1], False),
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

    make_edits_for_new_segment(
        [
            SegmentCommonPart(layer1, features1[0], [0, 1], False),
            SegmentCommonPart(layer1, features1[1], [0, 1], False),
            SegmentCommonPart(layer2, features2[0], [0, 1], False),
            SegmentCommonPart(layer2, features2[1], [0, 1], False),
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

    make_edits_for_new_segment(
        [
            SegmentCommonPart(layer1, features1[0], [0, 1], False),
            SegmentCommonPart(layer1, features1[1], [0, 1], False),
            SegmentCommonPart(layer2, features2[0], [0, 1], False),
            SegmentCommonPart(layer2, features2[1], [0, 1], False),
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
        "segment_reshape.geometry.replace_segment._move_edges",
        side_effect=GeometryTransformationError("mocked error"),
    )

    with pytest.raises(GeometryTransformationError, match="mocked error"):
        make_edits_for_new_segment(
            [
                SegmentCommonPart(layer1, features1[0], [0, 1], False),
                SegmentCommonPart(layer1, features1[1], [0, 1], False),
                SegmentCommonPart(layer2, features2[0], [0, 1], False),
                SegmentCommonPart(layer2, features2[1], [0, 1], False),
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
        "segment_reshape.geometry.replace_segment._move_edges",
        side_effect=GeometryTransformationError("mocked error"),
    )

    with pytest.raises(GeometryTransformationError, match="mocked error"):
        make_edits_for_new_segment(
            [
                SegmentCommonPart(layer1, features1[0], [0, 1], False),
                SegmentCommonPart(layer1, features1[1], [0, 1], False),
                SegmentCommonPart(layer2, features2[0], [0, 1], False),
                SegmentCommonPart(layer2, features2[1], [0, 1], False),
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
        "segment_reshape.geometry.replace_segment._move_edges",
        side_effect=GeometryTransformationError("mocked error"),
    )

    with pytest.raises(GeometryTransformationError, match="mocked error"):
        make_edits_for_new_segment(
            [
                SegmentCommonPart(layer1, features1[0], [0, 1], False),
                SegmentCommonPart(layer1, features1[1], [0, 1], False),
                SegmentCommonPart(layer2, features2[0], [0, 1], False),
                SegmentCommonPart(layer2, features2[1], [0, 1], False),
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

    make_edits_for_new_segment(
        [
            SegmentCommonPart(layer1, features1[0], [0, 1], False),
            SegmentCommonPart(layer2, features2[0], [0, 1], False),
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
        make_edits_for_new_segment(
            [
                SegmentCommonPart(layer1, features1[0], [1, 2], False),
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

    make_edits_for_new_segment(
        [
            SegmentCommonPart(layer1, features1[0], [0], False),
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
        make_edits_for_new_segment(
            [
                SegmentCommonPart(layer1, features1[0], [0], False),
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

    make_edits_for_new_segment(
        [
            SegmentCommonPart(layer1, features1[0], [1], False),
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

    make_edits_for_new_segment(
        [
            SegmentCommonPart(layer1, features1[0], [1, 2], False),
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

    make_edits_for_new_segment(
        [
            SegmentCommonPart(layer1, features1[0], [1], False),
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

    make_edits_for_new_segment(
        [
            SegmentCommonPart(layer1, features1[0], indices, False),
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

    make_edits_for_new_segment(
        [
            SegmentCommonPart(layer1, features1[0], indices, False),
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

    make_edits_for_new_segment(
        [
            SegmentCommonPart(layer1, features1[0], indices, False),
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

    make_edits_for_new_segment(
        [
            SegmentCommonPart(layer1, features1[0], indices, False),
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

    make_edits_for_new_segment(
        [
            SegmentCommonPart(layer1, features1[0], [1, 2], is_reversed=True),
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

    make_edits_for_new_segment(
        [
            SegmentCommonPart(layer1, features1[0], [1, 2], is_reversed=True),
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

    make_edits_for_new_segment(
        [
            SegmentCommonPart(layer1, features1[0], [4, 0, 1], is_reversed=True),
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

    make_edits_for_new_segment(
        [],
        [
            SegmentEdge(layer1, features1[0], 0, is_start=True),
            SegmentEdge(layer1, features1[1], 0, is_start=False),
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

    make_edits_for_new_segment(
        [],
        [
            SegmentEdge(layer1, features1[0], 1, is_start=True),
            SegmentEdge(layer1, features1[1], 0, is_start=False),
        ],
        QgsLineString([(2, 0), (0, 2)]),
    )

    _assert_layer_geoms(layer1, ["LINESTRING(0 0, 2 0)", "LINESTRING(0 2, 4 4)"])


def test_edge_polygons_moved_to_match_reshape(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
):
    layer1, features1 = preset_features_layer_factory(
        "l1",
        ["POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))", "POLYGON((2 2, 2 3, 3 3, 3 2, 2 2))"],
    )

    make_edits_for_new_segment(
        [],
        [
            SegmentEdge(layer1, features1[0], 2, is_start=True),
            SegmentEdge(layer1, features1[1], 0, is_start=False),
        ],
        QgsLineString([(2, 0), (0, 2)]),
    )

    _assert_layer_geoms(
        layer1,
        ["POLYGON((0 0, 0 1, 2 0, 1 0, 0 0))", "POLYGON((0 2, 2 3, 3 3, 3 2, 0 2))"],
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

    make_edits_for_new_segment(
        [
            SegmentCommonPart(layer1, features1[0], [1, 2, 3], False),
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

    make_edits_for_new_segment(
        [
            SegmentCommonPart(layer1, features1[0], [1, 2, 3], False),
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

    make_edits_for_new_segment(
        [
            SegmentCommonPart(layer1, features1[0], [4, 5, 0], False),
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

    make_edits_for_new_segment(
        [
            SegmentCommonPart(layer1, features1[0], [7, 4], False),
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

    make_edits_for_new_segment(
        [
            SegmentCommonPart(layer1, features1[0], [1, 2, 3], False),
        ],
        [
            SegmentEdge(layer1, features1[1], 1, is_start=True),
            SegmentEdge(layer1, features1[2], 0, is_start=True),
            SegmentEdge(layer1, features1[3], 1, is_start=False),
            SegmentEdge(layer1, features1[4], 0, is_start=False),
            SegmentEdge(layer2, features2[0], 0, is_start=True),
            SegmentEdge(layer2, features2[1], 0, is_start=False),
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

    make_edits_for_new_segment(
        [
            SegmentCommonPart(layer1, features1[0], [1], False),
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

    make_edits_for_new_segment(
        [
            SegmentCommonPart(layer1, features1[0], [2], False),
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

    make_edits_for_new_segment(
        [
            SegmentCommonPart(layer1, features1[0], [0, 1, 2, 3], False),
        ],
        [],
        QgsLineString([(1, 1), (1, 2), (2, 2), (2, 1), (1, 1)]),
    )

    _assert_layer_geoms(layer1, ["POLYGON((1 1, 1 2, 2 2, 2 1, 1 1))"])
