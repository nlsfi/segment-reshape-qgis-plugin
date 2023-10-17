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

import logging
from typing import Optional, cast

import qgis_plugin_tools
import segment_reshape
from qgis.gui import QgisInterface
from qgis.PyQt.QtCore import QCoreApplication, QObject, QTranslator
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QToolBar
from qgis.utils import iface as iface_
from qgis_plugin_tools.tools.custom_logging import setup_loggers
from qgis_plugin_tools.tools.i18n import setup_translation, tr
from qgis_plugin_tools.tools.resources import resources_path
from segment_reshape.map_tool.segment_reshape_tool import (
    SegmentReshapeTool,
    SegmentReshapeToolHandler,
)

import segment_reshape_plugin

iface = cast(QgisInterface, iface_)
LOGGER = logging.getLogger(__name__)


class SegmentReshapePlugin(QObject):
    def __init__(self) -> None:
        super().__init__(parent=None)

        self._teardown_loggers = lambda: None

        # Initialize locale
        locale, file_path = setup_translation()
        if file_path:
            self.translator = QTranslator()
            self.translator.load(file_path)
            QCoreApplication.installTranslator(self.translator)

        self.toolbar: Optional[QToolBar] = None
        self.segment_reshape_tool = SegmentReshapeTool(iface.mapCanvas())
        self.segment_reshape_tool_action: Optional[QAction] = None

    def initGui(self) -> None:  # noqa: N802 (qgis naming)
        self._teardown_loggers = setup_loggers(
            segment_reshape.__name__,
            segment_reshape_plugin.__name__,
            qgis_plugin_tools.__name__,
            message_log_name=tr("Segment reshape tool"),
        )

        toolbar = iface.addToolBar(
            self.tr("Segment reshape toolbar"),
        )
        toolbar.setObjectName("segment-reshape-toolbar")

        self.segment_reshape_tool_action = QAction(
            QIcon(resources_path("icons/segment_reshape.svg")),
            self.tr("Reshape common segment"),
            iface.mainWindow(),
        )
        self.segment_reshape_tool_handler = SegmentReshapeToolHandler(
            self.segment_reshape_tool, self.segment_reshape_tool_action
        )
        iface.registerMapToolHandler(self.segment_reshape_tool_handler)

        toolbar.addAction(self.segment_reshape_tool_action)

        self.toolbar = toolbar

    def unload(self) -> None:
        iface.unregisterMapToolHandler(self.segment_reshape_tool_handler)

        if self.toolbar is not None:
            self.toolbar.deleteLater()
        self.toolbar = None

        self._teardown_loggers()
        self._teardown_loggers = lambda: None
