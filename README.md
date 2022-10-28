# segment-reshape-qgis-plugin

QGIS plugin with a map tool to reshape a continuous segment topogically.

## Plugin

TBA

## Library

To use this library as an external dependency in your plugin or other Python code, install it using `pip install segment-reshape-qgis-plugin` and use imports from the provided `segment_reshape` package. If used in a plugin, library must be installed in the runtime QGIS environment or use [qgis-plugin-dev-tools] to bundle your plugin with runtime dependencies included.

### API documentation

Simple use case can be seen in [integration test](./test/integration/test_simple_line_reshape.py).

#### Finding common segment

`segment_reshape.topology.find_related.find_segment_to_reshape` calculates the line segment between features that share equal sequence of vertices along their edges at the trigger location. By default all QGIS project layers are used to find connected features if topological editing is enabled. Custom list of layers can also be passed as an argument.

Return values are:

- Common segment (`None` if not found)
- Features that share the common segment (and relevant vertex indices)
- Features that share the end points of the common segment (and relevant vertex index)

#### Editing geometries partially

`segment_reshape.geometry.reshape.make_reshape_edits` reshapes the provided common parts and edges, so that common part shared vertex indices are replaced and edges are moved to match the reshaped geometry. Output of `find_segment_to_reshape` (common parts & edges) can be used as input for this function.

## Development of segment-reshape-qgis-plugin

See [development readme](./DEVELOPMENT.md).

## License & copyright

Licensed under GNU GPL v3.0.

Copyright (C) 2022 [National Land Survey of Finland].

[National Land Survey of Finland]: https://www.maanmittauslaitos.fi/en
[qgis-plugin-dev-tools]: https://github.com/nlsfi/qgis-plugin-dev-tools
