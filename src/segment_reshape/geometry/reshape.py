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

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Union

from qgis.core import (
    QgsFeature,
    QgsGeometry,
    QgsLineString,
    QgsPoint,
    QgsVectorLayer,
    QgsVertexId,
    QgsWkbTypes,
)

from segment_reshape.utils import clone_geometry_safely


class GeometryTransformationError(Exception):
    pass


@dataclass
class ReshapeCommonPart:
    layer: QgsVectorLayer
    feature: QgsFeature
    vertex_indices: list[int]
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


_current_edit_command_layers: ContextVar[list[QgsVectorLayer]] = ContextVar(
    "current_edit_command_layers"
)
_set_editable_layer_ids: ContextVar[set[str]] = ContextVar("set_editable_layer_ids")


@contextmanager
def _wrap_all_edit_commands() -> Iterator[None]:
    layers: list[QgsVectorLayer] = []
    set_editable_ids: set[str] = set()
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
    common_parts: list[ReshapeCommonPart],
    edges: list[ReshapeEdge],
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
    common_parts: list[ReshapeCommonPart],
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


def _reshape_geometry(  # noqa: C901, PLR0912
    original: QgsGeometry,
    vertex_indices: list[int],
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
        # since the indices are always the longest continuous segment on
        # the origin geometry, if the indices wrap around also at the index
        # list start/end, its known to be a closed geometry

        # handle the case when a full polygon ring is reshaped
        if (
            original.type() == QgsWkbTypes.GeometryType.PolygonGeometry
            and len(vertex_indices) > 1
            and vertex_indices[0] == vertex_indices[-1]
        ):
            # can just omit the last vertex from target indices since it will
            # either be a mid-ring index duplicated, or the polygon ring origin index
            # (first/last, which will be automatically matched even without explicitly
            # moving both indices)
            vertex_indices = vertex_indices[:-1]

            # support reshape both with a fully redrawn closed geometry, and even
            # without explicitly closing the geometry, similary to target indices
            # can just omit the last reshape geometry vertex if it was closed
            if reshape_geometry.isClosed():
                reshape_geometry = reshape_geometry.clone()
                if not reshape_geometry.deleteVertex(
                    QgsVertexId(0, 0, reshape_geometry.vertexCount(0, 0) - 1)
                ):
                    raise GeometryTransformationError(
                        f"could not delete last vertex on {reshape_geometry}"
                    )

        # handle the case when a full closed linestring in reshaped
        elif (
            original.type() == QgsWkbTypes.GeometryType.LineGeometry
            and len(vertex_indices) > 1
            and vertex_indices[0] == vertex_indices[-1]
        ):
            # handle wraparound at origin by simply using the correct start index
            # instead of duplicating the max vertex index at the first index
            if vertex_indices[0] == max(vertex_indices):
                vertex_indices[0] = min(vertex_indices) - 1

            # handle wraparound at non-origin by simply rewriting the indices as if
            # the origin was at the new reshape geometry origin. this will essentially
            # scroll origin along the original geometryto the reshape start location,
            # assume this is not an issue since there was nothing connected at the
            # previous origin and something was connected at the new origin
            else:
                vertex_indices = list(
                    range(min(vertex_indices) - 1, max(vertex_indices) + 1)
                )

            # similarly to polygon rings support the reshape even without closing the
            # reshape geometry, by closing the reshape geometry manually here
            # NOTE: this way the code will never break closed linestring geometries,
            # even if that is what is wanted. TODO: possibly change this logic to
            # always require closed reshape geometries for closed origin geometries,
            # so that its an error to reshape a polygon ring without closing it?
            if not reshape_geometry.isClosed():
                reshape_geometry = reshape_geometry.clone()
                reshape_geometry.close()

        # handle case when a closed linestring in partially reshaped in a way that
        # the part origin wraparound falls inside the target vertex indices as
        # indicated by a gap in the otherwise continuous vertex indices
        elif (
            original.type() == QgsWkbTypes.GeometryType.LineGeometry
            and len(vertex_indices) > 1
            and any(
                abs(first - second) > 1
                for first, second in zip(vertex_indices[:-1], vertex_indices[1:])
            )
        ):
            # reshape will scroll the origin to be located at the start
            # of the reshape segment, to match the ends at the new position make
            # the wraparound vertex of the list the part minimum instead of the
            # part maximum (to insert the reshape as the start of the part), and
            # move the part maximum index to the start of the reshape to match
            # the new origin
            min_index, max_index = min(vertex_indices), max(vertex_indices)
            vertex_indices = [
                (min_index - 1 if i == max_index else i) for i in vertex_indices
            ]
            if not new.moveVertex(reshape_geometry.startPoint(), max_index):
                raise GeometryTransformationError(
                    f"could not move vertex {max_index}"
                    f" on {new} to {reshape_geometry.startPoint()}"
                )

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
    edges: list[ReshapeEdge], new_start: QgsPoint, new_end: QgsPoint
) -> None:
    # hold on to the updates so next iteration for same feature
    # uses the previous updated geometry instead of initial geometry
    previously_updated_geoms: dict[tuple[str, int], QgsGeometry] = {}

    for edge in edges:
        _set_editable_and_begin_edit_command_once(edge.layer)
        new_geometry = _move_vertex(
            previously_updated_geoms.get(
                (edge.layer.id(), edge.feature.id()), edge.feature.geometry()
            ),
            edge.vertex_index,
            new_start if edge.is_start else new_end,
        )
        _update_geometry_to_layer_feature(
            edge.layer,
            edge.feature,
            new_geometry,
        )
        previously_updated_geoms[(edge.layer.id(), edge.feature.id())] = new_geometry


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
