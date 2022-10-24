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

from typing import Union

from qgis.core import QgsGeometry, QgsLineString


def clone_geometry_safely(geometry: Union[QgsGeometry, QgsLineString]) -> QgsGeometry:
    if isinstance(geometry, QgsGeometry):
        original_abstract_geometry = geometry.get()
        cloned_original_abstract_geometry = original_abstract_geometry.clone()
        return QgsGeometry(cloned_original_abstract_geometry)
    else:
        cloned_original_abstract_geometry = geometry.clone()
        return QgsGeometry(cloned_original_abstract_geometry)
