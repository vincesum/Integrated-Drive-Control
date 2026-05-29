from datetime import datetime
import time
import nidaqmx
from nidaqmx.constants import ThermocoupleType, TemperatureUnits
import threading
from Logger import Temperature_logger

"""
Run setup.py if not set up yet to lock the serial port IDs to the hardware
"""

thermotype_map = {
    "K": ThermocoupleType.K,
    "T": ThermocoupleType.T,
    "J": ThermocoupleType.J
}


class NI():
    """
    National Instruments NI cDAQ-9274 NI 9213 Thermocouple Class
    
    Parameters:
    task - The task being run using the nidaqmx library
    active_channels - Array containing the channels that are used for the test
    logger - logger that is being used to log the thermocouple temperatures
    
    """
    def __init__(self, logger=None):
        """ Initialises the NI class for thermocouple readings"""
        self.task = nidaqmx.Task()
        self.active_channels = []
        self.logger = logger

    def read_temperature(self):
        """Returns the temperature of every thermocouple channel set up in dictionary form"""
        temperature_data = self.task.read()
        print(f"Current temperature: {temperature_data}")
        if not isinstance(temperature_data, list):
            temperature_data = [temperature_data]
        
        mapped_data = dict(zip(self.active_channels, temperature_data))
        
        return mapped_data

    def add_channel(self, channel_num, thermo_type_string):
        """
        Adds a channel to be recorded
        
        kwargs:
        channel_num - The channel number that is used
        thermo_type_string - The type of thermocouple used
        """
        try:
            self.task.ai_channels.add_ai_thrmcpl_chan(
                physical_channel=f"cDAQ1Mod2/ai{channel_num}",
                name_to_assign_to_channel=f"{channel_num}",
                thermocouple_type=thermotype_map[thermo_type_string.upper()],  # Change to J, T, K based on wire
                units=TemperatureUnits.DEG_C
            )
            self.active_channels.append(channel_num)
        except Exception as e:
            print(f"Error adding channel: {e}")

    # Close the connection when done
    def close(self):
        self.task.close()
        print("Hardware connection closed safely.")

    def read_and_log(self):
        data = self.read_temperature()
        logText = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-4] + '\n'
        if not self.logger == None:
            self.logger.record(data)

    def read_and_log_loop(self, interval_in_s):
        try:
            timer = RepeatTimer(interval_in_s, self.read_and_log)
            timer.start()
        except Exception as e:
            print(f"NI Error: {e}")

class RepeatTimer(threading.Timer):
    def run(self):
        next_target_time = time.time() + self.interval
        while not self.finished.is_set():
            sleep_duration = next_target_time - time.time()
            if sleep_duration > 0:
                if self.finished.wait(sleep_duration):
                    break
            self.function(*self.args, **self.kwargs)
            next_target_time += self.interval

if __name__ == "__main__":
    ni = NI(logger=Temperature_logger())
    try:
        ni.add_channel(channel_num=12, thermo_type_string="K")
        ni.add_channel(channel_num=11, thermo_type_string="K")
        ni.read_and_log_loop(10)

        print("Press Ctrl+C to stop logging and exit.")
        while True:
            time.sleep(1)
    except Exception as e:
        print(f"An error occurred during measurement: {e}")
    #finally:
        # This guarantees the hardware is released even if the read fails!
        #ni.close()