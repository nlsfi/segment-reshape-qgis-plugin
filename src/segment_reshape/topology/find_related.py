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

from collections.abc import Iterable, Iterator
from typing import NamedTuple, Optional

from qgis.core import (
    QgsAbstractGeometry,
    QgsFeature,
    QgsFeatureRequest,
    QgsGeometry,
    QgsLineString,
    QgsPoint,
    QgsPolygon,
    QgsProject,
    QgsVectorLayer,
    QgsWkbTypes,
)

from segment_reshape.geometry.reshape import ReshapeCommonPart, ReshapeEdge
from segment_reshape.utils.geometry_utils import vertices

Point = tuple[float, float]
Segment = frozenset[Point]


class CommonGeometriesResult(NamedTuple):
    segment: Optional[QgsLineString]
    common_parts: list[ReshapeCommonPart]
    edges: list[ReshapeEdge]


def find_segment_to_reshape(
    layer: QgsVectorLayer,
    feature: QgsFeature,
    segment_closest_to_trigger_location: tuple[int, int],
    candidate_layers: Optional[list[QgsVectorLayer]] = None,
) -> CommonGeometriesResult:
    """
    Calculates the line segment between features that share equal
    sequence of vertices along their edges at the segment closest to trigger location.

    By default uses project layers if topological editing is enabled, custom
    list can be provided in `candidate_layers`.
    """

    related_features = find_related_features(layer, feature, candidate_layers)

    return get_common_geometries(
        layer, feature, related_features, segment_closest_to_trigger_location
    )


def _find_topologically_related_project_layers(
    layer: QgsVectorLayer,
) -> list[QgsVectorLayer]:
    if not QgsProject.instance().topologicalEditing():
        return []

    # no advanced config available for topological relations?
    return [
        project_layer
        for project_layer in QgsProject.instance().mapLayers().values()
        if isinstance(project_layer, QgsVectorLayer)
    ]


def _is_same_feature(
    layer: QgsVectorLayer,
    feature: QgsFeature,
    other_layer: QgsVectorLayer,
    other_feature: QgsFeature,
) -> bool:
    return layer.id() == other_layer.id() and feature.id() == other_feature.id()


def find_related_features(
    layer: QgsVectorLayer,
    feature: QgsFeature,
    candidate_layers: Optional[list[QgsVectorLayer]] = None,
) -> Iterator[tuple[QgsVectorLayer, QgsFeature]]:
    if candidate_layers is None:
        candidate_layers = _find_topologically_related_project_layers(layer)

    feature_geometry = feature.geometry()

    feature_geometry_engine = QgsGeometry.createGeometryEngine(
        feature_geometry.constGet()
    )
    feature_geometry_engine.prepareGeometry()

    request = QgsFeatureRequest()
    request.setFilterRect(feature_geometry.boundingBox())  # noqa: SC200

    return (
        (candidate_layer, candidate_feature)
        for candidate_layer in candidate_layers
        for candidate_feature in candidate_layer.getFeatures(request)
        if not _is_same_feature(
            candidate_layer,
            candidate_feature,
            layer,
            feature,
        )
        and feature_geometry_engine.intersects(candidate_feature.geometry().constGet())
    )


def _as_point_or_line_components(geom: QgsGeometry) -> Iterator[QgsGeometry]:
    for part in geom.constParts():
        if isinstance(part, QgsPolygon):
            yield QgsGeometry(part.exteriorRing().clone())
            for ring_index in range(part.numInteriorRings()):
                yield QgsGeometry(part.interiorRing(ring_index).clone())
        else:
            yield QgsGeometry(part.clone())


def _get_geom_component_of_vertex(geom: QgsGeometry, vertex_id: int) -> QgsGeometry:
    """Returns the geometry component that vertex_id belongs to.

    Geometry component is either a single point or linestring from multipoint or
    multilinestring. In case of polygons geometry component is the edge linear ring
    that vertex_id belongs to.

    Args:
        geom (QgsGeometry): Input geometry
        vertex_id (int): Id of the vertex

    Raises:
        ValueError: Raised if vertex_id is not found from the input geometry.

    Returns:
        QgsGeometry: The geometry component vertex_id belongs to
    """

    success, vertex_details = geom.vertexIdFromVertexNr(vertex_id)
    if not success:
        raise ValueError(
            f"could not find vertex details by index {vertex_id}" f" from {geom}"
        )

    part = list(geom.constParts())[vertex_details.part]
    if isinstance(part, QgsPolygon):
        if vertex_details.ring == 0:
            return QgsGeometry(part.exteriorRing().clone())
        else:
            return QgsGeometry(part.interiorRing(vertex_details.ring - 1).clone())
    else:
        return QgsGeometry(part.clone())


def _find_vertex_indices(
    geom: QgsGeometry, segment: "QgsAbstractGeometry"
) -> list[int]:
    """Returns vertex indices of the geometry for matching vertices in the segment

    Args:
        geom (QgsGeometry): Geometry whose indices are requested
        segment (QgsAbstractGeometry): Segment geometry (usually QgsPolyline
            or QgsPoint) we want to match

    Raises:
        ValueError: Raises ValueError if some vertex from segment is not found
            from the geom.

    Returns:
        List[int]: List of vertex indices of the geometry in every matcing vertex
            of the segment
    """

    # Loop geometry only once and "cache" indices
    vertex_to_id_map = {
        (vertex.x(), vertex.y()): vertex_id for vertex_id, vertex in vertices(geom)
    }

    result: list[int] = []
    for segment_vertex in segment.vertices():
        try:
            result.append(vertex_to_id_map[(segment_vertex.x(), segment_vertex.y())])
        except KeyError:
            raise ValueError(
                f"could not find vertex index for {segment_vertex} from {geom}"
            ) from None

    return result


def _check_if_vertices_are_reversed(vertex_indices: list[int]) -> bool:
    first, second = vertex_indices[:2]
    return any(
        [
            (abs(first - second) == 1 and first > second),
            (abs(first - second) != 1 and first < second),
        ]
    )


def get_common_geometries(
    main_feature_layer: QgsVectorLayer,
    main_feature: QgsFeature,
    related_features_by_layer: Iterable[tuple[QgsVectorLayer, QgsFeature]],
    main_feature_segment: tuple[int, int],
) -> CommonGeometriesResult:
    # for now lines and polygons are supported as the trigger
    if main_feature.geometry().type() not in [
        QgsWkbTypes.GeometryType.LineGeometry,
        QgsWkbTypes.GeometryType.PolygonGeometry,
    ]:
        raise ValueError(
            f"unsupported source geometry type {main_feature.geometry().type()}"
        )

    from_vertex_id, to_vertex_id = main_feature_segment
    trigger_geometry = main_feature.geometry()

    from_vertex = trigger_geometry.vertexAt(from_vertex_id).clone()
    to_vertex = trigger_geometry.vertexAt(to_vertex_id).clone()

    # edge that was clicked
    trigger_segment = frozenset(
        (
            (from_vertex.x(), from_vertex.y()),
            (to_vertex.x(), to_vertex.y()),
        )
    )

    # line component that was clicked
    trigger_part = _get_geom_component_of_vertex(trigger_geometry, to_vertex_id)
    # start with the full line component as the result
    line_segments_to_keep = _as_line_segments(trigger_part)

    common_part_candidates: list[tuple[QgsVectorLayer, QgsFeature]] = []
    possible_edge_candidates: list[tuple[QgsVectorLayer, QgsFeature, QgsGeometry]] = []

    for layer, feature in related_features_by_layer:
        for component in _as_point_or_line_components(feature.geometry()):
            # found a point which can only act as a break to the segment
            # -> collect as possible edge
            if component.type() == QgsWkbTypes.GeometryType.PointGeometry:
                possible_edge_candidates.append((layer, feature, component))
                continue

            component_segments = _as_line_segments(component)

            # Found a line that contains the trigger segment.
            # Keep intersection to reduce the result to the part that is shared
            # as common segment.
            # -> collect as common part
            if trigger_segment in component_segments:
                line_segments_to_keep = line_segments_to_keep.intersection(
                    component_segments
                )
                common_part_candidates.append((layer, feature))

            # Found a line that does not contain trigger segment so remove it from
            # the result.
            # It might still touch the result
            # -> collect as possible edge
            else:
                line_segments_to_keep = line_segments_to_keep.difference(
                    component_segments
                )
                possible_edge_candidates.append((layer, feature, component))

    segment = _build_line_from_line_segment_set(
        trigger_part,
        line_segments_to_keep,
        trigger_segment,
        edge_candidate_geometries=[
            geometry for _, _, geometry in possible_edge_candidates
        ],
    )

    start, end = QgsGeometry(segment.startPoint()), QgsGeometry(segment.endPoint())

    common_parts: list[ReshapeCommonPart] = [
        ReshapeCommonPart(
            main_feature_layer,
            main_feature,
            _find_vertex_indices(main_feature.geometry(), segment),
            is_reversed=False,
        )
    ]
    for common_part_candidate in common_part_candidates:
        layer, feature = common_part_candidate
        indices = _find_vertex_indices(feature.geometry(), segment)
        common_parts.append(
            ReshapeCommonPart(
                layer,
                feature,
                indices,
                is_reversed=_check_if_vertices_are_reversed(indices),
            )
        )

    edges: list[ReshapeEdge] = []
    for possible_edge_candidate in possible_edge_candidates:
        layer, feature, component = possible_edge_candidate
        if start.intersects(component):
            indices = _find_vertex_indices(feature.geometry(), segment.startPoint())
            edges.append(
                ReshapeEdge(
                    layer,
                    feature,
                    indices[0],
                    is_start=True,
                )
            )
        if end.intersects(component):
            indices = _find_vertex_indices(feature.geometry(), segment.endPoint())
            edges.append(
                ReshapeEdge(
                    layer,
                    feature,
                    indices[0],
                    is_start=False,
                )
            )

    return CommonGeometriesResult(segment, common_parts, edges)


def _as_line_segments(geometry: QgsGeometry) -> set[Segment]:
    vertices = [(point.x(), point.y()) for point in geometry.vertices()]
    return {frozenset(line) for line in zip(vertices, vertices[1:])}


def _build_line_from_line_segment_set(
    trigger_part: QgsGeometry,
    line_segments_to_keep: set[Segment],
    trigger_segment: Segment,
    edge_candidate_geometries: list[QgsGeometry],
) -> QgsLineString:
    """Build a subline from trigger_part with constraints

    Builds a line which contains the trigger_segment and has only segments from
    line_segments_to_keep set and which is split at points where any geometry
    from edge_candidate_geometries touches the line.

    Args:
        trigger_part (QgsGeometry): Input geometry from where the subline is extracted
        line_segments_to_keep (Set[Segment]): Set of segments that the subline is build
            from
        trigger_segment (Segment): Edge which was clicked
        edge_candidate_geometries (List[QgsGeometry]): List of geometries which might
            act as break points

    Returns:
        QgsLineString: A sublinestring from the input geometry that follows the
            constraints
    """

    possible_split_points = {
        (vertex.x(), vertex.y())
        for geom in edge_candidate_geometries
        for vertex in geom.vertices()
    } & {(vertex.x(), vertex.y()) for vertex in trigger_part.vertices()}

    vertex_iterator = trigger_part.vertices()
    next_vertex_iterator = trigger_part.vertices()
    _ = next(next_vertex_iterator)  # advance the next_vertex iterator by one

    parts: list[list[QgsPoint]] = []
    current_part_vertices: list[QgsPoint] = []
    for vertex, next_vertex in zip(vertex_iterator, next_vertex_iterator):
        vertex_tuple = (vertex.x(), vertex.y())
        next_vertex_tuple = (next_vertex.x(), next_vertex.y())
        segment = frozenset((vertex_tuple, next_vertex_tuple))

        if segment in line_segments_to_keep:
            if segment == trigger_segment:
                trigger_in_part = len(parts)  # this will be the index of this part

            if not current_part_vertices:
                current_part_vertices.append(vertex.clone())
            current_part_vertices.append(next_vertex.clone())
        elif current_part_vertices:
            parts.append(current_part_vertices)
            current_part_vertices = []

        if next_vertex_tuple in possible_split_points and current_part_vertices:
            parts.append(current_part_vertices)
            current_part_vertices = []

    if current_part_vertices:
        parts.append(current_part_vertices)

    if _is_linear_ring_split(parts) and trigger_in_part in (0, len(parts) - 1):
        # The original geometry was a linear ring and was split at middle.
        # The trigger segment is in the first or last part so those must be merged.
        return QgsLineString(parts[-1] + parts[0][1:])
    else:
        return QgsLineString(parts[trigger_in_part])


def _is_linear_ring_split(parts: list[list[QgsPoint]]) -> bool:
    return len(parts) >= 2 and parts[0][0] == parts[-1][-1]  # noqa: PLR2004
