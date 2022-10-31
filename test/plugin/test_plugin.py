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

from typing import Iterator

import pytest
from pytest_mock import MockerFixture
from pytest_qgis import QgisInterface

from segment_reshape_plugin import classFactory
from segment_reshape_plugin.plugin import SegmentReshapePlugin


@pytest.fixture(scope="module")
def plugin_loaded(qgis_iface: QgisInterface) -> Iterator[SegmentReshapePlugin]:
    plugin = classFactory(qgis_iface)
    plugin.initGui()

    yield plugin

    plugin.unload()


def test_plugin_loads_without_errors(plugin_loaded: SegmentReshapePlugin) -> None:
    assert plugin_loaded.toolbar is not None
    assert plugin_loaded.segment_reshape_tool_action is not None


def test_plugin_action_activates_or_deactivates_reshape_map_tool(
    plugin_loaded: SegmentReshapePlugin, mocker: MockerFixture
) -> None:
    assert plugin_loaded.segment_reshape_tool_action is not None
    assert not plugin_loaded.segment_reshape_tool.isActive()

    m_tool_deactivate = mocker.patch.object(
        plugin_loaded.segment_reshape_tool,
        "deactivate",
    )

    plugin_loaded.segment_reshape_tool_action.trigger()

    assert plugin_loaded.segment_reshape_tool.isActive()

    plugin_loaded.segment_reshape_tool_action.trigger()
    m_tool_deactivate.assert_called_once()
