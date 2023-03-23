# CHANGELOG

## [0.1.3] - 2023-03-23

- Feature: Digitizing the new geometry for a segment behaves now as the native QGIS digitizing tools. It supports etc. snapping, tracing and advanced cad tools.
- Feature: Map tool button is enabled only when a line or polygon layer is active. This is implemented through MapToolHandler which ensures that the tool behaves like rest of the map tools. This means also that the tool can be deactivated only by selecting another map tool.
- Fix: Color of the start point indicator line was changed to grey to make difference to the digitized line.

## [0.1.2] - 2023-02-23

- Feature: Set z coordinate values of the reshaped geometry to QGIS's default z coordinate value instead of NaN

## [0.1.1] - 2023-01-17

- Fix: Correcly move multiple edges for same feature.

## [0.1.0] - 2022-12-14

- Feature: Add support for key commands (backspace and esc) in vertex editing.
- Fix: In cases where segment was split from the middle the start and end parts of the line is correctly merged back together.
- Fix: Geometry comparison was fixed so that only common vertices between geometries are taken into account. Before edges were split if an edge crossed other edge also from non vertex point.
- Feature: Preserve source feature z coordinate for calculated segment.

## [0.0.3] - 2022-11-17

- Fix: Fix missing toolbar icon by including resource files in setuptools build.

## [0.0.2] - 2022-11-09

- Feature: Implement a QGIS plugin with a simple toolbar.
- Feature: Add map tool for selecting and drawing the reshape geometry.
- Feature: Support complex calculation for the common segment.
- Feature: Add snapping support when drawing the reshape geometry.

## [0.0.1] - 2022-10-28

- Initial release: API for finding common segments and making reshape edits.

[0.0.1]: https://github.com/nlsfi/segment-reshape-qgis-plugin/releases/tag/v0.0.1
[0.0.2]: https://github.com/nlsfi/segment-reshape-qgis-plugin/releases/tag/v0.0.2
[0.0.3]: https://github.com/nlsfi/segment-reshape-qgis-plugin/releases/tag/v0.0.3
[0.1.0]: https://github.com/nlsfi/segment-reshape-qgis-plugin/releases/tag/v0.1.0
[0.1.1]: https://github.com/nlsfi/segment-reshape-qgis-plugin/releases/tag/v0.1.1
[0.1.2]: https://github.com/nlsfi/segment-reshape-qgis-plugin/releases/tag/v0.1.2
[0.1.3]: https://github.com/nlsfi/segment-reshape-qgis-plugin/releases/tag/v0.1.3
