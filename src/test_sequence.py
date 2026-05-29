import json
import msvcrt
import os

from Drive import Drive
from ESPEC import SH241
from Logger import Transfer_logger
from Logger import TCC_logger
from Logger import Temperature_logger
from diag_terminal import Terminal
from NI import NI
import serial
import serial.tools.list_ports
import threading
import time
import sys

from datetime import datetime

BAUD_RATE = 38400

class test_sequence():
    '''
    Class to run test sequence for sequential and random read/write
    '''
    def __init__(self, blocksize):
        self.lock = threading.Lock()
        
        # 1. Ask Windows for the SATA drive info
        try:
            time.sleep(0.1)
            self.drive = Drive(blockSize=blocksize)
        except Exception as e:
            print(f"[!] Drive not found error: {e}")
            sys.exit(1)
            
        print("[*] Waiting 2 seconds for Seagate processor to stabilize...")
        time.sleep(2.0)
        
        # 2. Run the serial detector
        self.port = self.autodetect_drive_port()
        
        # 3. Stop if port not found
        if self.port is None:
            print("\n[!] FATAL: Cannot find Seagate COM port.")
            print("[!] 1. Unplug drive power for 5 seconds.")
            print("[!] 2. Unplug USB cable and plug back in.")
            print("[!] 3. Power on drive, wait to spin up, and try again.")
            sys.exit(1) # <--- THIS KILLS THE SCRIPT SO IT DOESN'T CRASH LATER
            
        try:
            #4. Stealth opening of serial port
            self.ser = serial.Serial()
            self.ser.port = self.port
            self.ser.baudrate = 38400
            self.ser.bytesize = serial.EIGHTBITS
            self.ser.parity = serial.PARITY_NONE
            self.ser.stopbits = serial.STOPBITS_ONE
            self.ser.timeout = 0.1
            self.ser.dtr = False
            self.ser.rts = False
            
            self.ser.open()
            print("[*] Serial connection successfully initialised.")
            time.sleep(1) # Give time for oven to react
            
        except Exception as e: 
            print(f"[!] Terminal initialisation failed with exception: {e}")
            sys.exit(1)
            
        try:
            self.oven = SH241()
            time.sleep(1)
        except Exception as e:
            print(f"Oven not detected with exception {e}")

        self.thermocouple = NI(logger=Temperature_logger())
        self.is_running = True
        self.Tlogger = TCC_logger() 
        self.Slogger = Transfer_logger()


    def autodetect_drive_port(self):
        print("\n[*] Loading Hardware Configuration...")
        
        # 1. Path Management
        script_dir = os.path.dirname(os.path.abspath(__file__)) # Currently in /src
        project_root = os.path.dirname(script_dir)              # Backs up to root
        config_path = os.path.join(project_root, 'config', 'hardware_config.json')
        
        # 2. Load the JSON
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
                target_serial = config["drive_ftdi_serial"]
        except FileNotFoundError:
            print(f"[!] FATAL: {config_path} not found!")
            print("[!] Please run setup_hardware.py to map your cables.")
            return None

        # 3. Scan the hardware
        available_ports = serial.tools.list_ports.comports()
        for port_info in available_ports:
            if port_info.serial_number == target_serial:
                print(f"[*] SUCCESS: Seagate Drive dynamically found on {port_info.device}")
                return port_info.device
                
        print("[!] Could not find the mapped Seagate cable. Is it plugged in?")
        return None
    
    # Sets online mode for drive 
    def drive_s_set_online(self):
        try:
            with self.lock:
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                print("Sending Online Command (Ctrl+R)...")
                self.ser.write(b'\x12') # Send Ctrl+R

        except Exception as e:
            print(f"Serial transmission failed: {e}")

    def readFromUART(self):
        try:
            # log_buffer tracks the log status for the file
            log_buffer = ""
            has_user_input = False
            
            # NEW: This flag remembers if the cursor is at the start of a fresh line
            cursor_at_new_line = True 

            while self.is_running:
                with self.lock:
                    if self.ser.in_waiting:
                        raw_data = self.ser.read(self.ser.in_waiting)
                        line = raw_data.decode("ascii", errors="ignore").replace('\r', '')

                        # Display logic
                        display_str = ""
                        for char in line:
                            # If we are at the start of a line, and the char isn't just an empty newline, inject timestamp
                            if cursor_at_new_line and char != '\n':
                                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-4]
                                display_str += f"{timestamp} "
                                cursor_at_new_line = False
                            
                            display_str += char
                            
                            # If we hit a newline, prime the flag for the next character that arrives
                            if char == '\n':
                                cursor_at_new_line = True

                        # Print output
                        sys.stdout.write(display_str)
                        sys.stdout.flush()

                        # Logger logic
                        log_buffer += line
                        while '\n' in log_buffer:
                            complete_line, log_buffer = log_buffer.split('\n', 1)
                            clean_line = complete_line.strip() 
                            if clean_line and clean_line.__contains__("TCC"): 
                                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-4]
                                self.Tlogger.info(f"|{timestamp}|{clean_line}")
                                
                time.sleep(0.02)

        except Exception as e:
            print(e)
        

    
        
if __name__ == "__main__":
    # Initialise test sequence with blocksize
    test = test_sequence(blocksize=65536)

    # Set up drive serial port for TCC log and online mode
    threading.Thread(target=test.readFromUART, daemon=True).start()
    test.drive_s_set_online()

    # Add thermocouple channels, can add additional ones if you like
    test.thermocouple.add_channel(channel_num=10, thermo_type_string="K")
    test.thermocouple.add_channel(channel_num=11, thermo_type_string="K")

    # Set up oven and taasks
    test.oven.OpenChannel()
    test.oven.AddTask(temp=33,minutes=70)
    test.oven.startTask()

    # Sleep until oven reaches specified temperature
    while (test.oven.state != "SOAKING"):
        time.sleep(1)

    # Start recording thermocouple temperature every 10 seconds
    test.thermocouple.read_and_log_loop(10)

    # Perform the drive operation (sequentialWrite / sequentialRead / randomWrite / randomRead)
    threading.Thread(target=test.drive.randomWrite, kwargs={"min": 70, "logger": test.Slogger}, daemon=True).start()
    
    # Only need to modify function after drive. (example below)
    # threading.Thread(target=test.drive.sequentialWrite, kwargs={"min": 70, "logger": test.Slogger}, daemon=True).start()
    
    # Sleep thread so that program does not exit
    while True:
        time.sleep(10)

