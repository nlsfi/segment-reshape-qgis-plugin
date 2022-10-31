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

from typing import List, Optional, Tuple

from qgis.core import (
    QgsFeature,
    QgsFeatureRequest,
    QgsGeometry,
    QgsLineString,
    QgsPoint,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
    QgsWkbTypes,
)

from segment_reshape.geometry.reshape import ReshapeCommonPart, ReshapeEdge
from segment_reshape.utils import clone_geometry_safely

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


def get_common_geometries(
    main_feature_layer: QgsVectorLayer,
    main_feature: QgsFeature,
    related_features_by_layer: List[Tuple[QgsVectorLayer, QgsFeature]],
    main_feature_segment: Tuple[int, int],
) -> CommonGeometriesResult:

    main_feature_geom = main_feature.geometry()
    segment_start_point = clone_geometry_safely(
        main_feature_geom.vertexAt(main_feature_segment[0])
    )
    segment_end_point = clone_geometry_safely(
        main_feature_geom.vertexAt(main_feature_segment[1])
    )

    # Find geometries having their boundary intersecting main feature segment
    common_segment_candidates: List[QgsGeometry] = []
    for _, feature in related_features_by_layer:
        geom = feature.geometry()
        if (
            geom.type() == QgsWkbTypes.GeometryType.PolygonGeometry
            and (geom.touches(segment_start_point) and geom.touches(segment_end_point))
        ) or (
            geom.type() != QgsWkbTypes.GeometryType.PolygonGeometry
            and (
                geom.intersects(segment_start_point)
                and geom.intersects(segment_end_point)
            )
        ):
            common_segment_candidates.append(geom)

    segments = []
    end_points = []

    common_segment_as_geom = QgsGeometry()
    start_point = QgsPoint()
    end_point = QgsPoint()

    # Return just boundary as common segment if no candidates found
    if len(common_segment_candidates) == 0:
        if main_feature_geom.type() == QgsWkbTypes.GeometryType.PointGeometry:
            return (None, [], [])

        vertices = []
        if main_feature_geom.type() == QgsWkbTypes.GeometryType.PolygonGeometry:
            # TODO: multigeometries and holes in polygons
            vertices = main_feature_geom.asPolygon()[0]

        if main_feature_geom.type() == QgsWkbTypes.GeometryType.LineGeometry:
            # TODO: multigeometries
            vertices = main_feature_geom.asPolyline()

        # TODO: How to handle common segments along the boundary
        # (outside triggered segment)? Return just the boundary for now
        return (
            QgsLineString(vertices),
            [
                ReshapeCommonPart(
                    main_feature_layer,
                    main_feature,
                    list(range(len(vertices))),
                    is_reversed=False,
                )
            ],
            [],
        )

    else:
        common_segment = _calculate_common_segment(
            main_feature_geom,
            common_segment_candidates,
            segment_start_point,
            segment_end_point,
        )

        if common_segment is not None:
            common_segment_as_geom = clone_geometry_safely(common_segment)
            start_point = common_segment.startPoint()
            end_point = common_segment.endPoint()

    if common_segment is not None:
        vertex_indices = _get_vertex_indices_of_segment(
            main_feature_geom, common_segment_as_geom
        )

        segments.append(
            ReshapeCommonPart(
                main_feature_layer,
                main_feature,
                vertex_indices,
                is_reversed=_check_if_vertices_are_reversed(vertex_indices),
            )
        )
    else:
        dist, vertex = main_feature_geom.closestVertexWithContext(
            segment_start_point.asPoint()
        )

        if dist == 0:
            end_points.append(
                ReshapeEdge(main_feature_layer, main_feature, vertex, is_start=True)
            )

    for layer, feature in related_features_by_layer:
        geom = feature.geometry()

        # Features sharing common segment
        if common_segment is not None and geom.contains(common_segment_as_geom):
            vertex_indices = _get_vertex_indices_of_segment(
                geom, common_segment_as_geom
            )
            segments.append(
                ReshapeCommonPart(
                    layer,
                    feature,
                    vertex_indices,
                    is_reversed=_check_if_vertices_are_reversed(vertex_indices),
                )
            )

        # Other features which may have vertex at segment end points
        # or at trigger point location (in case common segment was not found)
        else:
            for point, is_start in [
                (QgsPointXY(start_point), True),
                (QgsPointXY(end_point), False),
            ]:
                dist, vertex = geom.closestVertexWithContext(point)

                if dist == 0:
                    end_points.append(
                        ReshapeEdge(layer, feature, vertex, is_start=is_start)
                    )

    return (
        QgsLineString(common_segment_as_geom.asPolyline())
        if common_segment is not None
        else None,
        segments,
        end_points,
    )


def _calculate_common_segment(
    main_geom: QgsGeometry,
    geoms: List[QgsGeometry],
    start_point: QgsGeometry,
    end_point: QgsGeometry,
) -> Optional[QgsLineString]:
    """
    Calculated shared segment of main geom and input geoms. Segment is shared when
    all vertices matches at some part of one or more geometries. Function returns
    common segment or None if resulting geometry is point or
    no shared segment found.
    """

    intersection = clone_geometry_safely(main_geom)

    # Calculate combined intersection
    for geom in geoms:
        temp_intersection = intersection.intersection(geom)
        intersection = clone_geometry_safely(temp_intersection)

    # Check that one of intersections matches at least one of tested
    # geoms (main geom is checked later)
    matches = []
    for geom in geoms:
        for part in intersection.constParts():
            if isinstance(part, QgsLineString):
                matches.append(_segment_matches_geom(geom, clone_geometry_safely(part)))

    if not any(matches):
        return None

    common_segment_candidates = [
        part.clone()
        for part in intersection.constParts()
        if isinstance(part, QgsLineString)
    ]

    # Find out which intersection is at trigger location
    for candidate_line in common_segment_candidates:
        candidate_geom = clone_geometry_safely(candidate_line)
        if candidate_geom.intersects(start_point) and candidate_geom.intersects(
            end_point
        ):
            if _segment_matches_geom(main_geom, candidate_geom):
                return QgsLineString(candidate_geom.asPolyline())
            else:
                # Common segment is not topologically correct (wrong end points)
                return None

    # Return None in case intersection was a point or nothing found
    return None


def _segment_matches_geom(geom: QgsGeometry, candidate_geom: QgsGeometry) -> bool:
    try:
        _get_vertex_indices_of_segment(geom, candidate_geom)
        return True
    except ValueError:
        return False


def _get_vertex_indices_of_segment(
    geom: QgsGeometry, segment_geom: QgsGeometry
) -> List[int]:

    polygon_start_point: Optional[QgsPoint] = None

    if geom.type() == QgsWkbTypes.GeometryType.PolygonGeometry:
        polygon_start_point = geom.asPolygon()[0][0]

    vertex_indices = []
    for i, point in enumerate(segment_geom.asPolyline()):
        dist, vertex = geom.closestVertexWithContext(QgsPointXY(point))

        if dist != 0:
            raise ValueError("Segment did not match original geometry")

        vertex_indices.append(vertex)
        if i > 0 and abs(vertex_indices[i - 1] - vertex_indices[i]) != 1:
            if polygon_start_point is not None:
                previous_point = geom.vertexAt(vertex_indices[i - 1])
                if abs(vertex_indices[i - 1] - vertex_indices[i]) == 0:
                    vertex_indices[i] = 0
                    continue
                elif (
                    point.x() == polygon_start_point.x()
                    and point.y() == polygon_start_point.y()
                ):
                    vertex_indices[i] = 0
                    continue
                elif (
                    previous_point.x() == polygon_start_point.x()
                    and previous_point.y() == polygon_start_point.y()
                ):
                    vertex_indices[i - 1] = 0
                    continue
            raise ValueError("Segment did not match original geometry")

    # Handle possible duplicates (applies to polygons only)
    if (
        geom.type() == QgsWkbTypes.GeometryType.PolygonGeometry
        and vertex_indices.count(0) > 1
    ):

        # Find first instance of duplicate index
        i = vertex_indices.index(0)

        max_index = max(vertex_indices)

        if i == 0:
            vertex_indices[-1] = max_index

        is_reversed = _check_if_vertices_are_reversed(vertex_indices)
        if is_reversed is True:
            # Replace second instance
            vertex_indices = (
                vertex_indices[: i + 1] + [max_index + 1] + vertex_indices[i + 2 :]
            )
        else:
            # Replace fist instance
            vertex_indices = (
                vertex_indices[:i] + [max_index + 1] + vertex_indices[i + 1 :]
            )

    return vertex_indices


def _check_if_vertices_are_reversed(vertex_indices: List[int]) -> bool:
    first, second = vertex_indices[:2]
    return any(
        [
            (abs(first - second) == 1 and first > second),
            (abs(first - second) != 1 and first < second),
        ]
    )
