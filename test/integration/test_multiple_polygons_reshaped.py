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
            "POLYGON((5 5, 6 6, 7 5, 6 4, 5 5))",  # base
            "POLYGON((6 3, 0 5, 6 7, 6 6, 5 5, 6 4, 6 3))",  # left
            "POLYGON((6 3, 6 4, 7 5, 6 6, 6 7, 10 5, 6 3))",  # right
        ],
    )

    QgsProject.instance().addMapLayer(layer)

    _, common_parts, edges = find_segment_to_reshape(
        layer,
        feature,
        (0, 1),  # 5,5 - 6,6
    )

    make_reshape_edits(
        common_parts, edges, QgsLineString([(6.6, 4.4), (5.5, 5.5), (6.6, 6.6)])
    )

    _assert_layer_geoms(
        layer,
        [
            "POLYGON((5.5 5.5, 6.6 6.6, 7 5, 6.6 4.4, 5.5 5.5))",  # base
            "POLYGON((6 3, 0 5, 6 7, 6.6 6.6, 5.5 5.5, 6.6 4.4, 6 3))",  # left shared
            "POLYGON((6 3, 6.6 4.4, 7 5, 6.6 6.6, 6 7, 10 5, 6 3))",  # right at edges
        ],
    )
