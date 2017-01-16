import logging
import numpy as np
import tables as tb
import progressbar

from pybar.fei4.register_utils import make_box_pixel_mask_from_col_row
from pybar.fei4_run_base import Fei4RunBase
from pybar.run_manager import RunManager
from pybar.analysis.plotting.plotting import plot_three_way


class IleakScan(Fei4RunBase):
    '''Pixel leakage current scan using external multimeter.
    '''
    _default_run_conf = {
        "pixels": (np.dstack(np.where(make_box_pixel_mask_from_col_row([1, 16], [1, 36]) == 1)) + 1).tolist()[0],  # list of (col, row) tupels. From 1 to 80/336.
    }

    def configure(self):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        self.register.set_pixel_register_value('Imon', 0)
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name='Imon'))
        self.register_utils.send_commands(commands)
        self.ileakmap = np.zeros(shape=(80, 336))

    def scan(self):
        logging.info("Scanning %d pixels" % len(self.pixels))
        progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.AdaptiveETA()], maxval=len(self.pixels), term_width=80)
        progress_bar.start()

        data_out = self.raw_data_file.h5_file.create_carray(self.raw_data_file.h5_file.root, name='Ileak_map', title='Leakage current per pixel in arbitrary units', atom=tb.Atom.from_dtype(self.ileakmap.dtype), shape=self.ileakmap.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))

        for pixel_index, (column, row) in enumerate(self.pixels):
            if self.stop_run.is_set():
                break
            # Set Imon for actual pixel and configure FE
            mask = np.zeros(shape=(80, 336))
            mask[column - 1, row - 1] = 1
            commands = []
            commands.extend(self.register.get_commands("ConfMode"))
            self.register.set_pixel_register_value('Imon', mask)
            commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, name='Imon'))
            self.register_utils.send_commands(commands)
            # Read and store voltage
            voltage_string = self.dut['Multimeter'].get_voltage()
            voltage = float(voltage_string.split(',')[0][:-4])
            self.ileakmap[column - 1, row - 1] = voltage

            progress_bar.update(pixel_index)

        progress_bar.finish()

        data_out[:] = self.ileakmap

    def analyze(self):
        with tb.open_file(self.output_filename + '.h5', 'r') as in_file_h5:
            data = in_file_h5.root.Ileak_map[:]
            data = np.ma.masked_where(data == 0, data)
            plot_three_way(hist=data.transpose(), title="Ileak", x_axis_title="Ileak", filename=self.output_filename + '.pdf')  # , minimum=0, maximum=np.amax(data))


if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(IleakScan)
