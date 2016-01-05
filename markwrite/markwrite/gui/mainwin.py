# -*- coding: utf-8 -*-
#
# This file is part of the open-source MarkWrite application.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
from __future__ import division
import numpy as np
import pyqtgraph as pg

from markwrite.gui import ProjectSettingsDialog, SETTINGS,  X_FIELD, Y_FIELD

from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.dockarea import DockArea, Dock

from markwrite.util import getIconFilePath
from markwrite.file_io import loadPredefinedSegmentTagList, readPickle, writePickle
from markwrite.reports import PenSampleReportExporter, SegmentLevelReportExporter, custom_report_classes
from markwrite.segment import PenDataSegment
from dialogs import ExitApplication, fileOpenDlg, ErrorDialog, warnDlg, \
    fileSaveDlg,ConfirmAction,infoDlg
from markwrite.project import MarkWriteProject

DEFAULT_WIN_SIZE = (1200, 800)

DEFAULT_DOCK_PLACEMENT = {
    u"Segment Tree": ('left', (.2, 1.0)),
    u"Timeline": (['right', u"Segment Tree"], (.8, .35)),
    u"Spatial View": (['bottom', u"Timeline"], (.60, .65)),
    u"Selected Pen Points": (['right', u"Spatial View"], (.2, .65)),
}

ABOUT_DIALOG_TEXT = """
<b> MarkWrite v0.1</b> <br>
This software is GLP v3 licensed.<br>
<br>
See licence.txt for license details.
"""

ABOUT_DIALOG_TITLE = "About MarkWrite"


def showNotImplementedDialog(widget, title=None, msg=None, func_name=None):
    if func_name:
        if title is None:
            title = "Function '{0}' Not Implemented"
            title = title.format(func_name)
        if msg is None:
            msg = "The Function '{0}' Has Not Yet Been Implemented."
            msg = msg.format(func_name)
    else:
        if title is None:
            title = "Action Not Implemented"
        if msg is None:
            msg = "The Selected Action Has Not Yet Been Implemented."
    QtGui.QMessageBox.information(widget, title, msg)


def not_implemented(wrapped_func):
    def func_wrapper(*args, **kwargs):
        showNotImplementedDialog(args[0], func_name=wrapped_func.__name__)

    return func_wrapper


def showSegmentNameDialog(tags, default=u""):
    return QtGui.QInputDialog.getItem(MarkWriteMainWindow.instance(),
                                      u"Segment Name (Tag)",
                                      u"Enter the desired pen segment tag, "
                                      u"or selected one from the predefined "
                                      u"tag list.",
                                      [default] + tags,
                                      current=0,
                                      editable=True,
    )

class MarkWriteMainWindow(QtGui.QMainWindow):
    SAMPLE_XY_FIELDS = ['x_filtered', 'y_filtered']
    sigProjectChanged = QtCore.Signal(object)  # new_project
    sigResetProjectData = QtCore.Signal(object)  # project
    sigSelectedPenDataUpdate = QtCore.Signal(object,
                                             object)  # (smin,smax), segmentdata
    sigSegmentCreated = QtCore.Signal(object)  # new segment
    sigSegmentRemoved = QtCore.Signal(object,
                                      object)  # segment being removed,
                                      # segment index in list
    sigAppSettingsUpdated = QtCore.Signal(object, #dict of app settings that changed
                                          object,) #ful settings dict
    sigActiveObjectChanged = QtCore.Signal(object, object) #new, old active objects
    _mainwin_instance=None
    _appdirs = None
    def __init__(self, qtapp):
        global  SETTINGS
        QtGui.QMainWindow.__init__(self)
        MarkWriteMainWindow._mainwin_instance = self

        self._current_project = None
        self._activeobject = None

        self._predefinedtags = loadPredefinedSegmentTagList(u'default.tag')

        # create qt actions used by menu, toolbar, or both
        self.createGuiActions()

        # init GUI related stuff
        self.setupGUI(qtapp)

        self.sigProjectChanged.connect(self.handleProjectChange)
        self.sigSelectedPenDataUpdate.connect(self.handleSelectedPenDataUpdate)
        self.sigAppSettingsUpdated.connect(self._penDataTimeLineWidget.handleUpdatedSettingsEvent)
        self.sigAppSettingsUpdated.connect(self._penDataSpatialViewWidget.handleUpdatedSettingsEvent)
        self.sigAppSettingsUpdated.connect(self._selectedPenDataViewWidget.handleUpdatedSettingsEvent)

    @staticmethod
    def instance():
        return MarkWriteMainWindow._mainwin_instance

    @property
    def project(self):
        return self._current_project

    @property
    def activeobject(self):
        return self._activeobject

    def setActiveObject(self, timeperioddatatype=None):
        prevactiveobj = self._activeobject

        self._activeobject = timeperioddatatype
        if timeperioddatatype is None:
            self._activeobject = self.project.selectedtimeregion
        #print "Settings active object:",self._activeobject
        if isinstance(self._activeobject,PenDataSegment):
            #print "**Setting region:",self._activeobject
            self._segmenttree.doNotSetActiveObject=True
            self.project.selectedtimeregion.setRegion(self._activeobject.timerange)
            self._segmenttree.doNotSetActiveObject=False
            self.removeSegmentAction.setEnabled(not self._activeobject.locked)
        else:
            self.removeSegmentAction.setEnabled(False)
        self.sigActiveObjectChanged.emit(self._activeobject,prevactiveobj)

        return self._activeobject

    @property
    def predefinedtags(self):
        if self.project:
            return self.project.autodetected_segment_tags + self._predefinedtags
        return self._predefinedtags

    def createGuiActions(self):
        #
        # File Menu / Toolbar Related Actions
        #
        atext = 'Open a supported digitized pen position ' \
                'file format.'
        aicon = 'folder&32.png'
        self.openFileAction = ContextualStateAction(
            QtGui.QIcon(getIconFilePath(aicon)),
            '&Open',
            self)
        self.openFileAction.setShortcut('Ctrl+O')
        self.openFileAction.setEnabled(True)
        self.openFileAction.setStatusTip(atext)
        self.openFileAction.triggered.connect(self.openFile)

        #atext = 'Save Current Project.'
        #aicon = 'save&32.png'
        #self.saveProjectAction = ContextualStateAction(
        #    QtGui.QIcon(getIconFilePath(aicon)),
        #    'Save',
        #    self)
        #self.saveProjectAction.setShortcut('Ctrl+S')
        #self.saveProjectAction.setEnabled(False)
        #self.saveProjectAction.setStatusTip(atext)
        #self.saveProjectAction.triggered.connect(self.saveProject)

        atext = 'Export Pen Sample Level Report to a File.'
        aicon = 'sample_report&32.png'
        self.exportSampleReportAction = ContextualStateAction(
            QtGui.QIcon(getIconFilePath(aicon)),
            'Sample Report',
            self)
        #self.exportSampleReportAction.setShortcut('Ctrl+S')
        self.exportSampleReportAction.setEnabled(False)
        self.exportSampleReportAction.setStatusTip(atext)
        self.exportSampleReportAction.triggered.connect(
            self.createPenSampleLevelReportFile)

        atext = 'Export Segment Level Report to a File.'
        aicon = 'segment_report&32.png'
        self.exportSegmentReportAction = ContextualStateAction(
            QtGui.QIcon(getIconFilePath(aicon)),
            'Segment Report',
            self)
        #self.exportSampleReportAction.setShortcut('Ctrl+S')
        self.exportSegmentReportAction.setEnabled(False)
        self.exportSegmentReportAction.setStatusTip(atext)
        self.exportSegmentReportAction.triggered.connect(
            self.createSegmentLevelReportFile)

        self.exportSampleReportAction.enableActionsList.append(self.exportSegmentReportAction)

        atext = 'Open the Application Settings Dialog.'
        aicon = 'settings&32.png'
        self.showProjectSettingsDialogAction = ContextualStateAction(
            QtGui.QIcon(getIconFilePath(aicon)),
            '&Settings',
            self)
        self.showProjectSettingsDialogAction.setShortcut('Alt+S')
        self.showProjectSettingsDialogAction.setEnabled(True)
        self.showProjectSettingsDialogAction.setStatusTip(atext)
        self.showProjectSettingsDialogAction.triggered.connect(
            self.handleDisplayAppSettingsDialogEvent)

        atext = 'Close the MarkWrite Application. Any data segmention will be lost!'
        aicon = 'shut_down&32.png'
        self.exitAction = ContextualStateAction(
            QtGui.QIcon(getIconFilePath(aicon)),
            'Exit',
            self)
        self.exitAction.setShortcut('Ctrl+Alt+Q')
        self.exitAction.setEnabled(True)
        self.exitAction.setStatusTip(atext)
        self.exitAction.triggered.connect(self.closeEvent)

        #
        # Selection Menu / Toolbar Related Actions
        #

        atext = 'Create a Segment Using Currently Selected Pen Data.'
        aicon = 'accept&32.png'
        self.createSegmentAction = ContextualStateAction(
            QtGui.QIcon(getIconFilePath(aicon)),
            'Create &New',
            self)
        self.createSegmentAction.setShortcut(QtCore.Qt.Key_Return)
        self.createSegmentAction.setEnabled(False)
        self.createSegmentAction.setStatusTip(atext)
        self.createSegmentAction.triggered.connect(self.createSegment)

        atext = 'Delete the Selected Segment and any of the segments children.'
        aicon = 'delete&32.png'
        self.removeSegmentAction = ContextualStateAction(
            QtGui.QIcon(getIconFilePath(aicon)),
            '&Delete',
            self)
        self.removeSegmentAction.setShortcut('Ctrl+D')
        self.removeSegmentAction.setEnabled(False)
        self.removeSegmentAction.setStatusTip(atext)
        self.removeSegmentAction.triggered.connect(self.removeSegment)

        #
        # Timeline Plot Zoom Related Actions
        #

        atext = 'Increase Timeplot Horizontal Magnification 2x'
        aicon = 'zoom_in&32.png'
        self.zoomInTimelineAction = ContextualStateAction(
            QtGui.QIcon(getIconFilePath(aicon)),
            'Zoom In 2x',
            self)
        self.zoomInTimelineAction.setShortcut(QtCore.Qt.CTRL + QtCore.Qt.Key_Plus)
        self.zoomInTimelineAction.setEnabled(False)
        self.zoomInTimelineAction.setStatusTip(atext)
        self.zoomInTimelineAction.triggered.connect(self.zoomInTimeline)

        atext = 'Decrease Timeplot Horizontal Magnification 2x'
        aicon = 'zoom_out&32.png'
        self.zoomOutTimelineAction = ContextualStateAction(
            QtGui.QIcon(getIconFilePath(aicon)),
            'Zoom Out 2x',
            self)
        self.zoomOutTimelineAction.setShortcut(QtCore.Qt.CTRL + QtCore.Qt.Key_Minus)
        self.zoomOutTimelineAction.setEnabled(False)
        self.zoomOutTimelineAction.setStatusTip(atext)
        self.zoomOutTimelineAction.triggered.connect(self.zoomOutTimeline)

        self.exportSampleReportAction.enableActionsList.append(self.zoomInTimelineAction)
        self.exportSampleReportAction.enableActionsList.append(self.zoomOutTimelineAction)

        atext = 'Reposition Views around Selected Time Period'
        aicon = 'target&32.png'
        self.gotoSelectedTimePeriodAction = ContextualStateAction(
            QtGui.QIcon(getIconFilePath(aicon)),
            'Go To Selected Time Period',
            self)
        self.gotoSelectedTimePeriodAction.setShortcut(QtCore.Qt.CTRL + QtCore.Qt.Key_Home)
        self.gotoSelectedTimePeriodAction.setEnabled(False)
        self.gotoSelectedTimePeriodAction.setStatusTip(atext)
        self.gotoSelectedTimePeriodAction.triggered.connect(self.gotoSelectTimelinePeriod)

        atext = "Move selected time period forward, so that it's start time is one sample after the current selection's end time"
        aicon = 'move_selection_forward&32.png'
        self.forwardSelectionAction = ContextualStateAction(
            QtGui.QIcon(getIconFilePath(aicon)),
            'Jump Forward',
            self)
        self.forwardSelectionAction.setShortcut(QtCore.Qt.Key_Right)
        self.forwardSelectionAction.setEnabled(False)
        self.forwardSelectionAction.setStatusTip(atext)
        self.forwardSelectionAction.triggered.connect(self.jumpTimeSelectionForward)

        atext = "Move selected time period backward, so that it's end time is one sample prior to the current selection's start time."
        aicon = 'move_selection_backward&32.png'
        self.backwardSelectionAction = ContextualStateAction(
            QtGui.QIcon(getIconFilePath(aicon)),
            'Jump Backward',
            self)
        self.backwardSelectionAction.setShortcut(QtCore.Qt.Key_Left)
        self.backwardSelectionAction.setEnabled(False)
        self.backwardSelectionAction.setStatusTip(atext)
        self.backwardSelectionAction.triggered.connect(self.jumpTimeSelectionBackward)


        atext = 'Increase Timeline Selection End Time'
        aicon = 'increase_select_endtime&32.png'
        self.increaseSelectionEndPointAction = ContextualStateAction(
            QtGui.QIcon(getIconFilePath(aicon)),
            'Increase Selection End',
            self)
        self.increaseSelectionEndPointAction.setShortcut(QtCore.Qt.CTRL + QtCore.Qt.Key_Right)
        self.increaseSelectionEndPointAction.setEnabled(False)
        self.increaseSelectionEndPointAction.setStatusTip(atext)
        self.increaseSelectionEndPointAction.triggered.connect(self.increaseSelectionEndPointTime)

        atext = 'Decrease Timeline Selection End Time'
        aicon = 'descrease_select_endtime&32.png'
        self.decreaseSelectionEndPointAction = ContextualStateAction(
            QtGui.QIcon(getIconFilePath(aicon)),
            'Decrease Selection End',
            self)
        self.decreaseSelectionEndPointAction.setShortcut(QtCore.Qt.CTRL + QtCore.Qt.Key_Left)
        self.decreaseSelectionEndPointAction.setEnabled(False)
        self.decreaseSelectionEndPointAction.setStatusTip(atext)
        self.decreaseSelectionEndPointAction.triggered.connect(self.decreaseSelectionEndPointTime)

        #======================================
        atext = 'Increase Timeline Selection Start Time'
        aicon = 'increase_select_starttime&32.png'
        self.increaseSelectionStartPointAction = ContextualStateAction(
            QtGui.QIcon(getIconFilePath(aicon)),
            'Increase Selection Start',
            self)
        self.increaseSelectionStartPointAction.setShortcut(QtCore.Qt.ALT + QtCore.Qt.Key_Right)
        self.increaseSelectionStartPointAction.setEnabled(False)
        self.increaseSelectionStartPointAction.setStatusTip(atext)
        self.increaseSelectionStartPointAction.triggered.connect(self.increaseSelectionStartPointTime)

        atext = 'Decrease Timeline Selection Start Time'
        aicon = 'decrease_select_starttime&32.png'
        self.decreaseSelectionStartPointAction = ContextualStateAction(
            QtGui.QIcon(getIconFilePath(aicon)),
            'Decrease Selection Start',
            self)
        self.decreaseSelectionStartPointAction.setShortcut(QtCore.Qt.ALT + QtCore.Qt.Key_Left)
        self.decreaseSelectionStartPointAction.setEnabled(False)
        self.decreaseSelectionStartPointAction.setStatusTip(atext)
        self.decreaseSelectionStartPointAction.triggered.connect(self.decreaseSelectionStartPointTime)

        #
        # Next/Prev Sample Series Actions
        #
        atext = 'Select Next Sample Series'
        aicon = 'nextstroke&24.png'
        self.selectNextSampleSeriesAction = ContextualStateAction(
            QtGui.QIcon(getIconFilePath(aicon)),
            'Select Next Sample Series',
            self)
        #self.selectNextSampleSeriesAction.setShortcut(QtCore.Qt.CTRL + QtCore.Qt.Key_Plus)
        self.selectNextSampleSeriesAction.setEnabled(False)
        self.selectNextSampleSeriesAction.setStatusTip(atext)
        self.selectNextSampleSeriesAction.triggered.connect(self.selectNextSampleSeries)

        atext = 'Select Previous Sample Series'
        aicon = 'prevstroke&24.png'
        self.selectPrevSampleSeriesAction = ContextualStateAction(
            QtGui.QIcon(getIconFilePath(aicon)),
            'Select Previous Sample Series',
            self)
        #self.selectPrevSampleSeriesAction.setShortcut(QtCore.Qt.CTRL + QtCore.Qt.Key_Plus)
        self.selectPrevSampleSeriesAction.setEnabled(False)
        self.selectPrevSampleSeriesAction.setStatusTip(atext)
        self.selectPrevSampleSeriesAction.triggered.connect(self.selectPrevSampleSeries)

        #
        # Next/Prev Pen Pressed Series Actions
        #
        atext = 'Selected Next Pressed Sample Run'
        aicon = 'nextstroke&24.png'
        self.selectNextPressedRunAction = ContextualStateAction(
            QtGui.QIcon(getIconFilePath(aicon)),
            'Selected Next Pressed Sample Run',
            self)
        #self.selectNextPressSeriesAction.setShortcut(QtCore.Qt.CTRL + QtCore.Qt.Key_Plus)
        self.selectNextPressedRunAction.setEnabled(False)
        self.selectNextPressedRunAction.setStatusTip(atext)
        self.selectNextPressedRunAction.triggered.connect(self.selectNextPressedRun)

        atext = 'Selected Previous Pressed Sample Run'
        aicon = 'prevstroke&24.png'
        self.selectPrevPressedRunAction = ContextualStateAction(
            QtGui.QIcon(getIconFilePath(aicon)),
            'Selected Previous Pressed Sample Run',
            self)
        #self.selectPrevPressSeriesAction.setShortcut(QtCore.Qt.CTRL + QtCore.Qt.Key_Plus)
        self.selectPrevPressedRunAction.setEnabled(False)
        self.selectPrevPressedRunAction.setStatusTip(atext)
        self.selectPrevPressedRunAction.triggered.connect(self.selectPrevPressedRun)

        #
        # Next/Prev Stroke Actions
        #
        atext = 'Select the Next Pen Stroke'
        aicon = 'nextstroke&24.png'
        self.selectNextStrokeAction = ContextualStateAction(
            QtGui.QIcon(getIconFilePath(aicon)),
            'Next Pen Stroke',
            self)
        self.selectNextStrokeAction.setShortcut(QtCore.Qt.KeypadModifier + QtCore.Qt.Key_Right)
        self.selectNextStrokeAction.setEnabled(False)
        self.selectNextStrokeAction.setStatusTip(atext)
        self.selectNextStrokeAction.triggered.connect(self.selectNextStroke)

        atext = 'Select the Previous Pen Stroke'
        aicon = 'prevstroke&24.png'
        self.selectPrevStrokeAction = ContextualStateAction(
            QtGui.QIcon(getIconFilePath(aicon)),
            'Previous Pen Stroke',
            self)
        self.selectNextStrokeAction.setShortcut(QtCore.Qt.KeypadModifier + QtCore.Qt.Key_Left)
        self.selectPrevStrokeAction.setEnabled(False)
        self.selectPrevStrokeAction.setStatusTip(atext)
        self.selectPrevStrokeAction.triggered.connect(self.selectPrevStroke)

        #---

        self.exportSampleReportAction.enableActionsList.append(self.zoomInTimelineAction)
        self.exportSampleReportAction.enableActionsList.append(self.zoomOutTimelineAction)
        self.exportSampleReportAction.enableActionsList.append(self.gotoSelectedTimePeriodAction)
        self.exportSampleReportAction.enableActionsList.append(self.decreaseSelectionEndPointAction)
        self.exportSampleReportAction.enableActionsList.append(self.increaseSelectionEndPointAction)
        self.exportSampleReportAction.enableActionsList.append(self.decreaseSelectionStartPointAction)
        self.exportSampleReportAction.enableActionsList.append(self.increaseSelectionStartPointAction)
        self.exportSampleReportAction.enableActionsList.append(self.forwardSelectionAction)
        self.exportSampleReportAction.enableActionsList.append(self.backwardSelectionAction)
        self.exportSampleReportAction.enableActionsList.append(self.selectNextSampleSeriesAction)
        self.exportSampleReportAction.enableActionsList.append(self.selectPrevSampleSeriesAction)
        self.exportSampleReportAction.enableActionsList.append(self.selectNextPressedRunAction)
        self.exportSampleReportAction.enableActionsList.append(self.selectPrevPressedRunAction)
        self.exportSampleReportAction.enableActionsList.append(self.selectNextStrokeAction)
        self.exportSampleReportAction.enableActionsList.append(self.selectPrevStrokeAction)
        #
        # Help Menu / Toolbar Related Actions
        #

        atext = 'Displays the MarkWrite About Dialog.'
        aicon = 'info&32.png'
        self.aboutAction = ContextualStateAction(
            QtGui.QIcon(getIconFilePath(aicon)),
            'About',
            self)
        self.aboutAction.setEnabled(True)
        self.aboutAction.setStatusTip(atext)
        self.aboutAction.triggered.connect(self.showAboutDialog)

    def setupGUI(self, app):
        '''

        :return:
        '''

        #
        ## Create Main GUI Menu Bar
        #

        menubar = self.menuBar()

        fileMenu = menubar.addMenu('&File')
        fileMenu.addAction(self.openFileAction)
        #fileMenu.addAction(self.saveProjectAction)
        fileMenu.addAction(self.showProjectSettingsDialogAction)
        fileMenu.addSeparator()
        exportMenu = fileMenu.addMenu("&Export")
        exportMenu.addAction(self.exportSampleReportAction)
        exportMenu.addAction(self.exportSegmentReportAction)
        exportMenu.addSeparator()
        self.customReportActions=[]
        for custom_report in custom_report_classes:
            a = exportMenu.addAction(custom_report.reportlabel(), lambda: self.exportCustomReport(custom_report))
            a.setEnabled(False)
            self.customReportActions.append(a)
            self.exportSampleReportAction.enableActionsList.append(a)

        fileMenu.addSeparator()
        fileMenu.addAction(self.exitAction)

        segmentMenu = menubar.addMenu('&Segment')
        segmentMenu.addAction(self.createSegmentAction)
        segmentMenu.addAction(self.removeSegmentAction)

        helpMenu = menubar.addMenu('&Help')
        helpMenu.addAction(self.aboutAction)

        self.toolbarFile = self.addToolBar('File')
        self.toolbarFile.addAction(self.openFileAction)
        #self.toolbarFile.addAction(self.saveProjectAction)
        self.toolbarFile.addAction(self.showProjectSettingsDialogAction)
        self.toolbarFile.addAction(self.exportSampleReportAction)
        self.toolbarFile.addAction(self.exportSegmentReportAction)


        self.toolbarsegment = self.addToolBar('Segment')
        self.toolbarsegment.addAction(self.createSegmentAction)
        self.toolbarsegment.addAction(self.removeSegmentAction)

        self.toolbartimelineview = self.addToolBar('Timeline View')
        self.toolbartimelineview.addAction(self.zoomInTimelineAction)
        self.toolbartimelineview.addAction(self.zoomOutTimelineAction)

        self.toolbarsegment = self.addToolBar('Timeline Selection')
        self.toolbarsegment.addAction(self.gotoSelectedTimePeriodAction)
        self.toolbarsegment.addAction(self.decreaseSelectionStartPointAction)
        self.toolbarsegment.addAction(self.increaseSelectionStartPointAction)
        self.toolbarsegment.addAction(self.backwardSelectionAction)
        self.toolbarsegment.addAction(self.forwardSelectionAction)
        self.toolbarsegment.addAction(self.decreaseSelectionEndPointAction)
        self.toolbarsegment.addAction(self.increaseSelectionEndPointAction)

        self.toolbarsegment.addAction(self.selectPrevSampleSeriesAction)
        self.toolbarsegment.addAction(self.selectNextSampleSeriesAction)
        self.toolbarsegment.addAction(self.selectPrevPressedRunAction)
        self.toolbarsegment.addAction(self.selectNextPressedRunAction)
        self.toolbarsegment.addAction(self.selectPrevStrokeAction)
        self.toolbarsegment.addAction(self.selectNextStrokeAction)

        self.toolbarHelp = self.addToolBar('Help')
        self.toolbarHelp.addAction(self.aboutAction)

        #
        ## Create App Dock Area
        #

        self._dockarea = DockArea()
        self.setCentralWidget(self._dockarea)

        # Enable antialiasing for prettier plots
        pg.setConfigOptions(antialias=True)


        # Create Docking Layout
        def addDock(name, inner_widget=None):
            ww, wh = DEFAULT_WIN_SIZE

            dpos, (dw, dh) = DEFAULT_DOCK_PLACEMENT[name]
            if isinstance(dpos, basestring):
                self._dockarea.addDock(Dock(name, size=[ww * dw, wh * dh]),
                                       dpos)
            else:
                self._dockarea.addDock(Dock(name, size=[ww * dw, wh * dh]),
                                       dpos[0], self._dockarea.docks[dpos[1]])

            if inner_widget:
                self._dockarea.docks[name].addWidget(inner_widget)

        from markwrite.gui.selecteddataview import SelectedPointsPlotWidget
        from markwrite.gui.spatialview import PenDataSpatialPlotWidget
        from markwrite.gui.timelineplot import PenDataTemporalPlotWidget
        from markwrite.gui.segmenttree import SegmentInfoDockArea

        self._segmenttree = SegmentInfoDockArea()
        addDock(u"Segment Tree", self._segmenttree)
        self._penDataTimeLineWidget = PenDataTemporalPlotWidget()
        self._penDataSpatialViewWidget = PenDataSpatialPlotWidget()
        addDock(u"Timeline", self._penDataTimeLineWidget)
        addDock(u"Spatial View", self._penDataSpatialViewWidget)
        self._selectedPenDataViewWidget = SelectedPointsPlotWidget()
        addDock(u"Selected Pen Points", self._selectedPenDataViewWidget)

        #
        ## Do Misc. GUI setup.
        #

        self.setWindowIcon(QtGui.QIcon(getIconFilePath('edit&32.png')))

        self.statusBar().showMessage('Ready')
        self.updateAppTitle()

        self.resize(*DEFAULT_WIN_SIZE)

    @property
    def penDataTemporalPlotWidget(self):
        return self._penDataTimeLineWidget

    def updateAppTitle(self):
        if self._current_project is None:
            fileName = u''
        else:
            fileName = self._current_project.name
            fileName = u'{0} : '.format(fileName)

        app_title = u'MarkWrite'
        full_title = u'{0}{1}'.format(fileName, app_title)

        self.setWindowTitle(full_title)

    def showAboutDialog(self):
        QtGui.QMessageBox.about(self, ABOUT_DIALOG_TITLE, ABOUT_DIALOG_TEXT)
        self.sender().enableAndDisableActions()


    def openFile(self):
        file_path = fileOpenDlg()
        if file_path:
            file_path = file_path[0]
            if len(file_path) > 0:
                try:
                    wmproj = MarkWriteProject(file_path=file_path,mwapp=self)

                    wmproj.selectedtimeregion.setBounds(bounds=(wmproj.pendata['time'][0], wmproj.pendata['time'][-1]))


                    self.sigProjectChanged.emit(wmproj)
                    self.sigResetProjectData.emit(wmproj)

                    if wmproj._trialtimes is not None:
                        for i, (tstart, tend) in enumerate(wmproj._trialtimes):
                            self.createSegmentAction.setEnabled(True)
                            self.project.selectedtimeregion.setRegion((tstart, tend))
                            seg = self.createSegment("Trial%d"%(i+1),trim_time_region=False)
                            if seg:
                                seg.locked = True
                            else:
                                print("!! Error: Unable to create segment for trial %d, with time period [%.3f, %.3f]."%(i,tstart, tend))
                        self.setActiveObject(self.project.segmentset.children[0])
                    else:
                        wmproj.selectedtimeregion.setRegion([wmproj.pendata['time'][0], wmproj.pendata['time'][0] + 1.0])

                    #self.displayAllDataChannelsTimePlot()

                except:
                    import traceback

                    traceback.print_exc()
                    ErrorDialog.info_text = u"An error occurred while " \
                                            u"opening:\n%s\nMarkWrite will " \
                                            u"now close." % (
                    file_path)
                    ErrorDialog().display()
                    self.closeEvent(u'FORCE_EXIT')

    def createPenSampleLevelReportFile(self):
        default_file_name = u"pen_samples_{0}.txt".format(self.project.name)
        file_path = fileSaveDlg(initFileName=default_file_name,
                                prompt="Export Pen Sample Report")
        if file_path:
            PenSampleReportExporter().export(file_path, self.project)

    def createSegmentLevelReportFile(self):
        default_file_name = u"segments_{0}.txt".format(self.project.name)
        file_path = fileSaveDlg(initFileName=default_file_name,
                                prompt="Export Segment Level Report")
        if file_path:
            SegmentLevelReportExporter().export(file_path, self.project)

    def exportCustomReport(self,reportcls):
        default_file_name = u"{}_{}.txt".format(reportcls.outputfileprefix(),self.project.name)
        file_path = fileSaveDlg(initFileName=default_file_name,
                                prompt="Export %s"%(reportcls.reportlabel()))
        if file_path:
            reportcls().export(file_path, self.project)

    def createSegment(self, name=None, trim_time_region = True):
        """
        Displays the Create Segment dialog. If dialog is not cancelled and
        segment name length >0, then create a new segment and add to the
        projects segment list.
        :return:
        """
        if self.createSegmentAction.isEnabled():
            # Shrink timeline selection region to fit start and end time
            # of possible segment being created.
            orgval = SETTINGS['new_segment_trim_0_pressure_points']

            timeperiod = self.project.selectedtimeperiod[:]
            if trim_time_region is False:
                SETTINGS['new_segment_trim_0_pressure_points']=False

            pendata_ix_range = self.project.segmentset.calculateTrimmedSegmentIndexBoundsFromTimeRange(*timeperiod)
            new_segment = None
            if len(pendata_ix_range)>0:
                if trim_time_region:
                    segmenttimeperiod = self.project.pendata['time'][pendata_ix_range]
                    self.project.selectedtimeregion.setRegion(segmenttimeperiod)

                ok = True
                if not name:
                    name, ok = showSegmentNameDialog(self.predefinedtags)
                name = unicode(name).strip().replace('\t', "#")

                if len(name) > 0 and ok:
                    psid = self.project.getSelectedDataSegmentIDs()[0]
                    new_segment = self.project.createSegmentFromSelectedPenData(name, psid)
                    self.handleSelectedPenDataUpdate(None,None)
                    self.sigSegmentCreated.emit(new_segment)
                    self.setActiveObject(new_segment)
                else:
                    # If segment creation was cancelled or failed, then reset
                    # timeline selection region to original time period.
                    self.project.selectedtimeregion.setRegion(timeperiod)

            SETTINGS['new_segment_trim_0_pressure_points'] = orgval
            return new_segment

        else:
            ErrorDialog.info_text = u"Segment Creation Failed.\nNo selected " \
                                    u"pen data."
            ErrorDialog().display()

    def removeSegment(self):
        ConfirmAction.text = 'Delete Segment Confirmation'
        ConfirmAction.info_text = "Are you sure you want to <b>permanently deleted</b> the currently selected segment?" \
                                  "<br><br>" \
                                  "Any children of this segment will also be deleted."
        yes = ConfirmAction.display()
        if not yes:
            return
        segment = self.activeobject
        if segment and segment.parent is not None:
            seg_ix = segment.parent.getChildIndex(segment)
            # Decrement the pendata array 'segment_id' field for elements within
            # the segment being removed so that # of segments that contain each
            # pen point can be tracked
            allpendata = self.project.pendata
            segment_filter = (allpendata['time'] >= segment.starttime) & (
            allpendata['time'] <= segment.endtime)
            allpendata['segment_id'][segment_filter] = segment.parent.id
            self.setActiveObject(self.project.selectedtimeregion)
            self.handleSelectedPenDataUpdate(None,None)
            self.sigSegmentRemoved.emit(segment, seg_ix)

            segment.parent.removeChild(segment)
        else:
            print "   - Remove action IGNORED"
       #print "<< removeSegment"

    def handleProjectChange(self, project):
        if self._current_project:
            pass
        self._current_project = project
        self.setActiveObject(self.project.selectedtimeregion)
        self.updateAppTitle()
        #self.saveProjectAction.setEnabled(project.modified)
        self.exportSampleReportAction.setEnabled(True)

    def zoomInTimeline(self):
        # TODO: Move method to _penDataTimeLineWidget
        self._penDataTimeLineWidget.scaleBy(x=0.5)

    def zoomOutTimeline(self):
        # TODO: Move method to _penDataTimeLineWidget
        self._penDataTimeLineWidget.scaleBy(x=2.0)#,center=(xmin+xmax)/2)

    def gotoSelectTimelinePeriod(self):
        # TODO: Move method to _penDataTimeLineWidget
        xmin, xmax , selpendat= self._penDataTimeLineWidget.currentSelection.selectedtimerangeanddata
        xpad = (xmax-xmin)/2
        pdat=self.project.pendata
        rx=(max(0,xmin-xpad),min(xmax+xpad,self._penDataTimeLineWidget.maxTime))
        if SETTINGS['timeplot_enable_ymouse']:
            ry = (
                    min(selpendat[X_FIELD].min(), selpendat[Y_FIELD].min()),
                    max(selpendat[X_FIELD].max(), selpendat[Y_FIELD].max()))
        else:
            ry = (0, max(pdat[X_FIELD].max(),pdat[Y_FIELD].max()))
        self._penDataTimeLineWidget.setPlotRange(xrange=rx, yrange=ry)

    def jumpTimeSelectionForward(self):
        # TODO: Move method to _penDataTimeLineWidget
        xmin, xmax = self.project.selectedtimeregion.getRegion()
        pendata_ix_range = self.project.segmentset.calculateTrimmedSegmentIndexBoundsFromTimeRange(xmin, xmax)
        if len(pendata_ix_range):
            nix_min = pendata_ix_range[1]+1
            if self.project.pendata['pressure'][nix_min]==0.0:
                start_ixs,stop_ixs,lengths=self.project.nonzero_region_ix
                next_starts = start_ixs[start_ixs>nix_min]
                if len(next_starts)>0:
                    nix_min=next_starts[0]
                else:
                    infoDlg(title=u"Action Aborted", prompt=u"The selected time period can not be moved forward.<br>Reason: NTs index not available.")
                    return
            nxmin = self.project.pendata['time'][nix_min]
            nxmax = min(nxmin +(xmax-xmin), self.project.pendata['time'][-1])
            if nxmin >= nxmax:
                infoDlg(title=u"Action Aborted", prompt=u"The selected time period can not be moved forward.<br>Reason: End of data reached.")
                return
            self.project.selectedtimeregion.setRegion([nxmin,nxmax])

            (vmin,vmax),(_,_)=self._penDataTimeLineWidget.getViewRange()
            if nxmax >= vmax:
                self._penDataTimeLineWidget.translateViewBy(x=(nxmax-vmax)*1.25)

    def jumpTimeSelectionBackward(self):
        # TODO: Move method to _penDataTimeLineWidget
        if 0:
            xmin, xmax = self.project.selectedtimeregion.getRegion()
            nxmax =xmin-0.001
            nxmin = max(nxmax-(xmax-xmin),0.0)
            pendata_ix_range = self.project.segmentset.calculateTrimmedSegmentIndexBoundsFromTimeRange(nxmin,nxmax)
            if len(pendata_ix_range):
                segmenttimeperiod = self.project.pendata['time'][pendata_ix_range]
                self.project.selectedtimeregion.setRegion(segmenttimeperiod)

                (vmin,vmax),(_,_)=self._penDataTimeLineWidget.getViewRange()
                if nxmin < vmin:
                    self._penDataTimeLineWidget.translateViewBy(x=(nxmin-vmin)*1.25)
        else:
            xmin, xmax = self.project.selectedtimeregion.getRegion()
            pendata_ix_range = self.project.segmentset.calculateTrimmedSegmentIndexBoundsFromTimeRange(xmin, xmax)
            if len(pendata_ix_range):
                nix_max = pendata_ix_range[0]-1
                if nix_max<=0:
                    infoDlg(title=u"Action Aborted", prompt=u"The selected time period can not be moved backward.<br>Reason: NTe index out of bounds.")
                    return
                if self.project.pendata['pressure'][nix_max]==0.0:
                    start_ixs,stop_ixs,lengths=self.project.nonzero_region_ix
                    prev_stops = stop_ixs[stop_ixs<=nix_max]
                    if len(prev_stops)>0:
                        nix_max=prev_stops[-1]
                    else:
                        infoDlg(title=u"Action Aborted", prompt=u"The selected time period can not be moved backward.<br>Reason: NTe index not available.")
                        return
                nxmax = self.project.pendata['time'][nix_max]
                nxmin = max(nxmax -(xmax-xmin), 0.0)
                if nxmin >= nxmax:
                    infoDlg(title=u"Action Aborted", prompt=u"The selected time period can not be moved backward.<br>Reason: End of data reached.")
                    return
                self.project.selectedtimeregion.setRegion([nxmin,nxmax])

                (vmin,vmax),(_,_)=self._penDataTimeLineWidget.getViewRange()
                if nxmin <= vmin:
                    self._penDataTimeLineWidget.translateViewBy(x=(nxmin-vmin)*1.25)

    def increaseSelectionEndPointTime(self):
        # TODO: Move method to _penDataTimeLineWidget
        xmin, xmax = self.project.selectedtimeregion.getRegion()
        ix_bounds = self.project.segmentset.calculateTrimmedSegmentIndexBoundsFromTimeRange(xmin, xmax)
        if len(ix_bounds)>0:
            min_ix, max_ix = ix_bounds
            start_ixs,stop_ixs,lengths=self.project.nonzero_region_ix
            next_max_ix = stop_ixs[stop_ixs>(max_ix+1)][0]
            #print "org_max_ix, new_max_ix",max_ix,next_max_ix
            #print 'new start , end samples: ',self.project.pendata[[min_ix, next_max_ix]]
            if next_max_ix < self.project.pendata.shape[0]:
                segmenttimeperiod = self.project.pendata['time'][[min_ix, next_max_ix]]
                min_ix, next_max_ix = self.project.segmentset.calculateTrimmedSegmentIndexBoundsFromTimeRange(*segmenttimeperiod)
                self.project.selectedtimeregion.setRegion(self.project.pendata['time'][[min_ix, next_max_ix]])
                _,nxmax=segmenttimeperiod
                (vmin,vmax),(_,_)=self._penDataTimeLineWidget.getViewRange()
                if nxmax >= vmax:
                    self._penDataTimeLineWidget.translateViewBy(x=(nxmax-vmax)*1.25)
            else:
                 infoDlg(title=u"Action Aborted", prompt=u"The selected time period can not be extended<br>as it is at the end of the data samples.")


    def decreaseSelectionEndPointTime(self):
        # TODO: Move method to _penDataTimeLineWidget
        xmin, xmax = self.project.selectedtimeregion.getRegion()
        ix_bounds = self.project.segmentset.calculateTrimmedSegmentIndexBoundsFromTimeRange(xmin, xmax)
        if len(ix_bounds)>0:
            min_ix, max_ix = ix_bounds
            if np.all(self.project.nonzero_pressure_mask[min_ix:max_ix]):
                self.project.selectedtimeregion.setRegion(self.project.pendata['time'][[min_ix, max_ix]])
                return
            start_ixs, stop_ixs, lengths=self.project.nonzero_region_ix
            prev_maxs = stop_ixs[stop_ixs<max_ix]
            if prev_maxs.shape[0]>0:
                if prev_maxs[-1] > min_ix:
                    prev_max_ix = prev_maxs[-1]
                    segmenttimeperiod = self.project.pendata['time'][[min_ix, prev_max_ix]]
                    min_ix, max_ix = self.project.segmentset.calculateTrimmedSegmentIndexBoundsFromTimeRange(*segmenttimeperiod)
                    self.project.selectedtimeregion.setRegion(self.project.pendata['time'][[min_ix, max_ix]])
                else:
                    infoDlg(title=u"Action Aborted", prompt=u"The end time of the selected time period can not be decreased further<br>without it being equal to the selected periods start time.")

    def increaseSelectionStartPointTime(self):
        # TODO: Move method to _penDataTimeLineWidget
        xmin, xmax = self.project.selectedtimeregion.getRegion()
        ix_bounds = self.project.segmentset.calculateTrimmedSegmentIndexBoundsFromTimeRange(xmin, xmax)
        if len(ix_bounds)>0:
            min_ix, max_ix = ix_bounds
            if np.all(self.project.nonzero_pressure_mask[min_ix:max_ix]):
                self.project.selectedtimeregion.setRegion(self.project.pendata['time'][[min_ix, max_ix]])
                return
            start_ixs,stop_ixs,lengths=self.project.nonzero_region_ix
            higher_starts=start_ixs[start_ixs>(min_ix)]
            if len(higher_starts)==0:
                infoDlg(title=u"Action Aborted", prompt=u"The start time of the selected time period can not be increased<br> any further; it is the last IPS run of the file.")
            elif higher_starts[0]>=max_ix-1:
                infoDlg(title=u"Action Aborted", prompt=u"The start time of the selected time period can not be further increased<br> without it exceeding the selected periods end time.")
            else:
                segmenttimeperiod = self.project.pendata['time'][[higher_starts[0], max_ix]]
                self.project.selectedtimeregion.setRegion(segmenttimeperiod)

    def decreaseSelectionStartPointTime(self):
        # TODO: Move method to _penDataTimeLineWidget
        xmin, xmax = self.project.selectedtimeregion.getRegion()
        ix_bounds = self.project.segmentset.calculateTrimmedSegmentIndexBoundsFromTimeRange(xmin, xmax)
        if len(ix_bounds)>0:
            min_ix, max_ix = ix_bounds
            start_ixs, stop_ixs, lengths=self.project.nonzero_region_ix
            prev_starts = start_ixs[start_ixs<min_ix]
            if len(prev_starts)>0 and prev_starts[-1] >= 0:
                    prev_start_ix = prev_starts[-1]
                    segmenttimeperiod = self.project.pendata['time'][[prev_start_ix, max_ix]]
                    min_ix, max_ix = self.project.segmentset.calculateTrimmedSegmentIndexBoundsFromTimeRange(*segmenttimeperiod)
                    self.project.selectedtimeregion.setRegion(self.project.pendata['time'][[min_ix, max_ix]])
                    nxmin,_=segmenttimeperiod
                    (vmin,vmax),(_,_)=self._penDataTimeLineWidget.getViewRange()
                    if nxmin < vmin:
                        self._penDataTimeLineWidget.translateViewBy(x=(nxmin-vmin)*1.25)

    def handleSelectedPenDataUpdate(self, timeperiod, pendata):
        #print '>> App.handleSelectedPenDataUpdate:',timeperiod
        self.createSegmentAction.setEnabled(
            self.project and self.project.isSelectedDataValidForNewSegment())
        #print '<< App.handleSelectedPenDataUpdate'

    def handleDisplayAppSettingsDialogEvent(self):
        updatedsettings, allsettings, savestate, ok = ProjectSettingsDialog.getProjectSettings(self)
        if ok is True:
            if len(updatedsettings)>0:
                writePickle(self._appdirs.user_config_dir,u'usersettings.pkl', SETTINGS)
                #print "MAINWIN.writePickle called:",SETTINGS
            if self.project:
                self.sigAppSettingsUpdated.emit(updatedsettings, allsettings)

    def getNextUnitTimeRange(self, unit_lookup_table):
        selection_start, selection_end = self.project.selectedtimeregion.getRegion()
        next_units = unit_lookup_table[unit_lookup_table['start_time'] > selection_start]
        try:
            return next_units[0]['start_time'], next_units[0]['end_time']
        except:
            return None

    def getPreviousUnitTimeRange(self, unit_lookup_table):
        selection_start, selection_end = self.project.selectedtimeregion.getRegion()
        next_units = unit_lookup_table[unit_lookup_table['start_time'] < selection_start]
        try:
            return next_units[-1]['start_time'], next_units[-1]['end_time']
        except:
            return None

    def selectNextSampleSeries(self):
        seriestimerange = self.getNextUnitTimeRange(self.project.series_boundaries)
        if seriestimerange:
            self.project.selectedtimeregion.setRegion(seriestimerange)

    def selectPrevSampleSeries(self):
        seriestimerange = self.getPreviousUnitTimeRange(self.project.series_boundaries)
        if seriestimerange:
            self.project.selectedtimeregion.setRegion(seriestimerange)


    def selectNextPressedRun(self):
        runtimerange = self.getNextUnitTimeRange(self.project.press_period_boundaries)
        if runtimerange:
            self.project.selectedtimeregion.setRegion(runtimerange)


    def selectPrevPressedRun(self):
        runtimerange = self.getPreviousUnitTimeRange(self.project.press_period_boundaries)
        if runtimerange:
            self.project.selectedtimeregion.setRegion(runtimerange)

    def selectNextStroke(self):
        stroketimerange = self.getNextUnitTimeRange(self.project.stroke_boundaries)
        if stroketimerange:
            self.project.selectedtimeregion.setRegion(stroketimerange)

    def selectPrevStroke(self):
        stroketimerange = self.getPreviousUnitTimeRange(self.project.stroke_boundaries)
        if stroketimerange:
            self.project.selectedtimeregion.setRegion(stroketimerange)


    def closeEvent(self, event):
        if event == u'FORCE_EXIT':
            QtCore.QCoreApplication.instance().quit()
            return

        exitapp = ExitApplication.display()
        if exitapp:
            pass
            if event:
                event.accept()
            else:
                QtCore.QCoreApplication.instance().quit()
        else:
            if event:
                event.ignore()

    def __del__(self):
        pass

    def displayAllDataChannelsTimePlot(self):
            pw = pg.plot()
            pw.setWindowTitle('All Pen Samples')
            pw = pw.plotItem
            pw.setLabels(left='Pen Position')

            pw.addLegend()
            pdata=self.project.pendata


            def getPenBrushForAxis(axis, penpoints, penarray=None, brusharray=None):
                if penarray is None:
                    penarray = np.empty(penpoints.shape[0], dtype=object)
                    brusharray = np.empty(penpoints.shape[0], dtype=object)

                pen = pg.mkPen(SETTINGS['timeplot_%strace_color'%(axis)],
                               width=SETTINGS['timeplot_%strace_size'%(axis)])
                pen2 = pg.mkPen(SETTINGS['timeplot_%strace_color'%(axis)].darker(),
                                width=SETTINGS['timeplot_%strace_size'%(axis)])
                penarray[:] = pen
                penarray[penpoints['pressure'] == 0] = pen2

                brush = pg.mkBrush(SETTINGS['timeplot_%strace_color'%(axis)])
                brush2 = pg.mkBrush(SETTINGS['timeplot_%strace_color'%(axis)].darker())
                brusharray[:] = brush
                brusharray[penpoints['pressure'] == 0] = brush2

                return penarray, brusharray


#            left_axis = ('x','y')
#            penarray=None
#            brusharray=None
#            for axis  in left_axis:
#                penarray, brusharray = getPenBrushForAxis(axis,pdata,penarray,brusharray)
#                left_plot.plot(x=pdata['time'], y=pdata['%s_filtered'%(axis)],
#                                pen=None, symbol='o',
#                                symbolSize=SETTINGS[
#                                    'timeplot_%strace_size'%(axis)],
#                                symbolPen=penarray,
#                                symbolBrush=brusharray,
#                                name = "%s"%(axis))



            left_axis = ('v','a')
            axis2data=dict(v='xy_velocity',a='xy_acceleration')

            ssize= SETTINGS['pen_stroke_boundary_size']
            scolor = SETTINGS['pen_stroke_boundary_color']
            pen = pg.mkPen(scolor, width=ssize)
            brush = pg.mkBrush(scolor)
            strokeBoundaryPoints = pg.ScatterPlotItem(size=ssize, pen=pen, brush=brush)
            pw.addItem(strokeBoundaryPoints)
            strokeboundries=self.project.velocity_minima_samples
            for axis in left_axis:
                strokeBoundaryPoints.addPoints(x=strokeboundries['time'],
                                               y=strokeboundries[axis2data[axis]])


            penarray=None
            brusharray=None
            for axis  in left_axis:
                penarray, brusharray = getPenBrushForAxis(axis,pdata,penarray, brusharray)
                pw.addItem(pg.PlotCurveItem(x=pdata['time'],
                                                    y=pdata[axis2data[axis]],
                                                    pen=None, symbol='o',
                                                    symbolSize=SETTINGS[
                                                        'timeplot_%strace_size'%(axis)],
                                                    symbolPen=penarray,
                                                    symbolBrush=brusharray,
                                                    name = "%s"%(axis)))

#
## Main App Helpers
#

class ContextualStateAction(QtGui.QAction):
    def __init__(self, *args, **kwargs):
        QtGui.QAction.__init__(self, *args, **kwargs)
        self.enableActionsList = []
        self.disableActionsList = []

    def enableAndDisableActions(self):
        for ea in self.enableActionsList:
            ea.setEnabled(True)
        for da in self.disableActionsList:
            da.setDisabled(True)

    def setEnabled(self, b):
        QtGui.QAction.setEnabled(self, b)
        self.enableAndDisableActions()
#
## GraphicsWidgets
#


