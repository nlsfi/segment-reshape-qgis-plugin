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
from typing import Any, List, Tuple

from qgis.core import QgsFeature, QgsLineString, QgsPoint, QgsVectorLayer

# hyödynnä geometry moduulin luokkia?


@dataclass
class CommonSegmentResult:
    layer: QgsVectorLayer
    feature: QgsFeature
    from_vertex_id: Any
    to_vertex_id: Any
    reversed: bool


@dataclass
class SegmentEndPointResult:
    layer: QgsVectorLayer
    feature: QgsFeature
    vertex_id: Any
    is_start: bool


FindSegmentResult = Tuple[
    QgsLineString, List[CommonSegmentResult], List[SegmentEndPointResult]
]


def find_segment_to_reshape(
    layer: QgsVectorLayer,
    feature: QgsFeature,
    trigger_location: QgsPoint,
) -> FindSegmentResult:
    pass

    # related = find_related_features()
    # find_common_segment(related)


def find_related_features(
    layer: QgsVectorLayer, feature: QgsFeature
) -> List[QgsFeature]:
    pass

    # tutki onko topologinen muokkaus päällä, jos ei, tyhjä lista
    # etsi kaikki input-featureen liittyvät kohteet, touches tms?


# miten määritetään digitointisuunta?
# uuden linjausken piirtosuunta pitää olla alkuperäisen kohteen segmentin piirtosuunta
# pitää visualsoida käyttäjälle


def calculate_common_segment(
    feature: QgsFeature, related_features: List[QgsFeature], trigger_location: QgsPoint
) -> FindSegmentResult:
    pass

    # päättele yhteinen segmentti input-pisteen
    # etsitään related kohteista ne, jotka kulkee input-pisteen sijainnisssa
    # esim. boundaryn intersect ja katsotaan mihin parttiin input osuu
    # leikataan tulosta jokaisella muulla kohteella, joka ei kulje input-pisteen
    # sijainnissa

    # tuloksena on featuret ja niille verteksivälit joita muutetaan

    # tuloksena myös päätepisteisiin koskevat featuret, joiden verteksi koskee
    # välin päätepisteeseen, ja verteksin tulee siirtyä uuden digitoidun välin
    # pisteeseen


# espalle:
#   - käyttäjä painaa pikanäppäintä ja klikkaa sijaintia
#   - espalle ilmestyy prosessin mukainen "yhteinen segmentti" nauhana
#     (importoi nauha jolla on erikois-id)
#   - käyttäjä muokkaa nauhaa
#   - käyttäjä painaa "nauha alkuperäiseksi"
#   - jos nauhalle lisätessä on laitettu joku erikois-id lippu (IS_RESHAPE_TRAIL),
#     voidaan käsitellä halutulla tavalla
#   - tehdään muutokset kohteille
