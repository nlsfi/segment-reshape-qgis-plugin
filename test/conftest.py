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

from typing import Callable, Union
from unittest.mock import Mock

import pytest
from qgis.core import (
    QgsFeature,
    QgsFields,
    QgsGeometry,
    QgsMemoryProviderUtils,
    QgsProject,
    QgsVectorLayer,
    QgsVectorLayerUtils,
    QgsWkbTypes,
)
from qgis.gui import QgisInterface, QgsAdvancedDigitizingDockWidget
from segment_reshape.geometry.reshape import (
    _current_edit_command_layers,
    _set_editable_layer_ids,
)


@pytest.fixture(scope="session")
def qgis_iface(qgis_iface: QgisInterface):
    qgis_iface.cadDockWidget = Mock(  # type: ignore[method-assign]
        return_value=QgsAdvancedDigitizingDockWidget(qgis_iface.mapCanvas())
    )
    return qgis_iface


@pytest.fixture()
def _use_topological_editing(qgis_new_project: None):
    QgsProject.instance().setTopologicalEditing(True)
    yield
    QgsProject.instance().setTopologicalEditing(False)


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
) -> Callable[[str, list[str]], tuple[QgsVectorLayer, list[QgsFeature]]]:
    def _factory(
        name: str, geoms: list[Union[str, QgsGeometry]]
    ) -> tuple[QgsVectorLayer, list[QgsFeature]]:
        geometries = [
            QgsGeometry.fromWkt(geom) if isinstance(geom, str) else geom
            for geom in geoms
        ]
        layer = memory_layer_factory(name, geometries[0].wkbType())
        features = [
            QgsVectorLayerUtils.createFeature(layer, geom) for geom in geometries
        ]
        _, added_features = layer.dataProvider().addFeatures(features)
        return layer, added_features

    return _factory


@pytest.fixture()
def _with_editable_layers():
    set_editable_ids: set[str] = set()
    layers: list[QgsVectorLayer] = []
    editable_ids_token = _set_editable_layer_ids.set(set_editable_ids)
    token = _current_edit_command_layers.set(layers)
    try:
        yield
    finally:
        _current_edit_command_layers.reset(token)
        _set_editable_layer_ids.reset(editable_ids_token)
