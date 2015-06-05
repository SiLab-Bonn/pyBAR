import sys
import re
import zmq
import time
import numpy as np

from PyQt4 import Qt
from PyQt4.QtCore import pyqtSignal, pyqtSlot
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.dockarea import DockArea, Dock
import pyqtgraph.ptime as ptime
from threading import Event

from pybar.analysis.RawDataConverter.data_interpreter import PyDataInterpreter
from pybar.analysis.RawDataConverter.data_histograming import PyDataHistograming


class DataWorker(QtCore.QObject):
    run_start = QtCore.pyqtSignal()
    config_data = QtCore.pyqtSignal(dict)
    interpreted_data = QtCore.pyqtSignal(dict)
    meta_data = QtCore.pyqtSignal(dict)
    finished = QtCore.pyqtSignal()

    def __init__(self):
        QtCore.QObject.__init__(self)
        self.integrate_readouts = 1
        self.n_readout = 0
        self._stop_readout = Event()
        self.setup_raw_data_analysis()

    def setup_raw_data_analysis(self):
        self.interpreter = PyDataInterpreter()
        self.histograming = PyDataHistograming()
        self.interpreter.set_warning_output(False)
        self.histograming.set_no_scan_parameter()
        self.histograming.create_occupancy_hist(True)
        self.histograming.create_rel_bcid_hist(True)
        self.histograming.create_tot_hist(True)
        self.histograming.create_tdc_hist(True)

    def connect(self, socket_addr):
        self.socket_addr = socket_addr
        self.context = zmq.Context()
        self.socket_pull = self.context.socket(zmq.PULL)
        self.socket_pull.connect(self.socket_addr)
        self.poller = zmq.Poller()  # poll needed to be able to return QThread
        self.poller.register(self.socket_pull, zmq.POLLIN)

    @pyqtSlot(float)
    def on_set_integrate_readouts(self, value):
        self.integrate_readouts = value

    def analyze_raw_data(self, raw_data):
        self.interpreter.interpret_raw_data(raw_data)
        self.histograming.add_hits(self.interpreter.get_hits())

    def process_data(self):  # infinite loop via QObject.moveToThread(), does not block event loop
        while(not self._stop_readout.wait(0.001)):  # use wait(), do not block here
#             socks = dict(self.poller.poll(1))
#             if self.socket_pull in socks and socks[self.socket_pull] == zmq.POLLIN:
#                 meta_data = self.socket_pull.recv_json()
            try:
                meta_data = self.socket_pull.recv_json(flags=zmq.NOBLOCK)
            except zmq.Again:
                pass
            else:
                name = meta_data.pop('name')
                if name == 'FEI4readoutData':
                    data = self.socket_pull.recv()
                    # reconstruct numpy array
                    buf = buffer(data)
                    dtype = meta_data.pop('dtype')
                    shape = meta_data.pop('shape')
                    data_array = np.frombuffer(buf, dtype=dtype).reshape(shape)
                    # count readouts and reset
                    self.n_readout += 1
                    if self.integrate_readouts != 0 and self.n_readout % self.integrate_readouts == 0:
                        self.histograming.reset()
                        # we do not want to reset interpreter to keep the error counters
    #                         self.interpreter.reset()
                        # interpreted data
                    self.analyze_raw_data(data_array)
                    if self.integrate_readouts == 0 or self.n_readout % self.integrate_readouts == self.integrate_readouts - 1:
                        interpreted_data = {
                            'occupancy': self.histograming.get_occupancy(),
                            'tot_hist': self.histograming.get_tot_hist(),
                            'tdc_counters': self.interpreter.get_tdc_counters(),
                            'error_counters': self.interpreter.get_error_counters(),
                            'service_records_counters': self.interpreter.get_service_records_counters(),
                            'trigger_error_counters': self.interpreter.get_trigger_error_counters(),
                            'rel_bcid_hist': self.histograming.get_rel_bcid_hist()}
                        self.interpreted_data.emit(interpreted_data)
                    # meta data
                    meta_data.update({'n_hits': self.interpreter.get_n_hits(), 'n_events': self.interpreter.get_n_events()})
                    self.meta_data.emit(meta_data)
                elif name == 'RunConf':
                    # TODO: from FE config
                    try:
                        n_bcid = int(data[1]['trig_count'])
                    except KeyError:
                        n_bcid = 0
                    self.histograming.reset()
                    self.interpreter.reset()
                    self.interpreter.set_trig_count(n_bcid)
                    self.run_start.emit()
                    self.config_data.emit(meta_data)

        self.finished.emit()

#     @pyqtSlot()
    def stop(self):
        self._stop_readout.set()


class OnlineMonitorApplication(QtGui.QMainWindow):

    def __init__(self, socket_addr):
        super(OnlineMonitorApplication, self).__init__()
        self.setup_plots()
        self.add_widgets()
        self.fps = 0  # data frames per second
        self.hps = 0  # hits per second
        self.eps = 0  # events per second
        self.plot_delay = 0
        self.updateTime = ptime.time()
        self.total_hits = 0
        self.total_events = 0
        self.setup_data_worker_and_start(socket_addr)

    def closeEvent(self, event):
        super(OnlineMonitorApplication, self).closeEvent(event)
        # wait for thread
        self.worker.stop()
        #self.thread.wait()

    def setup_data_worker_and_start(self, socket_addr):
        self.thread = QtCore.QThread()  # no parent
        self.worker = DataWorker()  # no parent
        self.worker.meta_data.connect(self.on_meta_data)
        self.worker.interpreted_data.connect(self.on_interpreted_data)
        self.worker.run_start.connect(self.on_run_start)
        self.worker.config_data.connect(self.on_config_data)
        self.spin_box.valueChanged.connect(self.worker.on_set_integrate_readouts)
        self.worker.moveToThread(self.thread)
        self.worker.connect(socket_addr)
#         self.aboutToQuit.connect(self.worker.stop)  # QtGui.QApplication
        self.thread.started.connect(self.worker.process_data)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def setup_plots(self):
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')

    def add_widgets(self):
        # Main window with dock area
        self.dock_area = DockArea()
        self.setCentralWidget(self.dock_area)

        # Docks
        dock_occcupancy = Dock("Occupancy", size=(400, 400))
        dock_run_config = Dock("Configuration", size=(400, 400))
        dock_tot = Dock("Time over threshold values (TOT)", size=(400, 400))
        dock_tdc = Dock("Time digital converter values (TDC)", size=(400, 400))
        dock_event_status = Dock("Event status", size=(400, 400))
        dock_trigger_status = Dock("Trigger status", size=(400, 400))
        dock_service_records = Dock("Service records", size=(400, 400))
        dock_hit_timing = Dock("Hit timing (rel. BCID)", size=(400, 400))
        dock_status = Dock("Status", size=(800, 40))
        self.dock_area.addDock(dock_run_config, 'left')
        self.dock_area.addDock(dock_occcupancy, 'above', dock_run_config)
        self.dock_area.addDock(dock_tdc, 'right', dock_occcupancy)
        self.dock_area.addDock(dock_tot, 'above', dock_tdc)
        self.dock_area.addDock(dock_service_records, 'bottom', dock_occcupancy)
        self.dock_area.addDock(dock_trigger_status, 'above', dock_service_records)
        self.dock_area.addDock(dock_event_status, 'above', dock_trigger_status)
        self.dock_area.addDock(dock_hit_timing, 'bottom', dock_tot)
        self.dock_area.addDock(dock_status, 'top')

        # Status widget
        cw = QtGui.QWidget()
        cw.setStyleSheet("QWidget {background-color:white}")
        layout = QtGui.QGridLayout()
        cw.setLayout(layout)
        self.rate_label = QtGui.QLabel("Readout Rate\n0 Hz")
        self.hit_rate_label = QtGui.QLabel("Hit Rate\n0 Hz")
        self.event_rate_label = QtGui.QLabel("Event Rate\n0 Hz")
        self.timestamp_label = QtGui.QLabel("Data Timestamp\n")
        self.plot_delay_label = QtGui.QLabel("Plot Delay\n")
        self.scan_parameter_label = QtGui.QLabel("Scan Parameters\n")
        self.spin_box = Qt.QSpinBox(value=1)
        layout.addWidget(self.timestamp_label, 0, 0, 0, 1)
        layout.addWidget(self.plot_delay_label, 0, 1, 0, 1)
        layout.addWidget(self.rate_label, 0, 2, 0, 1)
        layout.addWidget(self.hit_rate_label, 0, 3, 0, 1)
        layout.addWidget(self.event_rate_label, 0, 4, 0, 1)
        layout.addWidget(self.scan_parameter_label, 0, 5, 0, 1)
        layout.addWidget(self.spin_box, 0, 6, 0, 1)
        dock_status.addWidget(cw)

        # Config dock
        self.run_conf_list_widget = Qt.QListWidget()
        dock_run_config.addWidget(self.run_conf_list_widget)

        # Different plot docks

        occupancy_graphics = pg.GraphicsLayoutWidget()
        occupancy_graphics.show()
        view = occupancy_graphics.addViewBox()
        self.occupancy_img = pg.ImageItem(border='w')
        view.addItem(self.occupancy_img)
        view.setRange(QtCore.QRectF(0, 0, 80, 336))
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
        dock_hit_timing.addWidget(hit_timing_widget)

    @pyqtSlot()
    def on_run_start(self):
        # clear config data widget
        self.run_conf_list_widget.clear()
        self.run_conf_list_widget.addItem(Qt.QListWidgetItem("No run configuration"))

    @pyqtSlot(dict)
    def on_config_data(self, config_data):
        self.setup_config_text(**config_data)

    def setup_config_text(self, conf):
        for key, value in conf.iteritems():
            item = Qt.QListWidgetItem("%s: %s" % (key, value))
            self.run_conf_list_widget.addItem(item)

    @pyqtSlot(dict)
    def on_interpreted_data(self, interpreted_data):
        self.update_plots(**interpreted_data)

    def update_plots(self, occupancy, tot_hist, tdc_counters, error_counters, service_records_counters, trigger_error_counters, rel_bcid_hist):
        self.occupancy_img.setImage(occupancy[:, ::-1, 0], autoDownsample=True)
        self.tot_plot.setData(x=np.linspace(-0.5, 15.5, 17), y=tot_hist, fillLevel=0, brush=(0, 0, 255, 150))
        self.tdc_plot.setData(x=np.linspace(-0.5, 4096.5, 4097), y=tdc_counters, fillLevel=0, brush=(0, 0, 255, 150))
        self.event_status_plot.setData(x=np.linspace(-0.5, 15.5, 17), y=error_counters, stepMode=True, fillLevel=0, brush=(0, 0, 255, 150))
        self.service_record_plot.setData(x=np.linspace(-0.5, 31.5, 33), y=service_records_counters, stepMode=True, fillLevel=0, brush=(0, 0, 255, 150))
        self.trigger_status_plot.setData(x=np.linspace(-0.5, 7.5, 9), y=trigger_error_counters, stepMode=True, fillLevel=0, brush=(0, 0, 255, 150))
        self.hit_timing_plot.setData(x=np.linspace(-0.5, 15.5, 17), y=rel_bcid_hist, stepMode=True, fillLevel=0, brush=(0, 0, 255, 150))

    @pyqtSlot(dict)
    def on_meta_data(self, meta_data):
        self.update_monitor(**meta_data)

    def update_monitor(self, timestamp_start, timestamp_stop, readout_error, scan_parameters, n_hits, n_events):
        self.timestamp_label.setText("Data Timestamp\n%s" % time.asctime(time.localtime(timestamp_stop)))
        self.scan_parameter_label.setText("Scan Parameters\n%s" % re.sub(r'[{}()\[\]\'\"]', '', repr(scan_parameters)[1:]))
        now = ptime.time()
        recent_total_hits = n_hits
        recent_total_events = n_events
        self.plot_delay = self.plot_delay * 0.9 + (now - timestamp_stop) * 0.1
        self.plot_delay_label.setText("Plot Delay\n%s" % ((time.strftime('%H:%M:%S', time.gmtime(self.plot_delay))) if self.plot_delay > 5 else "%1.2f ms" % (self.plot_delay * 1.e3)))
        recent_fps = 1.0 / (now - self.updateTime)  # calculate FPS
        recent_hps = (recent_total_hits - self.total_hits) / (now - self.updateTime)
        recent_eps = (recent_total_events - self.total_events) / (now - self.updateTime)
        self.updateTime = now
        self.total_hits = recent_total_hits
        self.total_events = recent_total_events
        self.fps = self.fps * 0.7 + recent_fps * 0.3
        self.hps = self.hps + (recent_hps - self.hps) * 0.3 / self.fps
        self.eps = self.eps + (recent_eps - self.eps) * 0.3 / self.fps
        self.rate_label.setText("Readout Rate\n%d Hz" % self.fps)
        if self.spin_box.value() == 0:  # show number of hits, all hits are integrated
            self.hit_rate_label.setText("Total Hits\n%d" % int(recent_total_hits))
        else:
            self.hit_rate_label.setText("Hit Rate\n%d Hz" % int(self.hps))
        if self.spin_box.value() == 0:  # show number of events
            self.event_rate_label.setText("Total Events\n%d" % int(recent_total_events))
        else:
            self.event_rate_label.setText("Event Rate\n%d Hz" % int(self.eps))


if __name__ == '__main__':
    app = Qt.QApplication(sys.argv)
#     app.aboutToQuit.connect(myExitHandler)
    win = OnlineMonitorApplication(socket_addr='tcp://127.0.0.1:5678')
    win.resize(800, 840)
    win.setWindowTitle('Online Monitor')
    win.show()
    sys.exit(app.exec_())
