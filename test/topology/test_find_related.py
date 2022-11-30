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

from time import perf_counter
from typing import Callable, List, Tuple

import pytest
from qgis.core import QgsFeature, QgsGeometry, QgsProject, QgsVectorLayer

from segment_reshape.topology.find_related import (
    find_related_features,
    get_common_geometries,
)


def _normalize_wkt(wkt: str) -> str:
    geom = QgsGeometry.fromWkt(wkt)
    geom.normalize()
    return geom.asWkt()


def _assert_geom_equals_wkt(geom: QgsGeometry, wkt: str) -> None:
    __tracebackhide__ = True

    result = _normalize_wkt(geom.asWkt())
    target = _normalize_wkt(wkt)

    assert result == target


@pytest.mark.parametrize(
    argnames=("trigger_wkt", "trigger_indices", "expected_segment_wkt"),
    argvalues=[
        (
            "LINESTRING(0 0, 1 1)",
            (0, 1),
            "LINESTRING(0 0, 1 1)",
        ),
        (
            "MULTILINESTRING((0 0, 1 1), (2 2, 3 3))",
            (0, 1),
            "LINESTRING(0 0, 1 1)",
        ),
        (
            "MULTILINESTRING((0 0, 1 1), (2 2, 3 3))",
            (2, 3),
            "LINESTRING(2 2, 3 3)",
        ),
        (
            "POLYGON((0 0, 0 10, 10 10, 10 0, 0 0), (5 5, 5 6, 6 6, 6 5, 5 5))",
            (0, 1),
            "LINESTRING(0 0, 0 10, 10 10, 10 0, 0 0)",
        ),
        (
            "POLYGON((0 0, 0 10, 10 10, 10 0, 0 0), (5 5, 5 6, 6 6, 6 5, 5 5))",
            (5, 6),
            "LINESTRING(5 5, 5 6, 6 6, 6 5, 5 5)",
        ),
        (
            "MULTIPOLYGON("
            "((0 0, 0 10, 10 10, 10 0, 0 0), (5 5, 5 6, 6 6, 6 5, 5 5)),"
            "((20 20, 20 30, 30 30, 30 20, 20 20), (25 25, 25 26, 26 26, 26 25, 25 25))"
            ")",
            (0, 1),
            "LINESTRING(0 0, 0 10, 10 10, 10 0, 0 0)",
        ),
        (
            "MULTIPOLYGON("
            "((0 0, 0 10, 10 10, 10 0, 0 0), (5 5, 5 6, 6 6, 6 5, 5 5)),"
            "((20 20, 20 30, 30 30, 30 20, 20 20), (25 25, 25 26, 26 26, 26 25, 25 25))"
            ")",
            (5, 6),
            "LINESTRING(5 5, 5 6, 6 6, 6 5, 5 5)",
        ),
        (
            "MULTIPOLYGON("
            "((0 0, 0 10, 10 10, 10 0, 0 0), (5 5, 5 6, 6 6, 6 5, 5 5)),"
            "((20 20, 20 30, 30 30, 30 20, 20 20), (25 25, 25 26, 26 26, 26 25, 25 25))"
            ")",
            (10, 11),
            "LINESTRING(20 20, 20 30, 30 30, 30 20, 20 20)",
        ),
        (
            "MULTIPOLYGON("
            "((0 0, 0 10, 10 10, 10 0, 0 0), (5 5, 5 6, 6 6, 6 5, 5 5)),"
            "((20 20, 20 30, 30 30, 30 20, 20 20), (25 25, 25 26, 26 26, 26 25, 25 25))"
            ")",
            (15, 16),
            "LINESTRING(25 25, 25 26, 26 26, 26 25, 25 25)",
        ),
    ],
    ids=[
        "line",
        "multiline",
        "multiline-2nd-part",
        "polygon",
        "polygon-ring",
        "multipolygon",
        "multipolygon-ring",
        "multipolygon-2nd-part",
        "multipolygon-2nd-part-ring",
    ],
)
def test_calculate_common_segment_for_single_feature_picks_whole_triggered_component(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
    trigger_wkt: str,
    trigger_indices: Tuple[int, int],
    expected_segment_wkt: str,
):
    layer, (feature,) = preset_features_layer_factory("source", [trigger_wkt])

    (segment, _, _) = get_common_geometries(
        layer,
        feature,
        [],
        trigger_indices,
    )

    assert segment is not None
    _assert_geom_equals_wkt(segment, expected_segment_wkt)


@pytest.mark.parametrize(
    argnames=("trigger_wkt", "trigger_indices", "expected_result_indices"),
    argvalues=[
        (
            "LINESTRING(0 0, 1 1)",
            (0, 1),
            [0, 1],
        ),
        (
            "MULTILINESTRING((0 0, 1 1), (2 2, 3 3))",
            (0, 1),
            [0, 1],
        ),
        (
            "MULTILINESTRING((0 0, 1 1), (2 2, 3 3))",
            (2, 3),
            [2, 3],
        ),
        (
            "POLYGON((0 0, 0 10, 10 10, 10 0, 0 0), (5 5, 5 6, 6 6, 6 5, 5 5))",
            (0, 1),
            [4, 1, 2, 3, 4],
        ),
        (
            "POLYGON((0 0, 0 10, 10 10, 10 0, 0 0), (5 5, 5 6, 6 6, 6 5, 5 5))",
            (5, 6),
            [9, 6, 7, 8, 9],
        ),
        (
            "MULTIPOLYGON("
            "((0 0, 0 10, 10 10, 10 0, 0 0), (5 5, 5 6, 6 6, 6 5, 5 5)),"
            "((20 20, 20 30, 30 30, 30 20, 20 20), (25 25, 25 26, 26 26, 26 25, 25 25))"
            ")",
            (0, 1),
            [4, 1, 2, 3, 4],
        ),
        (
            "MULTIPOLYGON("
            "((0 0, 0 10, 10 10, 10 0, 0 0), (5 5, 5 6, 6 6, 6 5, 5 5)),"
            "((20 20, 20 30, 30 30, 30 20, 20 20), (25 25, 25 26, 26 26, 26 25, 25 25))"
            ")",
            (5, 6),
            [9, 6, 7, 8, 9],
        ),
        (
            "MULTIPOLYGON("
            "((0 0, 0 10, 10 10, 10 0, 0 0), (5 5, 5 6, 6 6, 6 5, 5 5)),"
            "((20 20, 20 30, 30 30, 30 20, 20 20), (25 25, 25 26, 26 26, 26 25, 25 25))"
            ")",
            (10, 11),
            [14, 11, 12, 13, 14],
        ),
        (
            "MULTIPOLYGON("
            "((0 0, 0 10, 10 10, 10 0, 0 0), (5 5, 5 6, 6 6, 6 5, 5 5)),"
            "((20 20, 20 30, 30 30, 30 20, 20 20), (25 25, 25 26, 26 26, 26 25, 25 25))"
            ")",
            (15, 16),
            [19, 16, 17, 18, 19],
        ),
    ],
    ids=[
        "line",
        "multiline",
        "multiline-2nd-part",
        "polygon",
        "polygon-ring",
        "multipolygon",
        "multipolygon-ring",
        "multipolygon-2nd-part",
        "multipolygon-2nd-part-ring",
    ],
)
def test_calculate_common_segment_for_single_feature_results_in_single_reshape_part_and_no_edges(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
    trigger_wkt: str,
    trigger_indices: Tuple[int, int],
    expected_result_indices: List[int],
):
    layer, (feature,) = preset_features_layer_factory("source", [trigger_wkt])

    (_, common_parts, edges) = get_common_geometries(
        layer,
        feature,
        [],
        trigger_indices,
    )

    assert len(edges) == 0
    assert len(common_parts) == 1
    common_part = common_parts[0]

    assert common_part.layer == layer
    assert common_part.feature == feature
    assert common_part.vertex_indices == expected_result_indices
    assert not common_part.is_reversed


@pytest.mark.parametrize(
    argnames=("trigger_wkt", "trigger_indices", "other_wkts", "expected_part_details"),
    argvalues=[
        (
            "LINESTRING(0 0, 1 1, 2 2)",
            (0, 1),
            ["LINESTRING(-1 -1, 0 0, 1 1, 2 2, 3 3)"],
            [([0, 1, 2], False), ([1, 2, 3], False)],
        ),
        (
            "LINESTRING(0 0, 1 1, 2 2)",
            (0, 1),
            ["LINESTRING(3 3, 2 2, 1 1, 0 0, -1 -1)"],
            [([0, 1, 2], False), ([3, 2, 1], True)],
        ),
    ],
    ids=[
        "other-fully-common-with-trigger",
        "other-fully-common-with-trigger-reversed",
    ],
)
def test_calculate_common_segment_for_multiple_lines_results_in_multiple_reshape_parts(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
    trigger_wkt: str,
    trigger_indices: Tuple[int, int],
    other_wkts: List[str],
    expected_part_details: List[Tuple[List[int], bool]],
):
    layer, (feature, *other_features) = preset_features_layer_factory(
        "source", [trigger_wkt] + other_wkts
    )

    (_, common_parts, _) = get_common_geometries(
        layer,
        feature,
        [(layer, f) for f in other_features],
        trigger_indices,
    )

    assert len(common_parts) == len(expected_part_details)

    for common_part, (expected_indices, expected_reversed) in zip(
        common_parts, expected_part_details
    ):
        assert common_part.vertex_indices == expected_indices
        assert common_part.is_reversed == expected_reversed


@pytest.mark.parametrize(
    argnames=("trigger_wkt", "trigger_indices", "other_wkts", "expected_edge_details"),
    argvalues=[
        (
            "LINESTRING(0 0, 1 1, 2 2)",
            (0, 1),
            ["LINESTRING(-1 -1, 0 0)", "LINESTRING(2 2, 3 3)"],
            [(1, True), (0, False)],
        ),
        (
            "LINESTRING(-1 0, 0 0, 1 1, 2 2, 3 2)",
            (1, 2),
            ["LINESTRING(-1 -1, 0 0)", "LINESTRING(2 2, 3 3)"],
            [(1, True), (0, False)],
        ),
        (
            "LINESTRING(0 0, 1 1, 2 2)",
            (0, 1),
            ["LINESTRING(-1 -1, 0 0, 2 0, 2 2, 3 3)"],
            [(1, True), (3, False)],
        ),
    ],
    ids=[
        "two-lines-at-trigger-feature-ends",
        "two-lines-breaking-trigger-feature",
        "same-feature-as-multiple-edges",
    ],
)
def test_calculate_common_segment_for_multiple_lines_results_in_multiple_edges(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
    trigger_wkt: str,
    trigger_indices: Tuple[int, int],
    other_wkts: List[str],
    expected_edge_details: List[Tuple[int, bool]],
):
    layer, (feature, *other_features) = preset_features_layer_factory(
        "source", [trigger_wkt] + other_wkts
    )

    (_, _, edges) = get_common_geometries(
        layer,
        feature,
        [(layer, f) for f in other_features],
        trigger_indices,
    )

    assert len(edges) == len(expected_edge_details)

    for edge, (expected_index, expected_start) in zip(edges, expected_edge_details):
        assert edge.vertex_index == expected_index
        assert edge.is_start == expected_start


@pytest.mark.parametrize(
    argnames=("count", "allowed_duration_ms"),
    argvalues=[
        (1000, 100),
        (2000, 200),
        (10000, 500),
    ],
    ids=[
        "1000x4-in-100-ms",
        "2000x4-in-200-ms",
        "10000x4-in-500-ms",
    ],
)
def test_calculate_common_segment_for_huge_polygon_coordinate_count_is_fast_enough(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
    count: int,
    allowed_duration_ms: int,
):
    polygon_wkt = "Polygon (("
    polygon_wkt += ", ".join([f"{x} 0" for x in range(count + 1)]) + ", "
    polygon_wkt += ", ".join([f"{count} {y}" for y in range(count + 1)]) + ", "
    polygon_wkt += ", ".join([f"{x} {count}" for x in range(count, -1, -1)]) + ", "
    polygon_wkt += ", ".join([f"0 {y}" for y in range(count, -1, -1)])
    polygon_wkt += "))"

    other_wkt = (
        "LINESTRING(" + ", ".join([f"{x} 0" for x in range(-500, count + 500)]) + ")"
    )

    layer, (feature,) = preset_features_layer_factory("source", [polygon_wkt])
    other_layer, (other_feature,) = preset_features_layer_factory("other", [other_wkt])

    start = perf_counter()
    get_common_geometries(
        layer,
        feature,
        [(other_layer, other_feature)],
        (count // 2, count // 2 - 1),
    )
    end = perf_counter()

    assert (
        end - start
    ) / 1000 < allowed_duration_ms, "common geometry code was not fast enough"


@pytest.mark.parametrize(
    argnames=("trigger_wkt", "trigger_indices", "other_wkts", "expected_segment_wkt"),
    argvalues=[
        (
            "LineStringZ (15 10 0, 10 10 0, 5 10 0, 0 15 0)",
            (1, 2),
            ["LineStringZ (10 10 0, 5 10 0)"],
            "LineString (10 10, 5 10)",
        ),
        (
            "LineStringZ (15 10 2, 10 10 2, 5 10 2, 0 15 2)",
            (1, 2),
            ["LineStringZ (10 10 0, 5 10 0)"],
            "LineString (10 10, 5 10)",
        ),
    ],
    ids=[
        "same-z-is-common-segment",
        "different-z-is-common-segment",
    ],
)
def test_calculate_common_segment_does_not_consider_z_dimension(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
    trigger_wkt: str,
    trigger_indices: Tuple[int, int],
    other_wkts: List[str],
    expected_segment_wkt: str,
):
    layer, (feature, *other_features) = preset_features_layer_factory(
        "source", [trigger_wkt] + other_wkts
    )

    (segment, _, _) = get_common_geometries(
        layer,
        feature,
        [(layer, f) for f in other_features],
        trigger_indices,
    )

    assert segment is not None

    # only test for 2d equality, since for different z case windows
    # returns (10 10 0, 5 10 2) and linux returns (10 10 1, 5 10 1)
    # investigate and possibly decide what should happen with z coords,
    # maybe always use the source geometry z's?
    segment.dropZValue()

    _assert_geom_equals_wkt(segment, expected_segment_wkt)


@pytest.mark.parametrize(
    argnames=("trigger_wkt", "trigger_indices", "other_wkts", "expected_segment_wkt"),
    argvalues=[
        (
            "LINESTRING(0 0, 1 1, 2 2, 3 3, 4 4, 5 5)",
            (2, 3),
            ["LINESTRING(4 4, 5 5)"],
            "LINESTRING(0 0, 1 1, 2 2, 3 3, 4 4)",
        ),
        (
            "LINESTRING(0 0, 1 1, 2 2, 3 3, 4 4, 5 5, 6 6, 7 7)",
            (3, 4),
            ["LINESTRING(0 0, 1 1)", "LINESTRING(6 6, 7 7)"],
            "LINESTRING(1 1, 2 2, 3 3, 4 4, 5 5, 6 6)",
        ),
        (
            "LINESTRING(0 0, 1 1, 2 2, 3 3, 4 4, 5 5, 6 6, 7 7)",
            (3, 4),
            ["LINESTRING(1 0, 1 1, 1 2)", "LINESTRING(6 5, 6 6, 6 7)"],
            "LINESTRING(1 1, 2 2, 3 3, 4 4, 5 5, 6 6)",
        ),
        (
            "LINESTRING(0 0, 1 1, 2 2, 3 3, 4 4, 5 5, 6 6, 7 7)",
            (3, 4),
            ["LINESTRING(0 1, 1 1, 1 0)", "LINESTRING(5 6, 6 6, 6 5)"],
            "LINESTRING(1 1, 2 2, 3 3, 4 4, 5 5, 6 6)",
        ),
        (
            "LINESTRING(0 0, 1 1, 2 2, 3 3, 4 4, 5 5, 6 6, 7 7)",
            (3, 4),
            ["LINESTRING(0 0, 1 1, 1 2, 5 6, 6 6, 7 7)"],
            "LINESTRING(1 1, 2 2, 3 3, 4 4, 5 5, 6 6)",
        ),
        (
            "LINESTRING(0 0, 1 1, 2 2, 3 3, 4 4, 5 5, 6 6, 7 7)",
            (3, 4),
            ["LINESTRING(1 0, 1 1, 1 2, 5 6, 6 6, 7 6)"],
            "LINESTRING(1 1, 2 2, 3 3, 4 4, 5 5, 6 6)",
        ),
    ],
    ids=[
        "self-outside-shared-expands-until-shared-and-end",
        "self-between-shared-expands-until-shared",
        "self-between-touching-expands-until-breaks",
        "self-between-intersect-expands-until-breaks",
        "self-between-other-partly-disjoint-expands-until-rejoin",
        "self-between-other-fully-disjoint-crosses-at-vertex-expands-until-breaks",
    ],
)
def test_calculate_common_segment_line_trigger_expanded(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
    trigger_wkt: str,
    trigger_indices: Tuple[int, int],
    other_wkts: List[str],
    expected_segment_wkt: str,
):
    layer, (feature, *other_features) = preset_features_layer_factory(
        "source", [trigger_wkt] + other_wkts
    )

    (segment, _, _) = get_common_geometries(
        layer,
        feature,
        [(layer, f) for f in other_features],
        trigger_indices,
    )

    assert segment is not None
    _assert_geom_equals_wkt(segment, expected_segment_wkt)


def test_calculate_common_segment_line_broken_by_points_as_edges(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
):
    layer, (feature,) = preset_features_layer_factory(
        "source", ["LINESTRING(-1 -1, 0 0, 1 1, 2 2, 3 3, 4 4)"]
    )
    other_layer, (point_1, point_2) = preset_features_layer_factory(
        "other", ["POINT(0 0)", "POINT(3 3)"]
    )

    (segment, common_parts, edges) = get_common_geometries(
        layer,
        feature,
        [(other_layer, point_1), (other_layer, point_2)],
        (2, 3),
    )

    assert segment is not None
    _assert_geom_equals_wkt(segment, "LINESTRING(0 0, 1 1, 2 2, 3 3)")

    assert len(common_parts) == 1  # source feature only
    assert len(edges) == 2  # points as edges

    edge_1, edge_2 = edges

    _assert_geom_equals_wkt(edge_1.feature.geometry(), "POINT(0 0)")
    assert edge_1.is_start
    _assert_geom_equals_wkt(edge_2.feature.geometry(), "POINT(3 3)")
    assert not edge_2.is_start


@pytest.mark.parametrize(
    argnames=("trigger_wkt", "trigger_indices", "other_wkts", "expected_segment_wkt"),
    argvalues=[
        (
            "LINESTRING(0 0, 1 1, 2 2, 3 3, 4 4, 5 5, 6 6, 7 7)",
            (3, 4),
            ["LINESTRING(1 0, 0 1)"],
            "LINESTRING(0 0, 1 1, 2 2, 3 3, 4 4, 5 5, 6 6, 7 7)",
        ),
        (
            "LINESTRING(0 0, 1 1, 2 2, 3 3, 4 4, 5 5, 6 6, 7 7)",
            (3, 4),
            ["LINESTRING(1 0, 1.5 1.5, 2 0, 5 0, 5.5 5.5, 6 0)"],
            "LINESTRING(0 0, 1 1, 2 2, 3 3, 4 4, 5 5, 6 6, 7 7)",
        ),
    ],
    ids=[
        "self-between-other-fully-disjoint-cross-not-at-vertex-expands-fully",
        "self-between-other-fully-disjoint-touch-not-at-vertex-expands-fully",
    ],
)
def test_calculate_common_segment_line_having_related_feature_not_at_vertex_trigger_expanded(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
    trigger_wkt: str,
    trigger_indices: Tuple[int, int],
    other_wkts: List[str],
    expected_segment_wkt: str,
):
    layer, (feature, *other_features) = preset_features_layer_factory(
        "source", [trigger_wkt] + other_wkts
    )

    (segment, _, _) = get_common_geometries(
        layer,
        feature,
        [(layer, f) for f in other_features],
        trigger_indices,
    )

    assert segment is not None
    _assert_geom_equals_wkt(segment, expected_segment_wkt)


@pytest.mark.parametrize(
    argnames=("trigger_wkt", "trigger_indices", "other_wkts", "expected_segment_wkt"),
    argvalues=[
        (
            "LINESTRING(0 0, 1 1, 2 2)",
            (0, 1),
            ["LINESTRING(1.5 1.5, 2 2, 3 3)"],
            "LINESTRING(0 0, 1 1, 2 2)",
        ),
    ],
    ids=[
        "partial-linear-intersection-only-breaks-at-shared-vertex",
    ],
)
def test_calculate_common_segment_line_having_related_feature_linear_intersect_trigger_expanded(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
    trigger_wkt: str,
    trigger_indices: Tuple[int, int],
    other_wkts: List[str],
    expected_segment_wkt: str,
):
    layer, (feature, *other_features) = preset_features_layer_factory(
        "source", [trigger_wkt] + other_wkts
    )

    (segment, _, _) = get_common_geometries(
        layer,
        feature,
        [(layer, f) for f in other_features],
        trigger_indices,
    )

    assert segment is not None
    _assert_geom_equals_wkt(segment, expected_segment_wkt)


@pytest.mark.parametrize(
    argnames=("trigger_wkt", "trigger_indices", "other_wkts", "expected_segment_wkt"),
    argvalues=[
        (
            "POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))",
            (0, 1),
            ["POLYGON((1 0, 1 1, 2 1, 2 0, 1 0))"],  # 1 0, 1 1 shared, removed
            "LINESTRING(1 0, 0 0, 0 1, 1 1)",
        ),
        (
            "POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))",
            (0, 1),
            ["POLYGON((2 0, 1 1, 2 1, 2 0))"],  # 1 1 touched, split
            "LINESTRING(1 1, 1 0, 0 0, 0 1, 1 1)",
        ),
    ],
    ids=[
        "shared-intersection-removed",
        "touch-location-split",
    ],
)
def test_calculate_common_segment_polygon_ring_boundary_crossed(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
    trigger_wkt: str,
    trigger_indices: Tuple[int, int],
    other_wkts: List[str],
    expected_segment_wkt: str,
):
    layer, (feature, *other_features) = preset_features_layer_factory(
        "source", [trigger_wkt] + other_wkts
    )

    (segment, _, _) = get_common_geometries(
        layer,
        feature,
        [(layer, f) for f in other_features],
        trigger_indices,
    )

    assert segment is not None
    _assert_geom_equals_wkt(segment, expected_segment_wkt)


@pytest.mark.parametrize(
    argnames=("trigger_wkt", "trigger_indices", "other_wkts", "expected_segment_wkt"),
    argvalues=[
        (
            "LINESTRING(0 0, 1 1, 2 2)",
            (0, 1),
            ["LINESTRING(0 0, 2 2)"],
            "LINESTRING(0 0, 1 1, 2 2)",
        ),
        (
            "LINESTRING(0 0, 1 1)",
            (0, 1),
            ["LINESTRING(0 0, 0.5 0.5, 1 1)"],
            "LINESTRING(0 0, 1 1)",
        ),
    ],
    ids=[
        "component-fully-contains-trigger-in-one-larger-segment-should-not-break",
        "component-fully-contains-trigger-in-multiple-segments-should-not-break",
    ],
)
def test_calculate_common_segment_line_having_related_feature_contains_trigger_as_difference_sequence(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ],
    trigger_wkt: str,
    trigger_indices: Tuple[int, int],
    other_wkts: List[str],
    expected_segment_wkt: str,
):
    layer, (feature, *other_features) = preset_features_layer_factory(
        "source", [trigger_wkt] + other_wkts
    )

    (segment, _, _) = get_common_geometries(
        layer,
        feature,
        [(layer, f) for f in other_features],
        trigger_indices,
    )

    assert segment is not None
    _assert_geom_equals_wkt(segment, expected_segment_wkt)


@pytest.mark.usefixtures("qgis_new_project")
def test_find_related_features_no_results_by_default_if_topological_editing_disabled(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ]
):
    source_layer, (source_feature,) = preset_features_layer_factory(
        "source", ["LINESTRING(0 0, 1 1)"]
    )
    layer1, _ = preset_features_layer_factory("l1", ["LINESTRING(0 0, 1 1)"])
    QgsProject.instance().addMapLayers([layer1])

    assert not QgsProject.instance().topologicalEditing()

    results = find_related_features(source_layer, source_feature)

    assert results == []


@pytest.mark.usefixtures("qgis_new_project", "use_topological_editing")
def test_find_related_features_results_by_default_from_project_vector_layers(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ]
):
    source_layer, (source_feature,) = preset_features_layer_factory(
        "source", ["LINESTRING(0 0, 1 1)"]
    )
    layer1, _ = preset_features_layer_factory("l1", ["LINESTRING(0 0, 1 1)"])
    layer2, _ = preset_features_layer_factory("l2", ["LINESTRING(0 0, 1 1)"])

    # not added to project, not present in results
    layer3, _ = preset_features_layer_factory("l3", ["LINESTRING(0 0, 1 1)"])

    QgsProject.instance().addMapLayers([layer1, layer2])

    results = find_related_features(source_layer, source_feature)

    layer_ids = [layer.id() for layer, _ in results]

    assert layer_ids == [layer1.id(), layer2.id()]


@pytest.mark.usefixtures("qgis_new_project")
def test_find_related_features_uses_custom_list_if_given_if_topological_editing_disabled(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ]
):
    source_layer, (source_feature,) = preset_features_layer_factory(
        "source", ["LINESTRING(0 0, 1 1)"]
    )
    layer1, _ = preset_features_layer_factory("l1", ["LINESTRING(0 0, 1 1)"])
    layer2, _ = preset_features_layer_factory("l2", ["LINESTRING(0 0, 1 1)"])

    # not given, not present in results
    layer3, _ = preset_features_layer_factory("l3", ["LINESTRING(0 0, 1 1)"])

    assert not QgsProject.instance().topologicalEditing()

    results = find_related_features(
        source_layer, source_feature, candidate_layers=[layer1, layer2]
    )

    layer_ids = [layer.id() for layer, _ in results]

    assert layer_ids == [layer1.id(), layer2.id()]


@pytest.mark.usefixtures("qgis_new_project", "use_topological_editing")
def test_find_related_features_uses_custom_list_if_given(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ]
):
    source_layer, (source_feature,) = preset_features_layer_factory(
        "source", ["LINESTRING(0 0, 1 1)"]
    )
    layer1, _ = preset_features_layer_factory("l1", ["LINESTRING(0 0, 1 1)"])
    layer2, _ = preset_features_layer_factory("l2", ["LINESTRING(0 0, 1 1)"])

    # not given, not present in results
    layer3, _ = preset_features_layer_factory("l3", ["LINESTRING(0 0, 1 1)"])

    results = find_related_features(
        source_layer, source_feature, candidate_layers=[layer1, layer2]
    )

    layer_ids = [layer.id() for layer, _ in results]

    assert layer_ids == [layer1.id(), layer2.id()]


@pytest.mark.usefixtures("qgis_new_project")
def test_find_related_features_finds_features_touching_the_target(
    preset_features_layer_factory: Callable[
        [str, List[str]], Tuple[QgsVectorLayer, List[QgsFeature]]
    ]
):
    source_layer, (source_feature,) = preset_features_layer_factory(
        "source", ["LINESTRING(0 0, 1 1)"]
    )
    layer1, _ = preset_features_layer_factory(
        "l1",
        [
            "LINESTRING(1 0, 0 1)",
            "LINESTRING(3 0, 0 3)",  # not touching
        ],
    )
    layer2, _ = preset_features_layer_factory(
        "l2",
        [
            "LINESTRING(1 1, 2 2)",
            "LINESTRING(0 0, -1 -1)",
            "LINESTRING(-0.1 -0.1, -1 -1)",  # not touching
        ],
    )
    layer3, _ = preset_features_layer_factory(
        "l3",
        [
            "POINT(0.1 0.1)",
            "POINT(0.9 0.9)",
            "POINT(1.1 1.1)",  # not touching
        ],
    )

    results = find_related_features(
        source_layer, source_feature, candidate_layers=[layer1, layer2, layer3]
    )

    assert len(results) == 1 + 2 + 2
