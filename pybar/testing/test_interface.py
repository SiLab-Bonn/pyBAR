''' Script to check the readout system interface (software + FPGA firmware).
A global register test is performed with pyBAR and a simulation of the FPGA + FE-I4.
'''
import unittest
import shutil
import mock
try:
    import Queue as queue
except ImportError:
    import queue
import subprocess
import time
import os
import logging

from pybar.run_manager import RunManager
from pybar.scans.test_register import RegisterTest


def configure_pixel(self, same_mask_for_all_dc=False):
    return


def send_commands(self, commands, repeat=1, wait_for_finish=True, concatenate=True, byte_padding=False, clear_memory=False, use_timeout=True):
    # no timeout for simulation
    use_timeout = False
    # append some zeros since simulation needs more time for calculation
    commands.extend(self.register.get_commands("zeros", length=20))
    if concatenate:
        commands_iter = iter(commands)
        try:
            concatenated_cmd = next(commands_iter)
        except StopIteration:
            logging.warning('No commands to be sent')
        else:
            for command in commands_iter:
                concatenated_cmd_tmp = self.concatenate_commands((concatenated_cmd, command), byte_padding=byte_padding)
                if concatenated_cmd_tmp.length() > self.command_memory_byte_size * 8:
                    self.send_command(command=concatenated_cmd, repeat=repeat, wait_for_finish=wait_for_finish, set_length=True, clear_memory=clear_memory, use_timeout=use_timeout)
                    concatenated_cmd = command
                else:
                    concatenated_cmd = concatenated_cmd_tmp
            # send remaining commands
            self.send_command(command=concatenated_cmd, repeat=repeat, wait_for_finish=wait_for_finish, set_length=True, clear_memory=clear_memory, use_timeout=use_timeout)
    else:
        max_length = 0
        if repeat:
            self.dut['CMD']['CMD_REPEAT'] = repeat
        for command in commands:
            max_length = max(command.length(), max_length)
            self.send_command(command=command, repeat=None, wait_for_finish=wait_for_finish, set_length=True, clear_memory=False, use_timeout=use_timeout)
        if clear_memory:
            self.clear_command_memory(length=max_length)


class TestInterface(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        subprocess.call('unzip -o test_interface_data/sim_build.zip', shell=True)
        subprocess.Popen(['make', '-f', '../../firmware/mio/cosim/Makefile', 'sim_only'])
        time.sleep(10)  # some time for simulator to start

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree('test_interface_data/module_test', ignore_errors=True)
        shutil.rmtree('./sim_build', ignore_errors=True)
        try:
            os.remove('./results.xml')
        except OSError:
            pass
        # keep waveform file
#         shutil.rmtree('./tb.vcd', ignore_errors=True)

    @mock.patch('pybar.fei4.register_utils.FEI4RegisterUtils.configure_pixel', autospec=True, side_effect=lambda *args, **kwargs: configure_pixel(*args, **kwargs))
    @mock.patch('pybar.fei4.register_utils.FEI4RegisterUtils.send_commands', autospec=True, side_effect=lambda *args, **kwargs: send_commands(*args, **kwargs))
    def test_global_register(self, mock_send_commands, mock_configure_pixel):
        run_manager = RunManager('test_interface_data/configuration.yaml')
        run_manager.run_run(RegisterTest, run_conf={'test_pixel': False})
        error_msg = 'Global register test failed. '
        try:
            error_msg += str(run_manager.current_run.err_queue.get(timeout=1)[1])
        except queue.Empty:
            pass
        ok = (run_manager.current_run._run_status == 'FINISHED')
        self.assertTrue(ok, msg=error_msg)


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestInterface)
    unittest.TextTestRunner(verbosity=2).run(suite)
