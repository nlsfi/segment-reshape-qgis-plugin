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
def test_simple_line_reshape(
    preset_features_layer_factory: Callable[
        [str, list[str]], tuple[QgsVectorLayer, list[QgsFeature]]
    ]
):
    layer, (feature, *_) = preset_features_layer_factory(
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

    # Selected segment is from base feature index 1 to index 2 (LINESTRING(1 1, 2 2))
    segment, common_parts, edges = find_segment_to_reshape(
        layer,
        feature,
        (1, 2),
    )

    assert segment is not None
    assert len(common_parts) == 3
    assert len(edges) == 2

    make_reshape_edits(common_parts, edges, QgsLineString([(1.1, 1.1), (2.2, 2.2)]))

    _assert_layer_geoms(
        layer,
        [
            "LINESTRING(0 0, 1.1 1.1, 2.2 2.2, 3 3)",
            "LINESTRING(1 0, 1.1 1.1, 2.2 2.2, 2 0)",
            "LINESTRING(0 2, 2.2 2.2, 1.1 1.1, 0 1)",
            "LINESTRING(0 0, 1.1 1.1)",
            "LINESTRING(2.2 2.2, 3 3)",
        ],
    )
