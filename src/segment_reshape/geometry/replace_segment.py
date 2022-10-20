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

from dataclasses import dataclass
from typing import Any, List

from qgis.core import QgsFeature, QgsGeometry, QgsLineString, QgsPoint, QgsVectorLayer


@dataclass
class SegmentCommonFeature:
    layer: QgsVectorLayer
    feature: QgsFeature
    from_vertex_id: Any
    to_vertex_id: Any
    reversed: bool


@dataclass
class SegmentEndPointFeature:
    layer: QgsVectorLayer
    feature: QgsFeature
    vertex_id: Any
    is_start: bool


def make_edits_for_new_segment(
    common_features: List[SegmentCommonFeature],
    end_point_features: List[SegmentEndPointFeature],
    new_segment: QgsLineString,
) -> None:
    pass

    # begineditcommand

    # _replace_segments
    # _replace_vertices

    # endeditcommand


def _replace_segments(
    to_replace: List[SegmentCommonFeature], new_segment: QgsLineString
) -> None:
    pass

    # for result in to_replace
    #   set editable
    #   do edit (replace_geometry_partially())
    #   if reversed: kutsutaan replace_geometry_partially käännetyllä new_segmentillä


def _move_geometry_segment(
    original: QgsGeometry,
    from_vertex_id: Any,
    to_vertex_id: Any,
    new_segment: QgsLineString,
) -> QgsGeometry:
    pass


def _replace_vertices(
    to_replace: List[SegmentEndPointFeature], start: QgsPoint, end: QgsPoint
) -> None:
    pass

    # for result in to_replace
    #   set editable
    #   do edit (move_vertex(alkupiste))
    #   if start_or_end: kutsutaan move_vertex loppupisteellä


def _move_vertex(
    original: QgsGeometry, vertex_id: Any, new_position: QgsPoint
) -> QgsGeometry:
    pass
