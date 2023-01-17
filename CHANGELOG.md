# CHANGELOG

## [0.1.1] - 2023-01-17

- Fix: Correcly move multiple edges for same feature

## [0.1.0] - 2022-12-14

- Feat: Add support for key commands (backspace and esc) in vertex editing
- Fix: In cases where segment was split from the middle the start and end parts of the line is correctly merged back together.
- Fix: Geometry comparison was fixed so that only common vertices between geometries are taken into account. Before edges were split if an edge crossed other edge also from non vertex point.
- Feat: Preserve source feature z coordinate for calculated segment

## [0.0.3] - 2022-11-17

- Fix: Fix missing toolbar icon by including resource files in setuptools build

## [0.0.2] - 2022-11-09

- Feat: Implement a QGIS plugin with a simple toolbar
- Feat: Add map tool for selecting and drawing the reshape geometry
- Feat: Support complex calculation for the common segment
- Feat: Add snapping support when drawing the reshape geometry

## [0.0.1] - 2022-10-28

- Initial release: API for finding common segments and making reshape edits

[0.0.1]: https://github.com/nlsfi/segment-reshape-qgis-plugin/releases/tag/v0.0.1
[0.0.2]: https://github.com/nlsfi/segment-reshape-qgis-plugin/releases/tag/v0.0.2
[0.0.3]: https://github.com/nlsfi/segment-reshape-qgis-plugin/releases/tag/v0.0.3
[0.1.0]: https://github.com/nlsfi/segment-reshape-qgis-plugin/releases/tag/v0.1.0
[0.1.1]: https://github.com/nlsfi/segment-reshape-qgis-plugin/releases/tag/v0.1.1
