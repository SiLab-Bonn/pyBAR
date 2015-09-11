''' Script to check the readout system interface (software + FPGA firmware).
A global register test is performed with pyBAR and a simulation of the FPGA + FE-I4.
'''
import unittest
import shutil
import mock
from Queue import Empty
import subprocess
import time

from pybar.run_manager import RunManager
from pybar.scans.test_register import RegisterTest


def send_commands(self, commands, repeat=1, wait_for_finish=True, concatenate=True, byte_padding=False, clear_memory=False):
    commands.extend(self.register.get_commands("zeros", length=20))  # append some zeros since simulation is more slow
    if concatenate:
        commands_iter = iter(commands)
        try:
            concatenated_cmd = commands_iter.next()
        except StopIteration:
            pass
        else:
            for command in commands_iter:
                concatenated_cmd_tmp = self.concatenate_commands((concatenated_cmd, command), byte_padding=byte_padding)
                if concatenated_cmd_tmp.length() > self.command_memory_byte_size * 8:
                    self.send_command(command=concatenated_cmd, repeat=repeat, wait_for_finish=wait_for_finish, set_length=True, clear_memory=clear_memory)
                    concatenated_cmd = command
                else:
                    concatenated_cmd = concatenated_cmd_tmp
            # send remaining commands
            self.send_command(command=concatenated_cmd, repeat=repeat, wait_for_finish=wait_for_finish, set_length=True, clear_memory=clear_memory)
    else:
        max_length = 0
        if repeat:
            self.dut['cmd']['CMD_REPEAT'] = repeat
        for command in commands:
            max_length = max(command.length(), max_length)
            self.send_command(command=command, repeat=None, wait_for_finish=wait_for_finish, set_length=True, clear_memory=False)
        if clear_memory:
            self.clear_command_memory(length=max_length)


class TestInterface(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        subprocess.call('unzip -o test_interface/sim_build.zip', shell=True)
        subprocess.Popen(['make', '-f', '../firmware/mio/cosim/Makefile', 'sim_only'])
        time.sleep(10)  # some time for simulator to start

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree('test_interface/module_test', ignore_errors=True)

    @mock.patch('pybar.fei4.register_utils.FEI4RegisterUtils.configure_pixel', side_effect=lambda *args, **kwargs: None)  # do not configure pixel registers to safe time
    @mock.patch('pybar.fei4.register_utils.FEI4RegisterUtils.send_commands', autospec=True, side_effect=lambda *args, **kwargs: send_commands(*args, **kwargs))  # do not configure pixel registers to safe time
    def test_global_register(self, mock_configure_pixel, mock_send_commands):
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
