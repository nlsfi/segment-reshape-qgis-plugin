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

from typing import Iterable, Iterator, List, Optional, Tuple, cast

from qgis.core import (
    QgsFeature,
    QgsFeatureRequest,
    QgsGeometry,
    QgsLineString,
    QgsMultiLineString,
    QgsPoint,
    QgsPointXY,
    QgsPolygon,
    QgsProject,
    QgsVectorLayer,
    QgsWkbTypes,
)

from segment_reshape.geometry.reshape import ReshapeCommonPart, ReshapeEdge

CommonGeometriesResult = Tuple[
    Optional[QgsLineString],
    List[ReshapeCommonPart],
    List[ReshapeEdge],
]


def find_segment_to_reshape(
    layer: QgsVectorLayer,
    feature: QgsFeature,
    segment_closest_to_trigger_location: Tuple[int, int],
    candidate_layers: Optional[List[QgsVectorLayer]] = None,
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
) -> List[QgsVectorLayer]:
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
    candidate_layers: Optional[List[QgsVectorLayer]] = None,
) -> List[Tuple[QgsVectorLayer, QgsFeature]]:
    if candidate_layers is None:
        candidate_layers = _find_topologically_related_project_layers(layer)

    # distance within 0 should work, bbox rect would return excess stuff,
    # feature must have equal vertex anyway for it be considered
    request = QgsFeatureRequest()
    request.setDistanceWithin(feature.geometry(), 0)

    return [
        (candidate_layer, candidate_feature)
        for candidate_layer in candidate_layers
        for candidate_feature in candidate_layer.getFeatures(request)
        if not _is_same_feature(
            candidate_layer,
            candidate_feature,
            layer,
            feature,
        )
    ]


def _as_point_or_line_components(geom: QgsGeometry) -> Iterator[QgsGeometry]:
    for part in geom.constParts():
        if isinstance(part, QgsPolygon):
            yield QgsGeometry(part.exteriorRing().clone())
            for ring_index in range(part.numInteriorRings()):
                yield QgsGeometry(part.interiorRing(ring_index).clone())
        else:
            yield QgsGeometry(part.clone())


def _get_containing_component(
    geom: QgsGeometry, contains_geom: QgsGeometry
) -> QgsGeometry:
    for component in _as_point_or_line_components(geom):
        if component.contains(contains_geom):
            return component

    raise ValueError(
        f"could not find component of {geom} that contains {contains_geom}"
    )


def _get_line_component_for_part_and_ring(
    geom: QgsGeometry, part_index: int, ring_index: int
) -> QgsGeometry:
    try:
        part = list(geom.constParts())[part_index]
        if not isinstance(part, QgsPolygon):
            return QgsGeometry(part.clone())
        elif ring_index == 0:
            return QgsGeometry(part.exteriorRing().clone())
        else:
            return QgsGeometry(part.interiorRing(ring_index - 1).clone())
    except IndexError:
        raise ValueError(
            f"could not extract part {part_index} ring {ring_index} of {geom}"
        )


def _split_at_position(geom: QgsGeometry, position: QgsPoint) -> QgsGeometry:
    new = QgsMultiLineString()
    collected = QgsLineString()
    for vertex in geom.vertices():
        collected.addVertex(vertex.clone())
        if vertex == position:
            if collected.vertexCount() > 1:
                new.addGeometry(collected)
            collected = QgsLineString([vertex.clone()])
    if collected.vertexCount() > 1:
        new.addGeometry(collected)
    return QgsGeometry(new)


def _find_vertex_indices(geom: QgsGeometry, positions: Iterable[QgsPoint]) -> List[int]:
    indices: List[int] = []
    for position in positions:
        distance, vertex_index = geom.closestVertexWithContext(QgsPointXY(position))
        if distance != 0:
            raise ValueError(f"could not find vertex index for {position} from {geom}")
        indices.append(vertex_index)
    return indices


def _check_if_vertices_are_reversed(vertex_indices: List[int]) -> bool:
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
    related_features_by_layer: List[Tuple[QgsVectorLayer, QgsFeature]],
    main_feature_segment: Tuple[int, int],
) -> CommonGeometriesResult:
    # for now lines and polygons are supported as the trigger
    if main_feature.geometry().type() not in [
        QgsWkbTypes.GeometryType.LineGeometry,
        QgsWkbTypes.GeometryType.PolygonGeometry,
    ]:
        raise ValueError(
            f"unsupported source geometry type {main_feature.geometry().type()}"
        )

    from_vertex, to_vertex = main_feature_segment
    trigger_geometry = main_feature.geometry()
    trigger_segment = QgsGeometry.fromPolyline(
        [
            trigger_geometry.vertexAt(from_vertex).clone(),
            trigger_geometry.vertexAt(to_vertex).clone(),
        ]
    )
    success, to_vertex_id = trigger_geometry.vertexIdFromVertexNr(to_vertex)
    if not success:
        raise ValueError(
            f"could not find vertex details by index {to_vertex}"
            f" from {trigger_geometry}"
        )

    # start with the full line component as the result
    result = _get_line_component_for_part_and_ring(
        trigger_geometry, to_vertex_id.part, to_vertex_id.ring
    )

    common_part_candidates: List[Tuple[QgsVectorLayer, QgsFeature]] = []
    possible_edge_candidates: List[Tuple[QgsVectorLayer, QgsFeature, QgsGeometry]] = []

    for layer, feature in related_features_by_layer:
        for component in _as_point_or_line_components(feature.geometry()):

            # found a point which can only act as a break to the segment,
            # split the result to multipart line at the point if possible
            # -> collect as possible edge
            if component.type() == QgsWkbTypes.GeometryType.PointGeometry:
                result = _split_at_position(result, component.vertexAt(0))
                possible_edge_candidates.append((layer, feature, component))

            # found a line that shares the trigger segment, intersection to
            # reduce the result to the part that is shared as common segment
            # -> collect as common part
            elif component.contains(trigger_segment):
                # TODO: how to handle partial linear intersection where the
                # component contains the trigger, but the containment is either
                # within one longer segment or multiple shorter segments, and
                # vertices will not match (same pair in same or reversed order)
                result = result.intersection(component)
                # intersection along multiple segments will return each segment
                # as a separate part, merge parts here to keep the continuous line
                if result.isMultipart():
                    result = result.mergeLines()
                common_part_candidates.append((layer, feature))

            # found a line that may intersect along the result but not along
            # trigger segment, cross or only touch the result, difference to reduce
            # the result by removing parts of intersection along the result or
            # by breaking the result to parts at the crossings or touch locations
            # -> collect as possible edge
            else:
                # TODO: how to handle partial linear intersection where the result
                # is reduced possibly even along the trigger segment, if the component
                # has an vertex that falls along a segment of the result
                # TODO: how to handle non-vertex touch/cross where the result will
                # be split on the touching vertex or crossing segment even if there
                # is no vertex on result
                result = result.difference(component)
                possible_edge_candidates.append((layer, feature, component))

            # TODO: how to handle ring-like lines which may result in a split
            # at a valid split point, and an existing split at the ring boundary,
            # and after the split or difference operation we want to keep the
            # continuous line around the boundary with with split or parts removed,
            # since this conflicts with the points or difference operation results
            # for crossing on touching lines which only result in breaks and will
            # be rejoined if mergeLines is ran without special checks
            # if result.isMultipart():
            #     result = result.mergeLines()

            # if result is now multipart due to the geometry operations,
            # only keep the component which contains the trigger segment
            # for polygon rings the two parts might overlap with
            # the loop boundary, resulting in two continuous parts
            if result.isMultipart():
                result = _get_containing_component(result, trigger_segment)

    # result is now the longest common combined segment available from the trigger
    segment = cast(QgsLineString, result.constGet().clone())
    start, end = QgsGeometry(segment.startPoint()), QgsGeometry(segment.endPoint())

    common_parts: List[ReshapeCommonPart] = [
        ReshapeCommonPart(
            main_feature_layer,
            main_feature,
            _find_vertex_indices(main_feature.geometry(), segment.vertices()),
            is_reversed=False,
        )
    ]
    for common_part_candidate in common_part_candidates:
        layer, feature = common_part_candidate
        indices = _find_vertex_indices(feature.geometry(), segment.vertices())
        common_parts.append(
            ReshapeCommonPart(
                layer,
                feature,
                indices,
                is_reversed=_check_if_vertices_are_reversed(indices),
            )
        )

    edges: List[ReshapeEdge] = []
    for possible_edge_candidate in possible_edge_candidates:
        layer, feature, component = possible_edge_candidate
        if start.intersects(component):
            indices = _find_vertex_indices(feature.geometry(), [segment.startPoint()])
            edges.append(
                ReshapeEdge(
                    layer,
                    feature,
                    indices[0],
                    is_start=True,
                )
            )
        if end.intersects(component):
            indices = _find_vertex_indices(feature.geometry(), [segment.endPoint()])
            edges.append(
                ReshapeEdge(
                    layer,
                    feature,
                    indices[0],
                    is_start=False,
                )
            )

    return segment, common_parts, edges
