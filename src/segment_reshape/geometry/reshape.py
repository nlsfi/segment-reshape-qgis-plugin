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
class ReshapeCommonPart:
    layer: QgsVectorLayer
    feature: QgsFeature
    vertex_indices: List[int]
    is_reversed: bool
    """
    Indicates if this feature's geometry is digitized
    in reverse direction to the shared segment.
    """


@dataclass
class ReshapeEdge:
    layer: QgsVectorLayer
    feature: QgsFeature
    vertex_index: int
    is_start: bool
    """
    Indicates if this feature's vertex is at the
    start (or end) of the shared segment.
    """


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


def make_reshape_edits(
    common_parts: List[ReshapeCommonPart],
    edges: List[ReshapeEdge],
    reshape_geometry: Union[QgsPoint, QgsLineString],
) -> None:
    """
    Reshape the provided common parts and edges, so that common part shared
    vertex indices are replaced by `reshape_geometry` and edges are moved
    to match `reshape_geometry`.

    Edits are made in a single edit command for each layer, and layers are
    set editable automatically if necessary.

    Raises `GeometryTransformationError` if operation fails.
    """

    # no crs support yet

    with _wrap_all_edit_commands():
        _reshape_common_parts(common_parts, reshape_geometry)
        if isinstance(reshape_geometry, QgsPoint):
            _move_edges(edges, reshape_geometry, reshape_geometry)
        else:
            _move_edges(
                edges,
                reshape_geometry.startPoint(),
                reshape_geometry.endPoint(),
            )


def _reshape_common_parts(
    common_parts: List[ReshapeCommonPart],
    reshape_geometry: Union[QgsPoint, QgsLineString],
) -> None:
    for common_part in common_parts:
        _set_editable_and_begin_edit_command_once(common_part.layer)
        new_geometry = _reshape_geometry(
            common_part.feature.geometry(),
            common_part.vertex_indices,
            (
                reshape_geometry.reversed()
                if isinstance(reshape_geometry, QgsLineString)
                and common_part.is_reversed
                else reshape_geometry
            ),
        )
        _update_geometry_to_layer_feature(
            common_part.layer,
            common_part.feature,
            new_geometry,
        )


def _reshape_geometry(
    original: QgsGeometry,
    vertex_indices: List[int],
    reshape_geometry: Union[QgsPoint, QgsLineString],
) -> QgsGeometry:
    new = clone_geometry_safely(original)

    if isinstance(reshape_geometry, QgsPoint):
        # move the first replaced vertex
        if not new.moveVertex(reshape_geometry, vertex_indices[0]):
            raise GeometryTransformationError(
                f"could not move vertex {vertex_indices[0]}"
                f" on {new} to {reshape_geometry}"
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
            and reshape_geometry.endPoint() == reshape_geometry.startPoint()
        ):
            reshape_geometry = QgsLineString(list(reshape_geometry.vertices())[:-1])

        # add vertices before the first replaced vertex
        min_vertex_index = min(vertex_indices)
        for new_vertex_index, new_vertex in enumerate(reshape_geometry.vertices()):
            add_before_index = min_vertex_index + new_vertex_index
            if not new.insertVertex(new_vertex, add_before_index):
                raise GeometryTransformationError(
                    f"could not insert {new_vertex} vertex"
                    f" before {add_before_index} on {new}"
                )
        # delete replace vertices that were moved by the added count in reverse order
        added_vertex_count = reshape_geometry.vertexCount()
        for original_delete_index in sorted(vertex_indices, reverse=True):
            deleted_index = original_delete_index + added_vertex_count
            if not new.deleteVertex(deleted_index):
                raise GeometryTransformationError(
                    f"could not delete vertex {deleted_index} on {new}"
                )

    return new


def _move_edges(
    edges: List[ReshapeEdge], new_start: QgsPoint, new_end: QgsPoint
) -> None:
    for edge in edges:
        _set_editable_and_begin_edit_command_once(edge.layer)
        new_geometry = _move_vertex(
            edge.feature.geometry(),
            edge.vertex_index,
            new_start if edge.is_start else new_end,
        )
        _update_geometry_to_layer_feature(
            edge.layer,
            edge.feature,
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
