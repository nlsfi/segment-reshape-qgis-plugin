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

from typing import List, Optional, Tuple

import pytest
from qgis.core import QgsFeature, QgsGeometry, QgsPoint, QgsVectorLayer

from segment_reshape.topology import find_related


@pytest.fixture()
def main_feature() -> Tuple[QgsFeature, List[QgsFeature]]:
    main_feature = QgsFeature()
    main_feature.setGeometry(
        QgsGeometry.fromWkt(
            "PolygonZ ((0 0 0, 0 10 0, 5 10 0, 10 10 0, 10 0 0, 0 0 0))"
        )
    )

    return main_feature


def test_get_common_geometries_with_line_shares_border_should_return_common_segment(
    main_feature: QgsFeature,
):
    layer_1 = QgsVectorLayer("layer1")
    layer_2 = QgsVectorLayer("layer2")

    line_feature = QgsFeature()
    # Intersects main feature at: LineStringZ (10 10 0, 5 10 0)
    line_feature.setGeometry(
        QgsGeometry.fromWkt("LineStringZ (15 10 0, 10 10 0, 5 10 0, 0 15 0)")
    )

    (
        segment,
        common_segment_results,
        segment_end_point_results,
    ) = find_related.get_common_geometries(
        layer_1, main_feature, [(layer_2, line_feature)], QgsPoint(7, 10, 0)
    )

    assert QgsGeometry(segment).isGeosEqual(
        QgsGeometry.fromWkt("LineStringZ (10 10 0, 5 10 0)")
    )
    assert len(common_segment_results) == 2
    assert len(segment_end_point_results) == 0

    assert common_segment_results[0].layer == layer_1
    assert common_segment_results[0].feature == main_feature
    assert common_segment_results[0].vertex_indices == [2, 3]
    assert common_segment_results[0].is_reversed is False

    assert common_segment_results[1].layer == layer_2
    assert common_segment_results[1].feature == line_feature
    assert common_segment_results[1].vertex_indices == [2, 1]
    assert common_segment_results[1].is_reversed is True


def test_get_common_geometries_with_no_intersecting_features_should_return_polygon_boundary_as_common_segment(
    main_feature: QgsFeature,
):
    layer_1 = QgsVectorLayer("layer1")
    (
        segment,
        common_segment_results,
        segment_end_point_results,
    ) = find_related.get_common_geometries(
        layer_1, main_feature, [], QgsPoint(7, 10, 0)
    )

    assert QgsGeometry(segment).isGeosEqual(
        QgsGeometry.fromWkt(
            "LineStringZ (0 0 0, 0 10 0, 5 10 0, 10 10 0, 10 0 0, 0 0 0)"
        )
    )
    assert len(common_segment_results) == 1
    assert len(segment_end_point_results) == 0

    assert common_segment_results[0].layer == layer_1
    assert common_segment_results[0].feature == main_feature
    assert common_segment_results[0].vertex_indices == [0, 1, 2, 3, 4, 5]
    assert common_segment_results[0].is_reversed is False


def test_get_common_geometries_with_no_intersecting_features_should_return_input_polyline_as_common_segment():
    layer_1 = QgsVectorLayer("layer1")
    line_feature = QgsFeature()
    input_wkt = "LineStringZ (15 10 0, 10 10 0"
    line_feature.setGeometry(QgsGeometry.fromWkt(input_wkt))

    (
        segment,
        common_segment_results,
        segment_end_point_results,
    ) = find_related.get_common_geometries(
        layer_1, line_feature, [], QgsPoint(12, 10, 0)
    )

    assert QgsGeometry(segment).isGeosEqual(QgsGeometry.fromWkt(input_wkt))
    assert len(common_segment_results) == 1
    assert len(segment_end_point_results) == 0

    assert common_segment_results[0].layer == layer_1
    assert common_segment_results[0].feature == line_feature
    assert common_segment_results[0].vertex_indices == [0, 1]
    assert common_segment_results[0].is_reversed is False


def test_get_common_geometries_line_end_point_at_trigger_location_should_return_common_edges(
    main_feature: QgsFeature,
):
    layer_1 = QgsVectorLayer("layer1")
    layer_2 = QgsVectorLayer("layer2")

    line_feature = QgsFeature()
    # Intersects main feature at: PointZ (10 10 0)
    line_feature.setGeometry(QgsGeometry.fromWkt("LineStringZ (15 10 0, 10 10 0)"))

    (
        segment,
        common_segment_results,
        segment_end_point_results,
    ) = find_related.get_common_geometries(
        layer_1, main_feature, [(layer_2, line_feature)], QgsPoint(10, 10, 0)
    )

    assert segment is None
    assert len(common_segment_results) == 0
    assert len(segment_end_point_results) == 2

    assert segment_end_point_results[0].layer == layer_1
    assert segment_end_point_results[0].feature == main_feature
    assert segment_end_point_results[0].vertex_index == 3
    assert segment_end_point_results[0].is_start is True

    assert segment_end_point_results[1].layer == layer_2
    assert segment_end_point_results[1].feature == line_feature
    assert segment_end_point_results[1].vertex_index == 1
    assert segment_end_point_results[1].is_start is True


def test_get_common_geometries_with_multiple_results_should_return_common_segments_and_edgess(
    main_feature: QgsFeature,
):
    layer_1 = QgsVectorLayer("layer1")
    layer_2 = QgsVectorLayer("layer2")

    line_feature_1 = QgsFeature()
    # Intersects main feature at: LineStringZ (10 10 0, 5 10 0)
    line_feature_1.setGeometry(
        QgsGeometry.fromWkt("LineStringZ (15 10 0, 10 10 0, 5 10 0, 0 15 0)")
    )

    line_feature_2 = QgsFeature()
    # Intersects main feature at: PointZ (10 10 0)
    line_feature_2.setGeometry(QgsGeometry.fromWkt("LineStringZ (15 10 0, 10 10 0)"))

    (
        segment,
        common_segment_results,
        segment_end_point_results,
    ) = find_related.get_common_geometries(
        layer_1,
        main_feature,
        [(layer_2, line_feature_1), (layer_2, line_feature_2)],
        QgsPoint(7, 10, 0),
    )

    assert QgsGeometry(segment).isGeosEqual(
        QgsGeometry.fromWkt("LineStringZ (5 10 0, 10 10 0)")
    )
    assert len(common_segment_results) == 2

    assert common_segment_results[0].layer == layer_1
    assert common_segment_results[0].feature == main_feature
    assert common_segment_results[0].vertex_indices == [2, 3]
    assert common_segment_results[0].is_reversed is False

    assert common_segment_results[1].layer == layer_2
    assert common_segment_results[1].feature == line_feature_1
    assert common_segment_results[1].vertex_indices == [2, 1]
    assert common_segment_results[1].is_reversed is True

    assert len(segment_end_point_results) == 1

    assert segment_end_point_results[0].layer == layer_2
    assert segment_end_point_results[0].feature == line_feature_2
    assert segment_end_point_results[0].vertex_index == 1
    assert segment_end_point_results[0].is_start is False


@pytest.mark.timeout(3)
def test_get_common_geometries_with_large_features():
    layer_1 = QgsVectorLayer("layer1")
    feature = QgsFeature()

    polygon_wkt = "Polygon (("
    polygon_wkt += ", ".join([f"{x} 0" for x in range(10001)])
    polygon_wkt += ", ".join([f"1000 {y}" for y in range(10001)])
    polygon_wkt += ", ".join([f"{x} 1000" for x in range(10001, -1, -1)])
    polygon_wkt += ", ".join([f"0 {y}" for y in range(10001, -1, -1)])
    polygon_wkt += "))"

    feature.setGeometry(QgsGeometry.fromWkt(polygon_wkt))
    assert not feature.geometry().isEmpty()

    intersecting_feature = QgsFeature()
    linestring_wkt = (
        "LineString (" + ", ".join([f"{x} 0" for x in range(-5000, 15000)]) + ")"
    )
    intersecting_feature.setGeometry(QgsGeometry.fromWkt(linestring_wkt))
    assert not intersecting_feature.geometry().isEmpty()

    (
        segment,
        common_segment_results,
        segment_end_point_results,
    ) = find_related.get_common_geometries(
        layer_1, feature, [(layer_1, intersecting_feature)], QgsPoint(7, 10, 0)
    )

    assert segment is not None
    assert len(common_segment_results) == 1
    assert len(segment_end_point_results) == 0


@pytest.mark.parametrize(
    ("geoms", "expected_result"),
    [
        (
            [QgsGeometry.fromWkt("LineStringZ (15 10 0, 10 10 0, 5 10 0, 0 15 0)")],
            QgsGeometry.fromWkt("LineStringZ (10 10 0, 5 10 0)"),
        ),
        (
            [QgsGeometry.fromWkt("LineStringZ (15 10 2, 10 10 2, 5 10 2, 0 15 2)")],
            QgsGeometry.fromWkt("LineStringZ (10 10 0, 5 10 0)"),
        ),
        (
            [QgsGeometry.fromWkt("LineStringZ (10 10 0, 8.8 10 0, 5 10 0)")],
            None,
        ),
        (
            [QgsGeometry.fromWkt("LineStringZ (8.8 10 0, 5.2 10 0)")],
            None,
        ),
        (
            [QgsGeometry.fromWkt("LineStringZ (10 10 0, 3 10 0)")],
            None,
        ),
        (
            # Intersects main feature at: LineStringZ (10 10 0, 5 10 0, 3 10 0), PointZ (10 6 0)
            [
                QgsGeometry.fromWkt(
                    "LineStringZ (10 6 0, 15 6 0, 15 10 0, 10 10 0, 5 10 0, 3 10 0, 0 15 0)"
                )
            ],
            QgsGeometry.fromWkt("LineStringZ (10 10 0, 5 10 0)"),
        ),
        (
            [
                QgsGeometry.fromWkt("LineStringZ (10 10 0, 5 10 0, 5 15 0)"),
                QgsGeometry.fromWkt(
                    "LineStringZ (10 6 0, 15 6 0, 15 10 0, 10 10 0, 5 10 0, 3 10 0, 0 15 0)"
                ),
            ],
            QgsGeometry.fromWkt("LineStringZ (10 10 0, 5 10 0)"),
        ),
        (
            [QgsGeometry.fromWkt("PointZ (10 10 0)")],
            None,
        ),
        (
            [QgsGeometry.fromWkt("PointZ (7 10 0)")],
            None,
        ),
        (
            [QgsGeometry.fromWkt("PolygonZ ((5 5 0, 5 15 0, 15 15 0, 15 5 0, 5 5 0))")],
            None,
        ),
        (
            [
                # Intersects main feature at: LineStringZ (10 10 0, 5 10 0), LineStringZ (10 6 0, 20 2 0)
                QgsGeometry.fromWkt(
                    "PolygonZ ((5 18 0, 5 10 0, 10 10 0, 10 13 0, 11 13 0, 11 6 0, 10 6 0, 10 2 0, 13 2 0, 13 18 0, 5 18 0))"
                ),
                QgsGeometry.fromWkt(
                    "LineStringZ (10 6 0, 15 6 0, 15 10 0, 10 10 0, 3 10 0, 0 15 0)"
                ),
            ],
            QgsGeometry.fromWkt("LineStringZ (5 10 0, 10 10 0)"),
        ),
        (
            [],
            None,
        ),
    ],
    ids=[
        "line shares polygon border",
        "line shares polygon border in 2D but not 3D",
        "line shares polygon border but have extra vertices",
        "line shares polygon border but does not match polygon vertices",
        "line shares polygon border but does not have all common vertices",
        "line multi-intersects polygon border",
        "2 lines multi-intersect polygon border",
        "point on polygon border but not on trigger point",
        "point on polygon border on trigger point",
        "overlapping polygon with no common vertices",
        "adjacent polygon plus intersecting line, multiple shared segments",
        "empty input list",
    ],
)
def test_calculate_common_segment(
    geoms: List[QgsGeometry], expected_result: QgsGeometry
):
    assert len([geom for geom in geoms if geom.isEmpty()]) == 0, "Error in input wkt"
    main_geom = QgsGeometry.fromWkt(
        "PolygonZ ((0 0 0, 0 10 0, 3 10 0, 5 10 0, 10 10 0, 10 6 0, 10 2 0, 10 0 0, 0 0 0))"
    )

    resulting_line = find_related._calculate_common_segment(
        main_geom,
        geoms,
        QgsGeometry(QgsPoint(7, 10, 0)),
    )

    if resulting_line is None:
        assert expected_result is None
    else:
        assert (
            expected_result is not None
        ), f"Did not expect to find common segment, got {resulting_line.asWkt()}"
        assert QgsGeometry(resulting_line).isGeosEqual(expected_result)


@pytest.mark.parametrize(
    ("geom", "segment", "expected_result"),
    [
        (
            QgsGeometry.fromWkt("PolygonZ ((0 0 0, 2 0 0, 2 2 0, 0 2 0, 0 0 0))"),
            QgsGeometry.fromWkt("LineStringZ (2 2 0, 0 2 0, 0 0 0, 0 0 0, 2 0 0)"),
            [2, 3, 4, 0, 1],
        ),
        (
            QgsGeometry.fromWkt("LineStringZ (0 0 0, 2 0 0, 4 0 0, 6 0 0)"),
            QgsGeometry.fromWkt("LineStringZ (2 0 0, 4 0 0)"),
            [1, 2],
        ),
        (
            QgsGeometry.fromWkt("LineStringZ (0 0 0, 2 0 0, 4 0 0, 6 0 0)"),
            QgsGeometry.fromWkt("LineStringZ (2 0 0, 5 0 0)"),
            None,
        ),
    ],
    ids=[
        "polygon boundary as segment",
        "line segment",
        "line when segment vertex does not match",
    ],
)
def test_get_vertex_indices_of_segment(
    geom: QgsGeometry, segment: QgsGeometry, expected_result: Optional[List[int]]
):
    assert not geom.isEmpty()
    assert not segment.isEmpty()

    if expected_result is None:
        with pytest.raises(ValueError):
            find_related._get_vertex_indices_of_segment(geom, segment)
    else:
        assert (
            find_related._get_vertex_indices_of_segment(geom, segment)
            == expected_result
        )


@pytest.mark.parametrize(
    ("vertex_indices", "expected_result"),
    [
        (
            [0, 1, 2, 3],
            False,
        ),
        (
            [3, 0, 1, 2],
            False,
        ),
        (
            [1, 0, 3, 2],
            True,
        ),
        (
            [3, 2, 1, 0],
            True,
        ),
    ],
    ids=[
        "from start point, not reversed",
        "from end point, not reversed",
        "from second point, is reversed",
        "from end point, is reversed",
    ],
)
def test_check_if_vertices_are_reversed(
    vertex_indices: List[int], expected_result: bool
):
    assert (
        find_related._check_if_vertices_are_reversed(vertex_indices) is expected_result
    )
