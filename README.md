# segment-reshape-qgis-plugin

QGIS plugin with a map tool to reshape a continuous segment topogically.

## Plugin

`Segment reshape tool` plugin is available from the QGIS plugin repository. It provides a simple toolbar with one action. Action will activate a segment reshape map tool, with which a common segment portion can be clicked and a new segment can be digitized. After digitizing the features are edited to match the new common segment.

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

#### Map tool

Map tool is found in `segment_reshape.map_tool.segment_reshape_tool.SegmentReshapeTool`, it can be subclassed or used as is in custom plugins.

The Map Tool should be taken into use as follows:

```python

from segment_reshape.map_tool.segment_reshape_tool import (
    SegmentReshapeTool,
    SegmentReshapeToolHandler,
)

class SegmentReshapePlugin(QObject):
    def __init__(self, iface) -> None:
        super().__init__(parent=None)
        self.iface = iface

        self.segment_reshape_tool = SegmentReshapeTool(iface.mapCanvas())

    def initGui(self) -> None:
        self.segment_reshape_tool_action = QAction(
            QIcon(resources_path("icons/segment_reshape.svg")),
            self.tr("Reshape common segment"),
            self.iface.mainWindow(),
        )
        self.segment_reshape_tool_handler = SegmentReshapeToolHandler(
            self.segment_reshape_tool, self.segment_reshape_tool_action
        )
        self.iface.registerMapToolHandler(self.segment_reshape_tool_handler)

        self.toolbar = iface.addToolBar(
            self.tr("Segment reshape toolbar"),
        )
        self.toolbar.addAction(self.segment_reshape_tool_action)

```

## Development of segment-reshape-qgis-plugin

See [development readme](./DEVELOPMENT.md).

## License & copyright

Licensed under GNU GPL v3.0.

Copyright (C) 2022 [National Land Survey of Finland].

[National Land Survey of Finland]: https://www.maanmittauslaitos.fi/en
[qgis-plugin-dev-tools]: https://github.com/nlsfi/qgis-plugin-dev-tools
