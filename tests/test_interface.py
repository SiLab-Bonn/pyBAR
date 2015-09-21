''' Script to check the readout system interface (software + FPGA firmware).
A global register test is performed with pyBAR and a simulation of the FPGA + FE-I4.
'''
import unittest
import shutil
import mock
from Queue import Empty
import subprocess
import time
import os

from pybar.run_manager import RunManager
from pybar.fei4.register_utils.FEI4RegisterUtils import send_commands
from pybar.scans.test_register import RegisterTest


def mock_configure_pixel(self, same_mask_for_all_dc=False):
    return


def mock_send_commands(self, commands, repeat=1, wait_for_finish=True, concatenate=True, byte_padding=False, clear_memory=False, use_timeout=True):
    # no timeout for simulation
    use_timeout = False
    # append some zeros since simulation is more slow
    commands.extend(self.register.get_commands("zeros", length=20))
    return send_commands(self, commands=commands, repeat=repeat, wait_for_finish=wait_for_finish, concatenate=concatenate, byte_padding=byte_padding, clear_memory=clear_memory, use_timeout=use_timeout)


class TestInterface(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        subprocess.call('unzip -o test_interface/sim_build.zip', shell=True)
        subprocess.Popen(['make', '-f', '../firmware/mio/cosim/Makefile', 'sim_only'])
        time.sleep(10)  # some time for simulator to start

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree('test_interface/module_test', ignore_errors=True)
        shutil.rmtree('./sim_build', ignore_errors=True)
        try:
            os.remove('./results.xml')
        except OSError:
            pass
        # keep waveform file
#         shutil.rmtree('./tb.vcd', ignore_errors=True)

    @mock.patch('pybar.fei4.register_utils.FEI4RegisterUtils.configure_pixel', autospec=True, side_effect=lambda *args, **kwargs: mock_configure_pixel(*args, **kwargs))
    @mock.patch('pybar.fei4.register_utils.FEI4RegisterUtils.send_commands', autospec=True, side_effect=lambda *args, **kwargs: mock_send_commands(*args, **kwargs))
    def test_global_register(self, mock_send_commands, mock_configure_pixel):
        run_manager = RunManager('test_interface/configuration.yaml')
        run_manager.run_run(RegisterTest, run_conf={'test_pixel': False})
        error_msg = 'Global register test failed. '
        try:
            error_msg += str(run_manager.current_run.err_queue.get(timeout=1)[1])
        except Empty:
            pass
        ok = (run_manager.current_run._run_status == 'FINISHED')
        self.assertTrue(ok, msg=error_msg)


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestInterface)
    unittest.TextTestRunner(verbosity=2).run(suite)
