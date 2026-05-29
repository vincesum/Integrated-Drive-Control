import json

import serial
import serial.tools.list_ports
import threading
import sys
import msvcrt
import time
from datetime import datetime
import logging
import os
#38400
#log all characters including newlines and carriage return, dont remove newlines and CECECECE
#Get binary from drive then decode into ASCII
SERIAL_PORT = "COM4" # Can be adjusted base on port
BAUD_RATE = 38400 # Standard baudrate for Seagate Drives
class Terminal():
    def __init__(self, baudrate):
        """
        Initiates a CLI terminal program that interfaces with the serial port of the Seagate Hard Disk Drive
        Logs the output with timestamps from the drive into a log file inside the logs directory
        
        @params:
        baudrate: The baudrate used by the serial port of the drive
        """
        # Initialisation of variables
        self.baudrate = baudrate
        self.is_running = True

        # Locks for mutex are implemented to prevent race conditions when writing/reading
        self.lock = threading.Lock()
        self.ready_flag = threading.Event()
        self.ready_flag.set() #Set flag to enable typing initially

        # Autodetect port by sending a handshake signal (disconnect other devices with different baud rates)
        self.port = self.autodetect_drive_port()
        
        # Exit if port not found
        if self.port is None:
            print("\n[!] FATAL: Terminal cannot find Seagate Drive.")
            print("[!] 1. Unplug drive power for 5 seconds.")
            print("[!] 2. Unplug USB cable and plug back in.")
            print("[!] 3. Power on drive, wait to spin up, and try again.")
            sys.exit(1) # Kills the script instantly to prevent OS crashes

        # Logger setup
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        log_dir = os.path.join(project_root, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        log_file_name = f"drive_diagnostic_{timestamp}.log"
        path = os.path.join(log_dir, log_file_name)
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(format='%(message)s', filename=path, encoding='utf-8', level=logging.DEBUG)

        # Serial initialisation
        try:
            self.ser = serial.Serial()
            self.ser.port = self.port
            self.ser.baudrate = self.baudrate
            self.ser.bytesize = serial.EIGHTBITS
            self.ser.parity = serial.PARITY_NONE
            self.ser.stopbits = serial.STOPBITS_ONE
            self.ser.timeout = 0.1
            
            # Prevent voltage spike
            self.ser.dtr = False
            self.ser.rts = False
            
            self.ser.open()
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            print(f"\n[*] Terminal securely locked to {self.port} in Stealth Mode.")
            
        except Exception as e:
            print(f"[!] Terminal initialisation failed with exception: {e}")
            sys.exit(1)

    def autodetect_drive_port(self):
        """
        Function that autodetects the port used by referring to the config file setup in the setup.py file
        Returns the port used for the drive
        """
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


    def readFromUART(self):
        """
        Function that reads from drive serial port periodically every 0.1s
        Logging of the read out from drive is executed here as well
        """
        try:
            # log_buffer tracks the log status and only adds to log everytime a \n character is received
            log_buffer = ""
            cursor_at_new_line = True 

            #has_user_input tracks whether the user has inputted after F3 terminal is on screen
            has_user_input = False
            while self.is_running:

                # Acquires lock to prevent writing while reading
                with self.lock:

                    # Read non-empty input
                    if (self.ser.in_waiting):
                        raw_data = self.ser.read(self.ser.in_waiting)
                        line = raw_data.decode("ascii", errors="ignore").replace('\r', '')

                        # Display logic
                        display_str = ""
                        for char in line:
                            # If we are at the start of a line, and the char isn't just an empty newline, inject timestamp
                            if cursor_at_new_line and char != '\n':
                                timestamp = self.getDateTime()
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
                        log_buffer = log_buffer + line

                        # Split all newlines
                        while '\n' in log_buffer:
                            
                            # Split the buffer into two pieces at the FIRST newline it finds.
                            # Piece 1: The finished line. Piece 2: Whatever is left over (like the F3 T> prompt!)
                            complete_line, log_buffer = log_buffer.split('\n', 1)
                            
                            clean_line = complete_line.strip() # Removes all trailing or leading whitespaces
                            clean_line = self.logCleaner(clean_line) # Removes all bacckspace characters and handles them
                            if clean_line: # Log all lines that are not blank
                                timestamp = self.getDateTime()
                                self.logger.info(f"{timestamp}{clean_line}")

                        # If the drive spits out prompt, allow writing
                        if '>' in line or "(P)SATAReset" in line:
                            self.ready_flag.set()
                    time.sleep(0.02)


        except Exception as e:
            print(e)
    
    def writeToUART(self):
        """
        Function that writes to drive based on user input
        Function is able to capture ctrl commands as well as regular keyboard commands
        """
        wait_timer = 0.0  # Keep track of how long we wait
        try:
            while self.is_running:

                # THE BLOCKER WITH WATCHDOG
                if not self.ready_flag.wait(timeout=0.1):
                    wait_timer += 0.1

                # If stuck for 3 seconds, break the lock
                    if wait_timer >= 3.0:
                        self.ready_flag.set() # Force the light green
                        wait_timer = 0.0
                    continue

                wait_timer = 0.0

                # Gets raw user input data(to intercept microsoft OS ctrl commands)
                raw_user_input_byte = msvcrt.getch()
                
                # ESC KEY INTERCEPTOR
                if raw_user_input_byte == b'\x1b':
                    self.is_running = False
                    break

                # CTRL OPERATION INTERCEPTOR
                # Check if the byte is between Ctrl+A (\x01) and Ctrl+Z (\x1a)
                if b'\x01' <= raw_user_input_byte <= b'\x1a':
                    
                    with self.lock:
                        # Exclude Enter (\r), Backspace (\x08), Tab (\x09), and Line Feed (\n)
                        if raw_user_input_byte not in (b'\r', b'\n', b'\x08', b'\x09'):
                            
                            # Reverse-calculate the letter for logs
                            # Taking the raw byte, turning it into an integer and adding 64 
                            # shifts it back up the ASCII table to the capital letters.
                            letter_pressed = chr(ord(raw_user_input_byte) + 64)
                            
                            # Print timestamp and sent command
                            sys.stdout.write(f"\n{self.getDateTime()} [Sent Ctrl+{letter_pressed}]\n")
                            sys.stdout.flush()

                            # Clears the ready flag to prevent further writing
                            self.ready_flag.clear() 

                # Write all other keys apart from Ctrl operations
                with self.lock:
                    self.ser.write(raw_user_input_byte)
                    self.ser.flush()

        except Exception as e:
            print(e)
            


    def logCleaner(self, line):
        """
        Cleans the logs by removing backspaces and handles them to remove the corresponding characters
        """
        clean_line = []
        for char in line:
            if char == '\x08': # Char code for backspace
                if clean_line:
                    clean_line.pop() # Delete last char saved due to backspace
            else:
                clean_line.append(char) # Save the character if not backspace
        return ''.join(clean_line) #Combines the array to form the clean line without backspace


    def start(self):
        """
        Starts the program and creates 2 threads - one for reading, one for writing
        """
        reading_thread = threading.Thread(target=self.readFromUART, daemon=True)
        reading_thread.start()

        self.writeToUART()

        self.ser.close()
        print("[*] Serial connection closed.")


    def getDateTime(self):
        """
        Gets the datetime and returns timestamp
        """
        timestamp = datetime.now().strftime('|%Y-%m-%d %H:%M:%S.%f|')
        return timestamp

"""
Entry point of program
Only executes if executed directly
"""
if __name__ == "__main__":
    terminal = Terminal(BAUD_RATE)
    terminal.start()
