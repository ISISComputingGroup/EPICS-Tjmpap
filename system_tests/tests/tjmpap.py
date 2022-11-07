import unittest
import os

from parameterized import parameterized

from utils.channel_access import ChannelAccess
from utils.ioc_launcher import get_default_ioc_dir, IOCRegister, ProcServLauncher, EPICS_TOP
from utils.test_modes import TestModes
from utils.testing import get_running_lewis_and_ioc, skip_if_recsim, parameterized_list


EUROTHERM_PREFIX = "EUROTHRM_01"
EUROTHERM_ADDRESS = "A01"
JULABO_PREFIX = "JULABO_01"
TJMPER_PREFIX = "TJMPER_01"
DEVICE_PREFIX = "TJMPAP_01"


CALIBRATION_FOLDER = "tjmpap/master/calibrations"
CALIBRATION_BASE_DIR = "C:/Instrument/Apps/EPICS/support"
MACROS = [
    ({
        "CALIBRATION_FILE" : "1x1.txt",
        "CALIBRATION_FOLDER" : CALIBRATION_FOLDER,
        "CALIBRATION_BASE_DIR" : CALIBRATION_BASE_DIR
    }, 1.0),
    ({
        "CALIBRATION_FILE" : "1x2.txt",
        "CALIBRATION_FOLDER" : CALIBRATION_FOLDER,
        "CALIBRATION_BASE_DIR" : CALIBRATION_BASE_DIR
    }, 2.0)
]


IOCS = [
    {
        "name": EUROTHERM_PREFIX,
        "directory": get_default_ioc_dir("EUROTHRM"),
        "ioc_launcher_class": ProcServLauncher,
        "macros": {
            "ADDR": EUROTHERM_ADDRESS,
            "ADDR_1": 1,
            "ADDR_2": "",
            "ADDR_3": "",
            "ADDR_4": "",
            "ADDR_5": "",
            "ADDR_6": "",
            "ADDR_7": "",
            "ADDR_8": "",
            "ADDR_9": "",
            "ADDR_10": ""
        },
        "emulator": "eurotherm",
        "lewis_additional_path": os.path.join(EPICS_TOP, "support", "DeviceEmulator", "master"),
    },
    {
        "name": JULABO_PREFIX,
        "directory": get_default_ioc_dir("JULABO"),
        "macros": {},
        "emulator": "julabo",
        "lewis_protocol": "julabo-version-1",
        "lewis_additional_path": os.path.join(EPICS_TOP, "support", "DeviceEmulator", "master"),
    },
    {
        "name": TJMPER_PREFIX,
        "directory": get_default_ioc_dir("TJMPER"),
        "macros": {},
        "emulator": "Tjmper",
        "lewis_additional_path": os.path.join(EPICS_TOP, "support", "tjmper", "master", "system_tests"),
    },
    {
        "name": DEVICE_PREFIX,
        "directory": get_default_ioc_dir("TJMPAP"),
        "ioc_launcher_class": ProcServLauncher,
        "macros": MACROS[0][0]
    },
]


TEST_MODES = [TestModes.DEVSIM]


MODES = [
    ("All out",                 ["True", "False", "True", "False", "True", "False"]),
    ("PLT1 and SMPL engaged",   ["False", "True", "True", "False", "False", "True"]),
    ("PLT2 and SMPL engaged",   ["True", "False", "False", "True", "False", "True"])
]


class TjmpapTests(unittest.TestCase):
    """
    Tests for the Tjmpap IOC.
    """
    def setUp(self):
        self._ioc = IOCRegister.get_running(DEVICE_PREFIX)
        self.assertIsNotNone(self._ioc)
        self.ca = ChannelAccess(device_prefix=DEVICE_PREFIX, default_wait_time=0)

        self._lewis_tjmper, self._ioc_tjmper = get_running_lewis_and_ioc("Tjmper", TJMPER_PREFIX)
        self.ca_tjmper = ChannelAccess(device_prefix=TJMPER_PREFIX, default_wait_time=0)
        self.ca_tjmper.assert_that_pv_exists("ID", timeout=10)

        self._lewis_euro, self._ioc_euro = get_running_lewis_and_ioc("eurotherm", EUROTHERM_PREFIX)
        self.ca_euro = ChannelAccess(device_prefix=f"{EUROTHERM_PREFIX}:{EUROTHERM_ADDRESS}")
        self.ca_euro.assert_that_pv_exists("CAL:SEL", timeout=10)
        self._lewis_euro.backdoor_set_on_device("address", "A01")

        self._lewis_julabo, self._ioc_julabo = get_running_lewis_and_ioc("julabo", JULABO_PREFIX)
        self.ca_julabo = ChannelAccess(device_prefix=JULABO_PREFIX)
        self.ca_julabo.assert_that_pv_exists("TEMP", timeout=30)        

    def test_WHEN_controllers_connected_THEN_controller_names_correct(self):
        self.ca.assert_that_pv_is("PLATE1:CONTROLLER", f"{EUROTHERM_PREFIX}:{EUROTHERM_ADDRESS}")
        self.ca.assert_that_pv_is("PLATE2:CONTROLLER", JULABO_PREFIX)
        self.ca.assert_that_pv_is("SAMPLE:READBACK", f"{EUROTHERM_PREFIX}:{EUROTHERM_ADDRESS}")

    @parameterized.expand(parameterized_list(MACROS))
    def test_WHEN_temperature_set_on_block_1_THEN_temperature_updates_on_controller(self, _, macros, multiplier):
        with self._ioc.start_with_macros(macros, "JMP:MODE"):
            self.ca.set_pv_value("PLATE1:TEMP:SP", 5.0)
            self.ca_euro.assert_that_pv_is("TEMP:SP:RBV", 5.0 / multiplier)
            self._lewis_euro.assert_that_emulator_value_is("ramp_setpoint_temperature", str(5.0 / multiplier))

            self._lewis_euro.backdoor_set_on_device("current_temperature", 6.0)
            self.ca.assert_that_pv_is_number("PLATE1:TEMP", 6.0 * multiplier, tolerance=0.01)

    @parameterized.expand(parameterized_list(MACROS))
    def test_WHEN_temperature_set_on_block_2_THEN_temperature_updates_on_controller(self, _, macros, multiplier):
        with self._ioc.start_with_macros(macros, "JMP:MODE"):
            self.ca.set_pv_value("PLATE2:TEMP:SP", 10.0)
            self.ca_julabo.assert_that_pv_is("TEMP:SP:RBV", 10.0 / multiplier)
            self._lewis_julabo.assert_that_emulator_value_is("set_point_temperature", str(10.0 / multiplier))

            self._lewis_julabo.backdoor_set_on_device("temperature", 11.0)
            self.ca.assert_that_pv_is_number("PLATE2:TEMP", 11.0 * multiplier, tolerance=0.01)

    def test_WHEN_temperature_set_on_readback_controller_via_backdoor_THEN_temperature_updates_correctly(self):
        self._lewis_euro.backdoor_set_on_device("current_temperature", 33.0)
        self.ca.assert_that_pv_is_number("SAMPLE:TEMP", 33.0, tolerance=0.01)

    @parameterized.expand(parameterized_list(MODES))
    def test_WHEN_position_moved_THEN_position_updates_correctly(self, _, mode, states):
        self.ca.set_pv_value("JMP:MODE:SP", mode)
        self.ca.assert_that_pv_is("JMP:MODE", mode)
        self.ca_tjmper.assert_that_pv_is("MODE", mode)

        self.ca.assert_that_pv_is("PLATE1:HOME", states[0])
        self.ca.assert_that_pv_is("PLATE1:ENGAGED", states[1])
        self.ca.assert_that_pv_is("PLATE2:HOME", states[2])
        self.ca.assert_that_pv_is("PLATE2:ENGAGED", states[3])
        self.ca.assert_that_pv_is("SAMPLE:HOME", states[4])
        self.ca.assert_that_pv_is("SAMPLE:ENGAGED", states[5])

        self.ca_tjmper.assert_that_pv_is("LMT:PLATE1:HOME", states[0])
        self.ca_tjmper.assert_that_pv_is("LMT:PLATE1:ENGAGED", states[1])
        self.ca_tjmper.assert_that_pv_is("LMT:PLATE2:HOME", states[2])
        self.ca_tjmper.assert_that_pv_is("LMT:PLATE2:ENGAGED", states[3])
        self.ca_tjmper.assert_that_pv_is("LMT:SAMPLE:HOME", states[4])
        self.ca_tjmper.assert_that_pv_is("LMT:SAMPLE:ENGAGED", states[5])
