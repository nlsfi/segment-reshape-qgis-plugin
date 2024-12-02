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
def test_two_equal_polygons_both_reshaped(
    preset_features_layer_factory: Callable[
        [str, list[str]], tuple[QgsVectorLayer, list[QgsFeature]]
    ],
):
    layer, (first,) = preset_features_layer_factory(
        "l1",
        [
            "POLYGON((0 0, 0 100, 100 100, 100 0, 0 0))",
        ],
    )
    other_layer, _ = preset_features_layer_factory(
        "l2",
        [
            "POLYGON((0 0, 0 100, 100 100, 100 0, 0 0))",
        ],
    )

    QgsProject.instance().addMapLayers([layer, other_layer])

    _, common_parts, edges = find_segment_to_reshape(
        layer,
        first,
        (0, 1),
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
            "POLYGON((11 11, 11 19, 19 19, 19 11, 11 11))",
        ],
    )
    _assert_layer_geoms(
        other_layer,
        [
            "POLYGON((11 11, 11 19, 19 19, 19 11, 11 11))",
        ],
    )


@pytest.mark.usefixtures("qgis_new_project", "_use_topological_editing")
@pytest.mark.parametrize(
    argnames="edited_feature_name",
    argvalues=["base", "border"],
    ids=["base-edited", "border-edited"],
)
def test_polygon_bordered_by_closed_linestring_both_reshaped(
    preset_features_layer_factory: Callable[
        [str, list[str]], tuple[QgsVectorLayer, list[QgsFeature]]
    ],
    edited_feature_name: str,
):
    layer, (base,) = preset_features_layer_factory(
        "l1",
        [
            "POLYGON((10 10, 10 20, 20 20, 20 10, 10 10))",
        ],
    )
    other_layer, (border,) = preset_features_layer_factory(
        "l2",
        [
            "LINESTRING(10 10, 10 20, 20 20, 20 10, 10 10)",
        ],
    )

    QgsProject.instance().addMapLayers([layer, other_layer])

    edited_layer = {"base": layer, "border": other_layer}[edited_feature_name]
    edited_feature = {"base": base, "border": border}[edited_feature_name]
    edited_indices = {"base": (0, 1), "border": (0, 1)}[edited_feature_name]

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
            "POLYGON((11 11, 11 19, 19 19, 19 11, 11 11))",
        ],
    )
    _assert_layer_geoms(
        other_layer,
        [
            "LINESTRING(11 11, 11 19, 19 19, 19 11, 11 11)",
        ],
    )
