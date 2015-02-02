# -*- coding: utf-8 -*-
import sys
import zmq
from PyQt4 import Qt

import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.dockarea import DockArea, Dock
import numpy as np
import pyqtgraph.ptime as ptime

from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.analysis.RawDataConverter.data_interpreter import PyDataInterpreter
from pybar.analysis.RawDataConverter import data_struct
from pybar.analysis.RawDataConverter.data_histograming import PyDataHistograming


class OnlineMonitorApplication(Qt.QApplication):

    def __init__(self, args):
        Qt.QApplication.__init__(self, args)
        self.connect()
        self.setup_raw_data_analysis()
        self.setup_plots()
        self.addWidgets()
        self.fps = 0
        self.updateTime = ptime.time()
        self.handleData()
        self.exec_()

    def setup_raw_data_analysis(self):
        self.interpreter = PyDataInterpreter()
        self.histograming = PyDataHistograming()
        self.interpreter.set_warning_output(False)
        self.histograming.set_no_scan_parameter()
        self.histograming.create_occupancy_hist(True)
        self.histograming.create_rel_bcid_hist(True)
        self.histograming.create_tot_hist(True)
        self.histograming.create_tdc_hist(True)

    def connect(self):
        context = zmq.Context()
        self.socket = context.socket(zmq.PULL)
        self.socket.connect("tcp://127.0.0.1:5678")

    def setup_plots(self):
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')

    def addWidgets(self):
        self.window = QtGui.QMainWindow()
        self.dock_area = DockArea()
        self.window.setCentralWidget(self.dock_area)
        self.window.resize(800, 800)
        self.window.setWindowTitle('Online Monitor')
        self.window.show()

        dock_occcupancy = Dock("Occupancy", size=(400, 400))
        dock_tot = Dock("Time over threshold values (TOT)", size=(400, 400))
        dock_tdc = Dock("Time digital converter values (TDC)", size=(400, 400))
        dock_event_status = Dock("Event status", size=(400, 400))
        dock_trigger_status = Dock("Trigger status", size=(400, 400))
        dock_service_records = Dock("Service records", size=(400, 400))
        dock_hit_timing = Dock("Hit timing (rel. BCID)", size=(400, 400))
        self.dock_area.addDock(dock_occcupancy, 'left')
        self.dock_area.addDock(dock_tdc, 'right', dock_occcupancy)
        self.dock_area.addDock(dock_tot, 'above', dock_tdc)
        self.dock_area.addDock(dock_service_records, 'bottom', dock_occcupancy)
        self.dock_area.addDock(dock_trigger_status, 'above', dock_service_records)
        self.dock_area.addDock(dock_event_status, 'above', dock_trigger_status)
        self.dock_area.addDock(dock_hit_timing, 'bottom', dock_tot)  # place d5 at top edge of d4

        occupancy_graphics = pg.GraphicsLayoutWidget()
        occupancy_graphics.show()  # show widget alone in its own window
        view = occupancy_graphics.addViewBox()
        self.occupancy_img = pg.ImageItem(border='w')
        view.addItem(self.occupancy_img)
        view.setRange(QtCore.QRectF(0, 0, 80, 336))
        self.text = pg.TextItem(html='<div style="text-align: center"><span style="color: #FFF;">No</span><br><span style="color: #FF0; connection: 16pt;">data</span></div>', anchor=(-0.3, 1.3), border='w', fill=(0, 0, 255, 100))
        view.addItem(self.text)
        dock_occcupancy.addWidget(occupancy_graphics)

        tot_plot_widget = pg.PlotWidget(background="w")
        self.tot_plot = tot_plot_widget.plot(np.linspace(-0.5, 15.5, 17), np.zeros((16)), stepMode=True)
        tot_plot_widget.showGrid(y=True)
        dock_tot.addWidget(tot_plot_widget)

        tdc_plot_widget = pg.PlotWidget(background="w")
        self.tdc_plot = tdc_plot_widget.plot(np.linspace(-0.5, 4095.5, 4097), np.zeros((4096)), stepMode=True)
        tdc_plot_widget.showGrid(y=True)
        tdc_plot_widget.setXRange(0, 800, update=True)
        dock_tdc.addWidget(tdc_plot_widget)

        event_status_widget = pg.PlotWidget()
        self.event_status_plot = event_status_widget.plot(np.linspace(-0.5, 15.5, 17), np.zeros((16)), stepMode=True)
        event_status_widget.showGrid(y=True)
#         event_status_widget.setLogMode(y=True)
        dock_event_status.addWidget(event_status_widget)

        trigger_status_widget = pg.PlotWidget()
        self.trigger_status_plot = trigger_status_widget.plot(np.linspace(-0.5, 7.5, 9), np.zeros((8)), stepMode=True)
        trigger_status_widget.showGrid(y=True)
        dock_trigger_status.addWidget(trigger_status_widget)

        service_record_widget = pg.PlotWidget()
        self.service_record_plot = service_record_widget.plot(np.linspace(-0.5, 31.5, 33), np.zeros((32)), stepMode=True)
        service_record_widget.showGrid(y=True)
        dock_service_records.addWidget(service_record_widget)

        hit_timing_widget = pg.PlotWidget()
        self.hit_timing_plot = hit_timing_widget.plot(np.linspace(-0.5, 15.5, 17), np.zeros((16)), stepMode=True)
        hit_timing_widget.showGrid(y=True)
#         hit_timing_widget.setLogMode(y=True)
        dock_hit_timing.addWidget(hit_timing_widget)

    def handleData(self):
        raw_data = self.recv_array()
        if np.any(raw_data):
            self.analyze_raw_data(raw_data)
            self.updatePlots()
        QtCore.QTimer.singleShot(1, self.handleData)

    def recv_array(self, flags=0, copy=True, track=False):
        try:
            array_meta_data = self.socket.recv_json(flags=zmq.NOBLOCK)
            msg = self.socket.recv(flags=flags, copy=copy, track=track)
            array = np.fromstring(msg, dtype=array_meta_data['dtype'])
            return array.reshape(array_meta_data['shape'])
        except zmq.error.Again:
            return None

    def analyze_raw_data(self, raw_data):
        self.interpreter.interpret_raw_data(raw_data)
        self.histograming.add_hits(self.interpreter.get_hits())

    def updatePlots(self):
        self.occupancy_img.setImage(self.histograming.get_occupancy()[:, ::-1, 0], autoDownsample=True)
        self.tot_plot.setData(x=np.linspace(-0.5, 15.5, 17), y=self.histograming.get_tot_hist(), fillLevel=0, brush=(0, 0, 255, 150))
        self.tdc_plot.setData(x=np.linspace(-0.5, 4096.5, 4097), y=self.interpreter.get_tdc_counters(), fillLevel=0, brush=(0, 0, 255, 150))
        self.event_status_plot.setData(x=np.linspace(-0.5, 15.5, 17), y=self.interpreter.get_error_counters(), stepMode=True, fillLevel=0, brush=(0, 0, 255, 150))
        self.service_record_plot.setData(x=np.linspace(-0.5, 31.5, 33), y=self.interpreter.get_service_records_counters(), stepMode=True, fillLevel=0, brush=(0, 0, 255, 150))
        self.trigger_status_plot.setData(x=np.linspace(-0.5, 7.5, 9), y=self.interpreter.get_trigger_error_counters(), stepMode=True, fillLevel=0, brush=(0, 0, 255, 150))
        self.hit_timing_plot.setData(x=np.linspace(-0.5, 15.5, 17), y=self.histograming.get_rel_bcid_hist(), stepMode=True, fillLevel=0, brush=(0, 0, 255, 150))
        #  calculate analyzed readouts per second
        now = ptime.time()
        fps2 = 1.0 / (now - self.updateTime)
        self.updateTime = now
        self.fps = self.fps * 0.9 + fps2 * 0.1
        self.text.setText("FPS %d" % self.fps)


if __name__ == '__main__':
    app = OnlineMonitorApplication(sys.argv)
