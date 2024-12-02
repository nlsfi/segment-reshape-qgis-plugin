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

from collections.abc import Callable

import pytest
from qgis.core import QgsFeature, QgsGeometry, QgsLineString, QgsProject, QgsVectorLayer

from segment_reshape.geometry.reshape import make_reshape_edits
from segment_reshape.topology.find_related import find_segment_to_reshape


def _normalize_wkt(wkt: str) -> str:
    g = QgsGeometry.fromWkt(wkt)
    g.normalize()
    return g.asWkt()


def _assert_layer_geoms(layer: QgsVectorLayer, expected_geom_wkts: list[str]):
    __tracebackhide__ = True

    layer_wkts = [_normalize_wkt(f.geometry().asWkt()) for f in layer.getFeatures()]
    expected_wkts = [_normalize_wkt(wkt) for wkt in expected_geom_wkts]

    assert layer_wkts == expected_wkts


@pytest.mark.usefixtures("qgis_new_project", "_use_topological_editing")
@pytest.mark.parametrize(
    argnames="edited_feature_name",
    argvalues=["base", "hole"],
    ids=["base-edited", "hole-edited"],
)
def test_polygon_hole_filled_with_other_polygon_same_layer_both_reshaped(
    preset_features_layer_factory: Callable[
        [str, list[str]], tuple[QgsVectorLayer, list[QgsFeature]]
    ],
    edited_feature_name: str,
):
    layer, features = preset_features_layer_factory(
        "l1",
        [
            "POLYGON((0 0, 0 100, 100 100, 100 0, 0 0), (10 10, 10 20, 20 20, 20 10, 10 10))",  # base
            "POLYGON((10 10, 10 20, 20 20, 20 10, 10 10))",  # hole filled by polygon
        ],
    )

    edited_feature = {"base": features[0], "hole": features[1]}[edited_feature_name]
    edited_indices = {"base": (5, 6), "hole": (0, 1)}[edited_feature_name]

    QgsProject.instance().addMapLayer(layer)

    _, common_parts, edges = find_segment_to_reshape(
        layer,
        edited_feature,
        edited_indices,
    )

    make_reshape_edits(
        common_parts,
        edges,
        QgsLineString(
            [(11.0, 11.0), (11.0, 19.0), (19.0, 19.0), (19.0, 11.0), (11.0, 11.0)]
        ),
    )

    _assert_layer_geoms(
        layer,
        [
            "POLYGON((0 0, 0 100, 100 100, 100 0, 0 0), (11 11, 11 19, 19 19, 19 11, 11 11))",  # base
            "POLYGON((11 11, 11 19, 19 19, 19 11, 11 11))",  # hole filled by polygon
        ],
    )


@pytest.mark.usefixtures("qgis_new_project", "_use_topological_editing")
@pytest.mark.parametrize(
    argnames="edited_feature_name",
    argvalues=["base", "hole"],
    ids=["base-edited", "hole-edited"],
)
def test_polygon_hole_filled_with_other_polygon_other_layer_both_reshaped(
    preset_features_layer_factory: Callable[
        [str, list[str]], tuple[QgsVectorLayer, list[QgsFeature]]
    ],
    edited_feature_name: str,
):
    layer, (base,) = preset_features_layer_factory(
        "l1",
        [
            "POLYGON((0 0, 0 100, 100 100, 100 0, 0 0), (10 10, 10 20, 20 20, 20 10, 10 10))",  # base
        ],
    )
    other_layer, (hole,) = preset_features_layer_factory(
        "l2",
        [
            "POLYGON((10 10, 10 20, 20 20, 20 10, 10 10))",  # hole filled by polygon
        ],
    )

    QgsProject.instance().addMapLayers([layer, other_layer])

    edited_layer = {"base": layer, "hole": other_layer}[edited_feature_name]
    edited_feature = {"base": base, "hole": hole}[edited_feature_name]
    edited_indices = {"base": (5, 6), "hole": (0, 1)}[edited_feature_name]

    _, common_parts, edges = find_segment_to_reshape(
        edited_layer,
        edited_feature,
        edited_indices,
    )

    make_reshape_edits(
        common_parts,
        edges,
        QgsLineString(
            [(11.0, 11.0), (11.0, 19.0), (19.0, 19.0), (19.0, 11.0), (11.0, 11.0)]
        ),
    )

    _assert_layer_geoms(
        layer,
        [
            "POLYGON((0 0, 0 100, 100 100, 100 0, 0 0), (11 11, 11 19, 19 19, 19 11, 11 11))",  # base
        ],
    )
    _assert_layer_geoms(
        other_layer,
        [
            "POLYGON((11 11, 11 19, 19 19, 19 11, 11 11))",  # hole filled by polygon
        ],
    )


@pytest.mark.usefixtures("qgis_new_project", "_use_topological_editing")
@pytest.mark.parametrize(
    argnames="edited_feature_name",
    argvalues=["base", "hole"],
    ids=["base-edited", "hole-edited"],
)
def test_polygon_hole_filled_with_closed_linestring_both_reshaped(
    preset_features_layer_factory: Callable[
        [str, list[str]], tuple[QgsVectorLayer, list[QgsFeature]]
    ],
    edited_feature_name: str,
):
    layer, (base,) = preset_features_layer_factory(
        "l1",
        [
            "POLYGON((0 0, 0 100, 100 100, 100 0, 0 0), (10 10, 10 20, 20 20, 20 10, 10 10))",  # base
        ],
    )
    other_layer, (hole,) = preset_features_layer_factory(
        "l2",
        [
            "LINESTRING(10 10, 10 20, 20 20, 20 10, 10 10)",  # hole filled by closed line
        ],
    )

    QgsProject.instance().addMapLayers([layer, other_layer])

    edited_layer = {"base": layer, "hole": other_layer}[edited_feature_name]
    edited_feature = {"base": base, "hole": hole}[edited_feature_name]
    edited_indices = {"base": (5, 6), "hole": (0, 1)}[edited_feature_name]

    _, common_parts, edges = find_segment_to_reshape(
        edited_layer,
        edited_feature,
        edited_indices,
    )

    make_reshape_edits(
        common_parts,
        edges,
        QgsLineString(
            [(11.0, 11.0), (11.0, 19.0), (19.0, 19.0), (19.0, 11.0), (11.0, 11.0)]
        ),
    )

    _assert_layer_geoms(
        layer,
        [
            "POLYGON((0 0, 0 100, 100 100, 100 0, 0 0), (11 11, 11 19, 19 19, 19 11, 11 11))",  # base
        ],
    )
    _assert_layer_geoms(
        other_layer,
        [
            "LINESTRING(11 11, 11 19, 19 19, 19 11, 11 11)",  # hole filled closed line
        ],
    )


@pytest.mark.usefixtures("qgis_new_project", "_use_topological_editing")
@pytest.mark.parametrize(
    argnames="edited_feature_name",
    argvalues=["base", "hole1", "hole2", "hole3"],
    ids=[
        "base-edited",
        "same-layer-hole-edited",
        "other-layer-hole-edited",
        "other-layer-line-edited",
    ],
)
def test_polygon_hole_filled_by_multiple_features_all_reshaped(
    preset_features_layer_factory: Callable[
        [str, list[str]], tuple[QgsVectorLayer, list[QgsFeature]]
    ],
    edited_feature_name: str,
):
    layer1, (base, hole1) = preset_features_layer_factory(
        "l1",
        [
            "POLYGON((0 0, 0 100, 100 100, 100 0, 0 0), (10 10, 10 20, 20 20, 20 10, 10 10))",  # base
            "POLYGON((10 10, 10 20, 20 20, 20 10, 10 10))",  # hole filled by polygon
        ],
    )
    layer2, (hole2,) = preset_features_layer_factory(
        "l2",
        [
            "POLYGON((10 10, 10 20, 20 20, 20 10, 10 10))",  # hole filled by polygon
        ],
    )
    layer3, (hole3,) = preset_features_layer_factory(
        "l3",
        [
            "LINESTRING(10 10, 10 20, 20 20, 20 10, 10 10)",  # hole filled by closed line
        ],
    )

    QgsProject.instance().addMapLayers([layer1, layer2, layer3])

    edited_layer = {"base": layer1, "hole1": layer1, "hole2": layer2, "hole3": layer3}[
        edited_feature_name
    ]
    edited_feature = {"base": base, "hole1": hole1, "hole2": hole2, "hole3": hole3}[
        edited_feature_name
    ]
    edited_indices = {
        "base": (5, 6),
        "hole1": (0, 1),
        "hole2": (0, 1),
        "hole3": (0, 1),
    }[edited_feature_name]

    _, common_parts, edges = find_segment_to_reshape(
        edited_layer,
        edited_feature,
        edited_indices,
    )

    make_reshape_edits(
        common_parts,
        edges,
        QgsLineString(
            [(11.0, 11.0), (11.0, 19.0), (19.0, 19.0), (19.0, 11.0), (11.0, 11.0)]
        ),
    )

    _assert_layer_geoms(
        layer1,
        [
            "POLYGON((0 0, 0 100, 100 100, 100 0, 0 0), (11 11, 11 19, 19 19, 19 11, 11 11))",  # base
            "POLYGON((11 11, 11 19, 19 19, 19 11, 11 11))",  # hole filled by polygon
        ],
    )
    _assert_layer_geoms(
        layer2,
        [
            "POLYGON((11 11, 11 19, 19 19, 19 11, 11 11))",  # hole filled by polygon
        ],
    )
    _assert_layer_geoms(
        layer3,
        [
            "LINESTRING(11 11, 11 19, 19 19, 19 11, 11 11)",  # hole filled closed line
        ],
    )


@pytest.mark.usefixtures("qgis_new_project", "_use_topological_editing")
@pytest.mark.parametrize(
    argnames="edited_feature_name",
    argvalues=["base", "hole"],
    ids=["base-edited", "hole-edited"],
)
def test_polygon_hole_filled_partially_with_other_polygon_both_reshaped(
    preset_features_layer_factory: Callable[
        [str, list[str]], tuple[QgsVectorLayer, list[QgsFeature]]
    ],
    edited_feature_name: str,
):
    layer, features = preset_features_layer_factory(
        "l1",
        [
            "POLYGON((0 0, 0 100, 100 100, 100 0, 0 0), (10 10, 10 20, 20 20, 20 10, 10 10))",  # base
            "POLYGON((10 10, 10 20, 20 20, 10 10))",  # hole partially filled by polygon
        ],
    )

    edited_feature = {"base": features[0], "hole": features[1]}[edited_feature_name]
    edited_indices = {"base": (5, 6), "hole": (0, 1)}[edited_feature_name]

    QgsProject.instance().addMapLayer(layer)

    _, common_parts, edges = find_segment_to_reshape(
        layer,
        edited_feature,
        edited_indices,
    )

    make_reshape_edits(
        common_parts,
        edges,
        QgsLineString([(11.0, 11.0), (11.0, 19.0), (19.0, 19.0)]),
    )

    _assert_layer_geoms(
        layer,
        [
            "POLYGON((0 0, 0 100, 100 100, 100 0, 0 0), (11 11, 11 19, 19 19, 20 10, 11 11))",  # base
            "POLYGON((11 11, 11 19, 19 19, 11 11))",  # hole filled by polygon
        ],
    )


@pytest.mark.usefixtures("qgis_new_project", "_use_topological_editing")
@pytest.mark.parametrize(
    argnames="edited_feature_name",
    argvalues=["base", "hole"],
    ids=["base-edited", "hole-edited"],
)
def test_polygon_hole_bordered_partially_with_linestring_both_reshaped(
    preset_features_layer_factory: Callable[
        [str, list[str]], tuple[QgsVectorLayer, list[QgsFeature]]
    ],
    edited_feature_name: str,
):
    layer, (base,) = preset_features_layer_factory(
        "l1",
        [
            "POLYGON((0 0, 0 100, 100 100, 100 0, 0 0), (10 10, 10 20, 20 20, 20 10, 10 10))",  # base
        ],
    )
    other_layer, (hole,) = preset_features_layer_factory(
        "l2",
        [
            "LINESTRING(10 10, 10 20, 20 20)",  # hole partially bordered by line
        ],
    )

    QgsProject.instance().addMapLayers([layer, other_layer])

    edited_layer = {"base": layer, "hole": other_layer}[edited_feature_name]
    edited_feature = {"base": base, "hole": hole}[edited_feature_name]
    edited_indices = {"base": (5, 6), "hole": (0, 1)}[edited_feature_name]

    _, common_parts, edges = find_segment_to_reshape(
        edited_layer,
        edited_feature,
        edited_indices,
    )

    make_reshape_edits(
        common_parts,
        edges,
        QgsLineString([(11.0, 11.0), (11.0, 19.0), (19.0, 19.0)]),
    )

    _assert_layer_geoms(
        layer,
        [
            "POLYGON((0 0, 0 100, 100 100, 100 0, 0 0), (11 11, 11 19, 19 19, 20 10, 11 11))",  # base
        ],
    )
    _assert_layer_geoms(
        other_layer,
        [
            "LINESTRING(11 11, 11 19, 19 19)",  # hole filled closed line
        ],
    )
