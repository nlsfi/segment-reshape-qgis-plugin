import pytest
from qgis.core import QgsGeometry, QgsPoint

from segment_reshape.utils import vertices


@pytest.mark.parametrize(
    ("wkt", "expected_points"),
    [
        ("Point(0 0)", [QgsPoint(0, 0)]),
        ("MultiPoint(0 0, 1 1)", [QgsPoint(0, 0), QgsPoint(1, 1)]),
        ("LineString(0 0, 1 0, 2 0)", [QgsPoint(0, 0), QgsPoint(1, 0), QgsPoint(2, 0)]),
        (
            "Polygon(( 0 0, 0 3, 3 3, 3 0, 0 0), (1 1, 1 2, 2 2, 2 1, 1 1))",
            [
                QgsPoint(0, 0),
                QgsPoint(0, 3),
                QgsPoint(3, 3),
                QgsPoint(3, 0),
                QgsPoint(0, 0),
                QgsPoint(1, 1),
                QgsPoint(1, 2),
                QgsPoint(2, 2),
                QgsPoint(2, 1),
                QgsPoint(1, 1),
            ],
        ),
    ],
)
def test_vertices_function_returns_expected_points(
    wkt: str, expected_points: list[QgsPoint]
):
    geometry = QgsGeometry.fromWkt(wkt)
    for i, (_, point) in enumerate(vertices(geometry)):
        assert point == expected_points[i]


@pytest.mark.parametrize(
    "wkt",
    [
        "Point(0 0)",
        "MultiPoint(0 0, 1 1)",
        "LineString(0 0, 1 0, 2 0)",
        "MultiLineString((0 0, 1 0, 2 0), (3 0, 4 0))",
        "Polygon(( 0 0, 0 3, 3 3, 3 0, 0 0))",
        "Polygon(( 0 0, 0 3, 3 3, 3 0, 0 0), (1 1, 1 2, 2 2, 2 1, 1 1))",
        (
            "Multipolygon("
            "(( 0 0, 0 3, 3 3, 3 0, 0 0), (1 1, 1 2, 2 2, 2 1, 1 1)), "
            "(( 10 0, 10 3, 13 3, 13 0, 10 0), (11 1, 11 2, 12 2, 12 1, 11 1))"
            ")"
        ),
    ],
    ids=[
        "point",
        "multipoint",
        "linestring",
        "multilinestring",
        "simple polygon",
        "polygon with a hole",
        "multipolygons with holes",
    ],
)
def test_vertices_function_returns_expected_vertex_ids(wkt: str):
    """Tests that our vertices function has same logic for vertex_id:s than qgis"""

    geometry = QgsGeometry.fromWkt(wkt)
    for vertex_id, point in vertices(geometry):
        expected_point = geometry.vertexAt(vertex_id)
        assert point == expected_point
