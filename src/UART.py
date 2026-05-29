import json
import os

import serial
import serial.rs485
import serial.tools.list_ports
import time
import sys
import glob

'''
UART Master class for serial communication
Baudrate: 9600
Data bits: 8
Parity: None
Stop bits: 1
'''
class UARTMaster:
    def __init__(self, port='COM3', baudrate=9600, timeout=1, use_rs485=False, device_address=1):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        self.use_rs485 = use_rs485
        self.address = device_address  # Store the target device address
        self.oven_connected = False
        self.autodetect_oven_port()  # Attempt to auto-detect the oven port on initialization

    def CreateDeviceInfoList(self):
        pass

    def GetDeviceInfoList(self):
        pass

    #Opens the serial port
    def Open(self):
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout
            )
            if self.use_rs485:
                # This tells the driver to toggle RTS high while sending
                # need a hardware adapter with "Automatic Send Data Control".
                rs485_conf = serial.rs485.RS485Settings(
                    rts_level_for_tx=True, 
                    rts_level_for_rx=False,
                    loopback=False,
                    delay_before_tx=None,
                    delay_before_rx=None,
                )
                self.ser.rs485_mode = rs485_conf
            self.oven_connected = True
        except serial.SerialException as e:
            print(f"Error opening serial port: {e}")
            self.ser = None
            self.oven_connected = False

    def Close(self):
        if self.ser:
            self.ser.close()

    def Purge(self):
        if self.ser:
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

    def Write(self, cmd):
        if self.ser and self.ser.is_open:
            full_command = f"{cmd}\r\n"
            self.ser.write(full_command.encode('ascii'))
        else:
            print("Error: Port not open")

    def Read(self):
        if self.ser and self.ser.is_open:
            # Read until newline
            return self.ser.readline().decode('ascii').strip()
        return None
    
    def autodetect_oven_port(self):
        print("\n[*] Loading Hardware Configuration for Oven...")
        
        # 1. Path Management
        script_dir = os.path.dirname(os.path.abspath(__file__)) 
        project_root = os.path.dirname(script_dir)              
        config_path = os.path.join(project_root, 'config', 'hardware_config.json')
        
        # 2. Load the JSON
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
                target_serial = config["oven_ftdi_serial"]
        except FileNotFoundError:
            print(f"[!] FATAL: {config_path} not found!")
            self.port = None
            return

        # 3. Scan the hardware
        available_ports = serial.tools.list_ports.comports()
        for port_info in available_ports:
            if port_info.serial_number == target_serial:
                print(f"[*] SUCCESS: Oven dynamically found on {port_info.device}")
                self.port = port_info.device
                return
                
        print("[!] Could not find the mapped Oven cable. Is it plugged in?")
        self.port = None
        
