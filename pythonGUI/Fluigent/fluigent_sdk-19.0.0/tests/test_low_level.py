# -*- coding: utf-8 -*-
"""
Test the functions in the low_level module of the SDK. Required Fluigent 
instruments to be connected to the computer
"""

import time
import unittest 
from Fluigent.SDK import low_level

class TestInfoFunctions(unittest.TestCase):
    """Test the FGT SDK functions that return informations about the connected
    instruments"""

    @classmethod
    def setUpClass(self):
        """Initialize the DLL engine"""
        low_level.fgt_init()
        
    @classmethod   
    def tearDownClass(self):
        """Stop the DLL engine"""
        low_level.fgt_close()
        
    def test_fgt_get_controllersInfo(self):
        c_error, channels = low_level.fgt_get_controllersInfo()
        self.assertEqual(c_error, low_level.fgt_ERROR.OK)
        for channel in channels:
            self.assertGreater(channel.SN, 0) 
    
    def test_fgt_get_pressureChannelCount(self):
        c_error, count = low_level.fgt_get_pressureChannelCount()
        self.assertEqual(c_error, low_level.fgt_ERROR.OK)
        self.assertGreater(count, 0)
        
    def test_fgt_get_flowrateChannelCount(self):
        c_error, count = low_level.fgt_get_sensorChannelCount()
        self.assertEqual(c_error, low_level.fgt_ERROR.OK)
        self.assertGreater(count, 0)
        
    def test_fgt_get_TTLChannelCount(self):
        c_error, count = low_level.fgt_get_TtlChannelCount()
        self.assertEqual(c_error, low_level.fgt_ERROR.OK)
        self.assertGreater(count, 0)
        
    def test_fgt_get_pressureChannelsInfo(self):
        c_error, channels = low_level.fgt_get_pressureChannelsInfo()
        self.assertEqual(c_error, low_level.fgt_ERROR.OK)
        for channel in channels:
            self.assertGreater(channel.ControllerSN, 0)        
        
    def test_fgt_get_sensorChannelsInfo(self):
        c_error, channels, sensor_types = low_level.fgt_get_sensorChannelsInfo()
        self.assertEqual(c_error, low_level.fgt_ERROR.OK)
        for channel in channels:
            self.assertGreater(channel.ControllerSN, 0) 
        for sensor_type in sensor_types:
            self.assertNotEqual(sensor_type, low_level.fgt_INSTRUMENT_TYPE.NONE) 

    def test_fgt_get_TTLChannelsInfo(self):
        c_error, channels = low_level.fgt_get_TtlChannelsInfo()
        self.assertEqual(c_error, low_level.fgt_ERROR.OK)
        for channel in channels:
            self.assertGreater(channel.ControllerSN, 0)  
            
class TestPressure(unittest.TestCase):
    """Test the functions that control pressure channels"""
    @classmethod
    def setUpClass(self):
        """Initialize the DLL engine"""
        low_level.fgt_init()
        c_error, self.n_channels = low_level.fgt_get_pressureChannelCount()
        
    @classmethod   
    def tearDownClass(self):
        """Stop the DLL engine"""
        low_level.fgt_close()
        
    def tearDown(self):
        """Reset the pressures after every test"""
        for channel in range(self.n_channels):
            low_level.fgt_set_pressure(channel, 0)
        
    def test_fgt_set_pressure(self):
        setpoints = []
        for channel in range(self.n_channels):
            c_error, min_pressure, max_pressure = low_level.fgt_get_pressureRange(channel)
            self.assertEqual(c_error, low_level.fgt_ERROR.OK)
            setpoint = (min_pressure + max_pressure)/2
            c_error = low_level.fgt_set_pressure(channel, setpoint)
            setpoints.append(setpoint)
            
        if(self.n_channels > 0): time.sleep(3)
        for channel in range(self.n_channels):
            c_error, pressure = low_level.fgt_get_pressure(channel)
            rel_error = abs(setpoints[channel] - pressure)/abs(setpoints[channel])
            # Check that the pressure 
            self.assertLess(rel_error, 0.02)
            
class TestStructures(unittest.TestCase):
    """Test the structure classes that are returned by the info functions"""
        
    def test_fgt_CHANNEL_INFO_getitem(self):
        struct = low_level.fgt_CHANNEL_INFO()
        print(struct)
        self.assertEqual(struct.ControllerSN, struct["ControllerSN"])
        self.assertEqual(struct.firmware, struct["firmware"])
        self.assertEqual(struct.DeviceSN, struct["DeviceSN"])
        self.assertEqual(struct.position, struct["position"])
        self.assertEqual(struct.index, struct["index"])
        self.assertEqual(struct.indexID, struct["indexID"])
        self.assertEqual(struct.type, struct["type"])
        
    def test_fgt_CONTROLLER_INFO_getitem(self):
        struct = low_level.fgt_CONTROLLER_INFO()
        print(struct)
        self.assertEqual(struct.SN, struct["SN"])
        self.assertEqual(struct.Firmware, struct["Firmware"])
        self.assertEqual(struct.id, struct["id"])
        self.assertEqual(struct.type, struct["type"])
        

if __name__ == '__main__':
    unittest.main()