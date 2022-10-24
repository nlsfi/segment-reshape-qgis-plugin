from qgis.core import QgsGeometry


def clone_geometry_safely(geometry: QgsGeometry) -> QgsGeometry:
    original_abstract_geometry = geometry.get()
    cloned_original_abstract_geometry = original_abstract_geometry.clone()
    return QgsGeometry(cloned_original_abstract_geometry)
