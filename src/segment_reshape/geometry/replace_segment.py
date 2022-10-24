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

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator, List, Set, Union

from qgis.core import (
    QgsFeature,
    QgsGeometry,
    QgsLineString,
    QgsPoint,
    QgsVectorLayer,
    QgsWkbTypes,
)

from segment_reshape.utils import clone_geometry_safely


class GeometryTransformationError(Exception):
    pass


@dataclass
class SegmentCommonPart:
    layer: QgsVectorLayer
    feature: QgsFeature
    vertex_indices: List[int]
    is_reversed: bool


@dataclass
class SegmentEdge:
    layer: QgsVectorLayer
    feature: QgsFeature
    vertex_index: int
    is_start: bool


_current_edit_command_layers: ContextVar[List[QgsVectorLayer]] = ContextVar(
    "current_edit_command_layers"
)
_set_editable_layer_ids: ContextVar[Set[str]] = ContextVar("set_editable_layer_ids")


@contextmanager
def _wrap_all_edit_commands() -> Iterator[None]:
    layers: List[QgsVectorLayer] = []
    set_editable_ids: Set[str] = set()
    token = _current_edit_command_layers.set(layers)
    editable_ids_token = _set_editable_layer_ids.set(set_editable_ids)
    try:
        yield
        for layer in layers:
            layer.endEditCommand()
    except GeometryTransformationError as e:
        for layer in layers:
            layer.destroyEditCommand()
            if layer.id() in set_editable_ids:
                layer.rollBack()
        raise e
    finally:
        _current_edit_command_layers.reset(token)
        _set_editable_layer_ids.reset(editable_ids_token)


def _set_editable_and_begin_edit_command_once(layer: QgsVectorLayer) -> None:
    if layer.isEditCommandActive():
        return

    if not layer.isEditable():
        if not layer.startEditing():
            raise GeometryTransformationError(f"could not start editing on {layer}")
        _set_editable_layer_ids.get().add(layer.id())

    layer.beginEditCommand("Reshape segment")
    _current_edit_command_layers.get().append(layer)


def make_edits_for_new_segment(
    segment_common_parts: List[SegmentCommonPart],
    segment_edges: List[SegmentEdge],
    reshaped_segment: Union[QgsPoint, QgsLineString],
) -> None:
    # no crs support yet

    with _wrap_all_edit_commands():
        _replace_segments(segment_common_parts, reshaped_segment)
        if isinstance(reshaped_segment, QgsPoint):
            _move_edges(segment_edges, reshaped_segment, reshaped_segment)
        else:
            _move_edges(
                segment_edges,
                reshaped_segment.startPoint(),
                reshaped_segment.endPoint(),
            )


def _replace_segments(
    to_replace_common_parts: List[SegmentCommonPart],
    new_segment: Union[QgsPoint, QgsLineString],
) -> None:
    for segment_common_part in to_replace_common_parts:
        _set_editable_and_begin_edit_command_once(segment_common_part.layer)
        new_geometry = _replace_geometry_segment(
            segment_common_part.feature.geometry(),
            segment_common_part.vertex_indices,
            (
                new_segment.reversed()
                if isinstance(new_segment, QgsLineString)
                and segment_common_part.is_reversed
                else new_segment
            ),
        )
        _update_geometry_to_layer_feature(
            segment_common_part.layer,
            segment_common_part.feature,
            new_geometry,
        )


def _replace_geometry_segment(
    original: QgsGeometry,
    vertex_indices: List[int],
    reshaped_segment: Union[QgsPoint, QgsLineString],
) -> QgsGeometry:
    new = clone_geometry_safely(original)

    if isinstance(reshaped_segment, QgsPoint):
        # move the first replaced vertex
        if not new.moveVertex(reshaped_segment, vertex_indices[0]):
            raise GeometryTransformationError(
                f"could not move vertex {vertex_indices[0]}"
                f" on {new} to {reshaped_segment}"
            )
        # delete rest in reverse order
        for deleted_index in sorted(vertex_indices[1:], reverse=True):
            if not new.deleteVertex(deleted_index):
                raise GeometryTransformationError(
                    f"could not delete vertex {deleted_index} on {new}"
                )

    else:
        # cleanup last in case a full polygon is redrawn
        if (
            original.type() == QgsWkbTypes.GeometryType.PolygonGeometry
            and reshaped_segment.endPoint() == reshaped_segment.startPoint()
        ):
            reshaped_segment = QgsLineString(list(reshaped_segment.vertices())[:-1])

        # add vertices before the first replaced vertex
        min_vertex_index = min(vertex_indices)
        for new_vertex_index, new_vertex in enumerate(reshaped_segment.vertices()):
            add_before_index = min_vertex_index + new_vertex_index
            if not new.insertVertex(new_vertex, add_before_index):
                raise GeometryTransformationError(
                    f"could not insert {new_vertex} vertex"
                    f" before {add_before_index} on {new}"
                )
        # delete replace vertices that were moved by the added count in reverse order
        added_vertex_count = reshaped_segment.vertexCount()
        for original_delete_index in sorted(vertex_indices, reverse=True):
            deleted_index = original_delete_index + added_vertex_count
            if not new.deleteVertex(deleted_index):
                raise GeometryTransformationError(
                    f"could not delete vertex {deleted_index} on {new}"
                )

    return new


def _move_edges(
    to_move_edges: List[SegmentEdge], new_start: QgsPoint, new_end: QgsPoint
) -> None:
    for segment_edge in to_move_edges:
        _set_editable_and_begin_edit_command_once(segment_edge.layer)
        new_geometry = _move_vertex(
            segment_edge.feature.geometry(),
            segment_edge.vertex_index,
            new_start if segment_edge.is_start else new_end,
        )
        _update_geometry_to_layer_feature(
            segment_edge.layer,
            segment_edge.feature,
            new_geometry,
        )


def _move_vertex(
    original: QgsGeometry, vertex_index: int, new_position: QgsPoint
) -> QgsGeometry:
    new = clone_geometry_safely(original)
    if not new.moveVertex(new_position, vertex_index):
        raise GeometryTransformationError(
            f"could not move vertex {vertex_index} on {new} to {new_position}"
        )
    return new


def _update_geometry_to_layer_feature(
    layer: QgsVectorLayer,
    feature: QgsFeature,
    new_geometry: QgsGeometry,
) -> None:
    if not layer.changeGeometry(
        feature.id(),
        new_geometry,
    ):
        raise GeometryTransformationError(
            f"could not update geometry {new_geometry} to fid {feature.id()} on {layer}"
        )
