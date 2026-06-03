# Integrated Hardware Testing Suite: User Guide

## Overview
This automated test sequence script orchestrates simultaneous control and logging of a hard disk drive, an ESPEC temperature chamber, and National Instruments (NI) data acquisition hardware. It is designed to run continuous drive I/O operations (Sequential/Random Read and Write) while syncing environmental temperature changes and logging real-time thermal telemetry. 

The script utilizes multi-threading to ensure that UART diagnostic logging, drive I/O operations, and thermocouple polling occur simultaneously without blocking one another.

## Hardware & System Requirements
* **Operating System:** Windows (Must run terminal as **Administrator** for raw physical disk access).
* **Storage Device:** Seagate SATA Hard Drive connected to the host machine via USB-to-SATA cable and USB serial port.
* **Serial Diagnostic Cable:** FTDI serial cable connected to the drive's diagnostic pins.
* **Temperature Chamber:** ESPEC SH241/641 connected to host via FTDI serial port.
* **DAQ Hardware:** National Instruments chassis and thermocouple module NI 9213 with Type-K thermocouples.

## 1. Initial Setup & Configuration
Before running the script, the serial diagnostic cable must be mapped so the script can dynamically locate the correct COM port.

1. Navigate to the project's `setup.py` file.
2. Run it and follow its instructions to setup configurations to bind the IDs of the hard drive and chamber.

## 2. Modifying the Test Sequence
The test parameters are defined at the very bottom of the script inside the `if __name__ == "__main__":` execution block. You must edit these lines to match your specific laboratory test requirements before executing the script.

### Step A: Configuring the Thermocouples
To add or remove NI thermocouple channels, modify the `add_channel` lines. Ensure the `thermo_type_string` matches your physical wire type (e.g., "K", "J", "T").
```python
test.thermocouple.add_channel(channel_num=10, thermo_type_string="K")
test.thermocouple.add_channel(channel_num=11, thermo_type_string="K")
```

### Step B: Configuring the Temperature Chamber
Open the channel to the chamber to connect to the temperature chamber.
```python
test.oven.OpenChannel()
```

Set your target environmental temperature (in Celsius) and the duration of the thermal test (in minutes). 

```python
test.oven.AddTask(temp=33, minutes=70)
```
*Note: The script is programmed toonly start drive operations when the chamber physically reaches this target temperature and enters the "SOAKING" state.*

Then, start the task to start ramping the temperature of the chamber to target temperature.

```python
test.oven.startTask()
```

**Check if temperature has been reached**

Drive only runs after set temperature is reached. Hence, the chamber should be in soaking mode when drive operation starts. This conditional pings for oven soaking status before proceeding with the rest of the script.
```python
while (test.oven.state != "SOAKING"):
    time.sleep(1)
```

### Step C: Configuring the Drive Operation
Select the specific drive operation to stress-test the hardware. The target method is passed into the threading mechanism. Update the `kwargs` to set the duration (e.g., `min`, `hour`, `sec`).

**Start Logging and Set Online Mode**
```python
threading.Thread(target=test.readFromUART, daemon=True).start()
test.drive_s_set_online()
```

**For Sequential Read:**
```python
threading.Thread(target=test.drive.sequentialRead, kwargs={"min": 70, "logger": test.Slogger}, daemon=True).start()
```

**For Sequential Write:**
```python
threading.Thread(target=test.drive.sequentialWrite, kwargs={"min": 70, "logger": test.Slogger}, daemon=True).start()
```

**For Random Read/Write:**
Change the `target` parameter to `test.drive.randomRead` or `test.drive.randomWrite`.

## 3. Running the Test
Once your parameters are set, execute the script from an elevated command prompt:

```bash
python test_sequence.py
```

### Execution Flow
1. **Hardware Handshake:** The script will verify the SATA connection and dynamically locate the UART diagnostic port.
2. **Online Mode:** It will send `Ctrl+R` (`\x12`) over the serial connection to put the drive into online mode.
3. **Chamber Ramp-Up/Down:** The ESPEC chamber will engage and heat/cool to the target temperature. Terminal output will pause here until the "SOAKING" state is achieved.
4. **Testing Commences:** Once at temperature, the NI thermocouple logger starts polling every 10 seconds, and the high-speed drive thread initiates.

## 4. Log Files & Data Output
The script automatically generates three distinct data streams. Logs file can be found under the `logs/` directory for the output. Each individual logs file is named with the corresponding timestamp attached to them.
* **Drive Transfer Logs (`Transfer_logger`):** Records the precise transfer rate metris in MB/s in CSV-format for the reads and writes.
* **Temperature Logs (`Temperature_logger`):** A CSV-formatted output of the NI thermocouple channels, tracking ambient and component-level heat.
* **TCC Logs (`TCC_logger`):** The UART read thread constantly filters the serial stream for lines containing the string `"TCC"`. These lines are stamped with the host machine's timestamp and saved to the TCC log file.