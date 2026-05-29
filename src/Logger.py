import logging
import csv
import os
from datetime import datetime

Units = {
    0: "",
    3: "K",
    6: "M",
    9: "G",
    12: "T",
}

"""
Logger base class
Creates a logs directory where the logs would be stored
@params: None
"""
class Logger():
    def __init__(self):
        # LOGGER SETUP
        # Find absolute path of script
        script_dir = os.path.dirname(os.path.abspath(__file__))

        # Finds source directory which script resides in
        project_root = os.path.dirname(script_dir)

        # Finds the log directory which can be called
        self.log_dir = os.path.join(project_root, 'logs')

        # Makes the log directory if it does not exist, ignore if it exists
        os.makedirs(self.log_dir, exist_ok=True)

        # Creates timestamp for current log
        self.timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

        
"""
Logger class that tracks transfer speed data
Stores data into CSV format 

"""
class Transfer_logger(Logger):
    def __init__(self):
        super().__init__()
        # Logger setup
        # Create a unique name of log based on timestamp
        log_file_name = f"transfer_log_{self.timestamp}.csv"

        # Retrieves the final path of the log
        self.path = os.path.join(self.log_dir, log_file_name)

        # Final set up of the logger

        # self.logger = logging.getLogger(__name__)
        # logging.basicConfig(format='%(message)s', filename=path, encoding='utf-8', level=logging.DEBUG)

        # Initialises the log file and closes it
        open(self.path,"w").close()

        # Initialise variables
        self.recordCount = 0
        self.totalbytes = 0

    def record(self, isWriting, bytes):
        self.recordCount += 1
        self.totalbytes += bytes
        if (self.recordCount >= 30):
            bytes_per_sec = self.totalbytes / self.recordCount
            avg_speed = self.convertUnits(bytes_per_sec)[:-2]
            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

            with open(self.path, "a", newline='') as f:
                writer = csv.writer(f)
            
                if isWriting:
                    # row format: [Column 1, Column 2, Column 3]
                    writer.writerow([timestamp, "Write", avg_speed])
                else:
                    writer.writerow([timestamp, "Read", avg_speed]) 

            self.recordCount = 0
            self.totalbytes = 0
    
    def convertUnits(self, totalBytes):
        powers_of_ten = 0
        while (totalBytes > 1000):
            totalBytes /= 1000
            powers_of_ten += 3
        return f"{totalBytes:.2f}{Units[powers_of_ten]}B"
    
class TCC_logger(Logger):
    def __init__(self):
        super().__init__()
        
        log_file_name = f"TCC_log_{self.timestamp}.log"
        self.path = os.path.join(self.log_dir, log_file_name)

        self.logger = logging.getLogger("TCC_Diagnostics")
        self.logger.setLevel(logging.DEBUG)

        self.logger.propagate = False 

        # Create a FileHandler to route this specific logger to your file
        if not self.logger.handlers: # Prevents adding duplicates when restarting the test
            file_handler = logging.FileHandler(self.path, encoding='utf-8')
            formatter = logging.Formatter('%(message)s')
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    # Add the wrapper method
    def info(self, message):
        self.logger.info(message)

class Temperature_logger(Logger):
    def __init__(self):
        super().__init__()
        
        log_file_name = f"temperature_log_{self.timestamp}.csv"
        self.path = os.path.join(self.log_dir, log_file_name)
        
        # Flag to know if we need to write the CSV headers
        self.header_written = False

        # Create empty file
        open(self.path,"w").close()

    def record(self, channel_info):
        """
        Takes the mapped_data dictionary, formats it into CSV, and appends it.
        """
        # 1. Generate the timestamp for this specific reading
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-4]

        # 2. Sort the keys to guarantee column order (e.g., Channel 0, Channel 1)
        sorted_channels = sorted(channel_info.keys())

        # 3. Write the Header Row if this is the very first reading
        if not self.header_written:
            headers = ["Timestamp"] + [f"Channel_{ch}" for ch in sorted_channels]
            with open(self.path, "a") as f:
                f.write(",".join(headers) + "\n")
            self.header_written = True

        # 4. Extract the temperature values in that exact same sorted order
        values = [str(channel_info[ch]) for ch in sorted_channels]

        # 5. Flatten into a single CSV row and append to the file
        csv_row = f"{current_time}," + ",".join(values) + "\n"
        
        with open(self.path, "a") as f:
            f.write(csv_row)
