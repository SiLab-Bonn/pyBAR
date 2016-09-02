import sys
import zmq
import time
import numpy as np
from optparse import OptionParser

from PyQt4 import Qt
from PyQt4.QtCore import pyqtSlot, pyqtSignal
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.dockarea import DockArea, Dock
import pyqtgraph.ptime as ptime
from threading import Event, Lock

from pybar_fei4_interpreter.data_interpreter import PyDataInterpreter
from pybar_fei4_interpreter.data_histograming import PyDataHistograming


class DataWorker(QtCore.QObject):
    run_start = QtCore.pyqtSignal()
    run_config_data = QtCore.pyqtSignal(dict)
    global_config_data = QtCore.pyqtSignal(dict)
    filename = QtCore.pyqtSignal(dict)
    interpreted_data = QtCore.pyqtSignal(dict)
    meta_data = QtCore.pyqtSignal(dict)
    finished = QtCore.pyqtSignal()

    def __init__(self):
        QtCore.QObject.__init__(self)
        self.integrate_readouts = 1
        self.n_readout = 0
        self._stop_readout = Event()
        self.setup_raw_data_analysis()
        self.reset_lock = Lock()

    def setup_raw_data_analysis(self):
        self.interpreter = PyDataInterpreter()
        self.histograming = PyDataHistograming()
        self.interpreter.set_warning_output(False)
        self.histograming.set_no_scan_parameter()
        self.histograming.create_occupancy_hist(True)
        self.histograming.create_rel_bcid_hist(True)
        self.histograming.create_tot_hist(True)
        self.histograming.create_tdc_hist(True)
        try:
            self.histograming.create_tdc_distance_hist(True)
            self.interpreter.use_tdc_trigger_time_stamp(True)
        except AttributeError:
            self.has_tdc_distance = False
        else:
            self.has_tdc_distance = True

    def connect(self, socket_addr):
        self.socket_addr = socket_addr
        self.context = zmq.Context()
        self.socket_pull = self.context.socket(zmq.SUB)  # subscriber
        self.socket_pull.setsockopt(zmq.SUBSCRIBE, '')  # do not filter any data
        self.socket_pull.connect(self.socket_addr)

    @pyqtSlot(float)
    def on_set_integrate_readouts(self, value):
        self.integrate_readouts = value

#     @pyqtSlot()
    def reset(self):
        with self.reset_lock:
            self.histograming.reset()
            self.interpreter.reset()
            self.n_readout = 0

    def analyze_raw_data(self, raw_data):
        self.interpreter.interpret_raw_data(raw_data)
        self.histograming.add_hits(self.interpreter.get_hits())

    @pyqtSlot()
    def process_data(self):  # infinite loop via QObject.moveToThread(), does not block event loop
        while(not self._stop_readout.wait(0.01)):  # use wait(), do not block here
            with self.reset_lock:
                try:
                    meta_data = self.socket_pull.recv_json(flags=zmq.NOBLOCK)
                except zmq.Again:
                    pass
                else:
                    name = meta_data.pop('name')
                    if name == 'ReadoutData':
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
                                'tdc_distance': self.interpreter.get_tdc_distance() if self.has_tdc_distance else np.zeros((256,), dtype=np.uint8),
                                'error_counters': self.interpreter.get_error_counters(),
                                'service_records_counters': self.interpreter.get_service_records_counters(),
                                'trigger_error_counters': self.interpreter.get_trigger_error_counters(),
                                'rel_bcid_hist': self.histograming.get_rel_bcid_hist()}
                            self.interpreted_data.emit(interpreted_data)
                        # meta data
                        meta_data.update({'n_hits': self.interpreter.get_n_hits(), 'n_events': self.interpreter.get_n_events()})
                        self.meta_data.emit(meta_data)
                    elif name == 'RunConf':
                        self.run_config_data.emit(meta_data)
                    elif name == 'GlobalRegisterConf':
                        trig_count = int(meta_data['conf']['Trig_Count'])
                        self.interpreter.set_trig_count(trig_count)
                        self.global_config_data.emit(meta_data)
                    elif name == 'Reset':
                        self.histograming.reset()
                        self.interpreter.reset()
                        self.run_start.emit()
                    elif name == 'Filename':
                        self.filename.emit(meta_data)
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
        self.reset_plots()

    def closeEvent(self, event):
        super(OnlineMonitorApplication, self).closeEvent(event)
        # wait for thread
        self.worker.stop()
        self.thread.wait(2)  # fixes message: QThread: Destroyed while thread is still running

    def setup_data_worker_and_start(self, socket_addr):
        self.thread = QtCore.QThread()  # no parent
        self.worker = DataWorker()  # no parent
        self.worker.meta_data.connect(self.on_meta_data)
        self.worker.interpreted_data.connect(self.on_interpreted_data)
        self.worker.run_start.connect(self.on_run_start)
        self.worker.run_config_data.connect(self.on_run_config_data)
        self.worker.global_config_data.connect(self.on_global_config_data)
        self.worker.filename.connect(self.on_filename)
        self.spin_box.valueChanged.connect(self.worker.on_set_integrate_readouts)
        self.reset_button.clicked.connect(self.on_reset)
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
        dock_run_config = Dock("Run configuration", size=(400, 400))
        dock_global_config = Dock("Global configuration", size=(400, 400))
        dock_tot = Dock("ToT", size=(400, 400))
        dock_tdc = Dock("TDC", size=(400, 400))
        dock_tdc_distance = Dock("TDC distance", size=(400, 400))
        dock_event_status = Dock("Event status", size=(400, 400))
        dock_trigger_status = Dock("Trigger status", size=(400, 400))
        dock_service_records = Dock("Service records", size=(400, 400))
        dock_hit_timing = Dock("Hit timing (rel. BCID)", size=(400, 400))
        dock_status = Dock("Status", size=(800, 40))
        self.dock_area.addDock(dock_global_config, 'left')
        self.dock_area.addDock(dock_run_config, 'above', dock_global_config)
        self.dock_area.addDock(dock_occcupancy, 'above', dock_run_config)
        self.dock_area.addDock(dock_tdc_distance, 'right', dock_occcupancy)
        self.dock_area.addDock(dock_tdc, 'above', dock_tdc_distance)
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
        self.spin_box.setMaximum(1000000)
        self.spin_box.setSuffix(" Readouts")
        self.reset_button = QtGui.QPushButton('Reset')
        layout.addWidget(self.timestamp_label, 0, 0, 0, 1)
        layout.addWidget(self.plot_delay_label, 0, 1, 0, 1)
        layout.addWidget(self.rate_label, 0, 2, 0, 1)
        layout.addWidget(self.hit_rate_label, 0, 3, 0, 1)
        layout.addWidget(self.event_rate_label, 0, 4, 0, 1)
        layout.addWidget(self.scan_parameter_label, 0, 5, 0, 1)
        layout.addWidget(self.spin_box, 0, 6, 0, 1)
        layout.addWidget(self.reset_button, 0, 7, 0, 1)
        dock_status.addWidget(cw)

        # Run config dock
        self.run_conf_list_widget = Qt.QListWidget()
        dock_run_config.addWidget(self.run_conf_list_widget)

        # Global config dock
        self.global_conf_list_widget = Qt.QListWidget()
        dock_global_config.addWidget(self.global_conf_list_widget)

        # Different plot docks
        occupancy_graphics = pg.GraphicsLayoutWidget()
        occupancy_graphics.show()
        view = occupancy_graphics.addViewBox()
        self.occupancy_img = pg.ImageItem(border='w')
        view.addItem(self.occupancy_img)
        view.setRange(QtCore.QRectF(0, 0, 80, 336))
        dock_occcupancy.addWidget(occupancy_graphics)

        tot_plot_widget = pg.PlotWidget(background="w")
        self.tot_plot = tot_plot_widget.plot(np.linspace(-0.5, 15.5, 17, endpoint=True), np.zeros((16)), stepMode=True)
        tot_plot_widget.showGrid(y=True)
        dock_tot.addWidget(tot_plot_widget)

        tdc_plot_widget = pg.PlotWidget(background="w")
        self.tdc_plot = tdc_plot_widget.plot(np.linspace(-0.5, 4095.5, 4097, endpoint=True), np.zeros((4096)), stepMode=True)
        tdc_plot_widget.showGrid(y=True)
        tdc_plot_widget.setXRange(0, 800, update=True)
        dock_tdc.addWidget(tdc_plot_widget)

        tdc_distance_plot_widget = pg.PlotWidget(background="w")
        self.tdc_distance_plot = tdc_distance_plot_widget.plot(np.linspace(-0.5, 255.5, 257, endpoint=True), np.zeros((256)), stepMode=True)
        tdc_distance_plot_widget.showGrid(y=True)
        tdc_distance_plot_widget.setXRange(0, 800, update=True)
        dock_tdc_distance.addWidget(tdc_distance_plot_widget)

        event_status_widget = pg.PlotWidget()
        self.event_status_plot = event_status_widget.plot(np.linspace(-0.5, 15.5, 17, endpoint=True), np.zeros((16)), stepMode=True)
        event_status_widget.showGrid(y=True)
        dock_event_status.addWidget(event_status_widget)

        trigger_status_widget = pg.PlotWidget()
        self.trigger_status_plot = trigger_status_widget.plot(np.linspace(-0.5, 7.5, 9, endpoint=True), np.zeros((8)), stepMode=True)
        trigger_status_widget.showGrid(y=True)
        dock_trigger_status.addWidget(trigger_status_widget)

        service_record_widget = pg.PlotWidget()
        self.service_record_plot = service_record_widget.plot(np.linspace(-0.5, 31.5, 33, endpoint=True), np.zeros((32)), stepMode=True)
        service_record_widget.showGrid(y=True)
        dock_service_records.addWidget(service_record_widget)

        hit_timing_widget = pg.PlotWidget()
        self.hit_timing_plot = hit_timing_widget.plot(np.linspace(-0.5, 15.5, 17, endpoint=True), np.zeros((16)), stepMode=True)
        hit_timing_widget.showGrid(y=True)
        dock_hit_timing.addWidget(hit_timing_widget)

    @pyqtSlot()
    def on_reset(self):
        self.worker.reset()
        self.total_hits = 0
        self.total_events = 0
        self.reset_plots()
        self.update_rate(0, 0, 0, 0, 0)

    @pyqtSlot()
    def on_run_start(self):
        # clear config data widgets
        self.run_conf_list_widget.clear()
        self.global_conf_list_widget.clear()
        self.setWindowTitle('Online Monitor')

    @pyqtSlot(dict)
    def on_run_config_data(self, config_data):
        self.setup_run_config_text(**config_data)

    @pyqtSlot(dict)
    def on_global_config_data(self, config_data):
        self.setup_global_config_text(**config_data)

    @pyqtSlot(dict)
    def on_filename(self, config_data):
        self.setup_filename(**config_data)

    def setup_run_config_text(self, conf):
        for key, value in sorted(conf.iteritems()):
            item = Qt.QListWidgetItem("%s: %s" % (key, value))
            self.run_conf_list_widget.addItem(item)

    def setup_global_config_text(self, conf):
        for key, value in sorted(conf.iteritems()):
            item = Qt.QListWidgetItem("%s: %s" % (key, value))
            self.global_conf_list_widget.addItem(item)

    def setup_filename(self, conf):
        self.setWindowTitle('Online Monitor - %s' % conf)

    @pyqtSlot(dict)
    def on_interpreted_data(self, interpreted_data):
        self.update_plots(**interpreted_data)

    def reset_plots(self):
        self.update_plots(np.zeros((80, 336, 1), dtype=np.uint8), np.zeros((16,), dtype=np.uint8), np.zeros((4096,), dtype=np.uint8), np.zeros((256,), dtype=np.uint8), np.zeros((16,), dtype=np.uint8), np.zeros((32,), dtype=np.uint8), np.zeros((8,), dtype=np.uint8), np.zeros((16,), dtype=np.uint8))

    def update_plots(self, occupancy, tot_hist, tdc_counters, tdc_distance, error_counters, service_records_counters, trigger_error_counters, rel_bcid_hist):
        self.occupancy_img.setImage(occupancy[:, ::-1, 0], autoDownsample=True)
        self.tot_plot.setData(x=np.linspace(-0.5, 15.5, 17, endpoint=True), y=tot_hist, fillLevel=0, brush=(0, 0, 255, 150), stepMode=True)
        self.tdc_plot.setData(x=np.linspace(-0.5, 4095.5, 4097, endpoint=True), y=tdc_counters, fillLevel=0, brush=(0, 0, 255, 150), stepMode=True)
        self.tdc_distance_plot.setData(x=np.linspace(-0.5, 255.5, 257, endpoint=True), y=tdc_distance, fillLevel=0, brush=(0, 0, 255, 150), stepMode=True)
        self.event_status_plot.setData(x=np.linspace(-0.5, 15.5, 17, endpoint=True), y=error_counters, fillLevel=0, brush=(0, 0, 255, 150), stepMode=True)
        self.service_record_plot.setData(x=np.linspace(-0.5, 31.5, 33, endpoint=True), y=service_records_counters, fillLevel=0, brush=(0, 0, 255, 150), stepMode=True)
        self.trigger_status_plot.setData(x=np.linspace(-0.5, 7.5, 9, endpoint=True), y=trigger_error_counters, fillLevel=0, brush=(0, 0, 255, 150), stepMode=True)
        self.hit_timing_plot.setData(x=np.linspace(-0.5, 15.5, 17, endpoint=True), y=rel_bcid_hist[:16], fillLevel=0, brush=(0, 0, 255, 150), stepMode=True)

    @pyqtSlot(dict)
    def on_meta_data(self, meta_data):
        self.update_monitor(**meta_data)

    def update_monitor(self, timestamp_start, timestamp_stop, readout_error, scan_parameters, n_hits, n_events):
        self.timestamp_label.setText("Data Timestamp\n%s" % time.asctime(time.localtime(timestamp_stop)))
        self.scan_parameter_label.setText("Scan Parameters\n%s" % ', '.join('%s: %s' % (str(key), str(val)) for key, val in scan_parameters.iteritems()))
        now = ptime.time()
        recent_total_hits = n_hits
        recent_total_events = n_events
        self.plot_delay = self.plot_delay * 0.9 + (now - timestamp_stop) * 0.1
        self.plot_delay_label.setText("Plot Delay\n%s" % ((time.strftime('%H:%M:%S', time.gmtime(self.plot_delay))) if abs(self.plot_delay) > 5 else "%1.2f ms" % (self.plot_delay * 1.e3)))
        recent_fps = 1.0 / (now - self.updateTime)  # calculate FPS
        recent_hps = (recent_total_hits - self.total_hits) / (now - self.updateTime)
        recent_eps = (recent_total_events - self.total_events) / (now - self.updateTime)
        self.updateTime = now
        self.total_hits = recent_total_hits
        self.total_events = recent_total_events
        self.fps = self.fps * 0.7 + recent_fps * 0.3
        self.hps = self.hps + (recent_hps - self.hps) * 0.3 / self.fps
        self.eps = self.eps + (recent_eps - self.eps) * 0.3 / self.fps
        self.update_rate(self.fps, self.hps, recent_total_hits, self.eps, recent_total_events)

    def update_rate(self, fps, hps, recent_total_hits, eps, recent_total_events):
        self.rate_label.setText("Readout Rate\n%d Hz" % fps)
        if self.spin_box.value() == 0:  # show number of hits, all hits are integrated
            self.hit_rate_label.setText("Total Hits\n%d" % int(recent_total_hits))
        else:
            self.hit_rate_label.setText("Hit Rate\n%d Hz" % int(hps))
        if self.spin_box.value() == 0:  # show number of events
            self.event_rate_label.setText("Total Events\n%d" % int(recent_total_events))
        else:
            self.event_rate_label.setText("Event Rate\n%d Hz" % int(eps))


if __name__ == '__main__':
    usage = "Usage: %prog ADDRESS"
    description = "ADDRESS: Remote address of the sender (default: tcp://127.0.0.1:5678)."
    parser = OptionParser(usage, description=description)
    options, args = parser.parse_args()
    if len(args) == 0:
        socket_addr = 'tcp://127.0.0.1:5678'
    elif len(args) == 1:
        socket_addr = args[0]
    else:
        parser.error("incorrect number of arguments")

    app = Qt.QApplication(sys.argv)
#     app.aboutToQuit.connect(myExitHandler)
    win = OnlineMonitorApplication(socket_addr=socket_addr)  # enter remote IP to connect to the other side listening
    win.resize(800, 840)
    win.setWindowTitle('Online Monitor')
    win.show()
    sys.exit(app.exec_())
