import serial.tools.list_ports
import json
import time
import os # <-- Added for path management

"""
Setup code to bind the FTDI chips for the drive and the ESPEC chamber
Run this setup whenever the cables used for the testing operation change
"""

def get_current_ftdi_serials():
    """
    Returns a set that contains all the serial numbers of the ports
    """
    ports = serial.tools.list_ports.comports()
    return {p.serial_number for p in ports if p.serial_number}

def run_calibration():
    """
    Main setup code to bind the FTDI chips for the drive and the chamber
    """
    print("=== TEST RIG HARDWARE CALIBRATOR ===")
    print("Please UNPLUG all USB-to-Serial cables from your laptop.")
    input("Press ENTER when all cables are unplugged...")
    
    baseline_serials = get_current_ftdi_serials()
    
    # ---------------------------------------------------------
    # 1. Map the Drive
    # ---------------------------------------------------------
    print("\n[*] Plug in ONLY the Seagate Drive USB cable and press ENTER.")
    print("    (Or type 'skip' and press ENTER to skip the drive)")
    user_input = input("> ").strip().lower()
    
    drive_serial_val = None # Safe default
    
    if user_input == 'skip':
        print("[-] Skipping Seagate Drive configuration.")
    else:
        time.sleep(2)
        current_serials = get_current_ftdi_serials()
        # Compare the new set against old set and check if any new ports appeared
        drive_serial = list(current_serials - baseline_serials)
        
        if drive_serial:
            drive_serial_val = drive_serial[0]
            print(f"[+] Drive Cable Locked! (Serial: {drive_serial_val})")
            baseline_serials.update(drive_serial) # Add to baseline so it doesn't confuse the oven scan
        else:
            print("[!] No new cable detected. Seagate Drive will remain unconfigured.")

    # ---------------------------------------------------------
    # 2. Map the Oven
    # ---------------------------------------------------------
    print("\n[*] Now plug in the ESPEC Oven USB cable and press ENTER.")
    print("    (Or type 'skip' and press ENTER to skip the oven)")
    user_input = input("> ").strip().lower()
    
    oven_serial_val = None # Safe default
    
    if user_input == 'skip':
        print("[-] Skipping ESPEC Oven configuration.")
    else:
        time.sleep(2)
        current_serials = get_current_ftdi_serials()
        oven_serial = list(current_serials - baseline_serials)
        
        if oven_serial:
            oven_serial_val = oven_serial[0]
            print(f"[+] Oven Cable Locked! (Serial: {oven_serial_val})")
        else:
            print("[!] No new cable detected. Oven will remain unconfigured.")
            
    config = {
        "drive_ftdi_serial": drive_serial_val,
        "oven_ftdi_serial": oven_serial_val
    }
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    if os.path.basename(current_dir) == 'src':
        project_root = os.path.dirname(current_dir)
    else:
        project_root = current_dir
    
    config_dir = os.path.join(project_root, 'config')
    os.makedirs(config_dir, exist_ok=True) 
    
    config_file = os.path.join(config_dir, 'hardware_config.json')
    
    with open(config_file, "w") as f:
        json.dump(config, f, indent=4)
        
    print(f"\n[*] SUCCESS: Hardware configuration saved to {config_file}!")

if __name__ == "__main__":
    run_calibration()