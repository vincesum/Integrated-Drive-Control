import os
import random
import time
import numpy as np
import math
import subprocess
import json

# CONFIGURATION
# WARNING: Changing this might lead to system destruction
DISK_NUMBER = 1
DRIVE_PATH = rf"\\.\PhysicalDrive{DISK_NUMBER}"

#Dictionary to store pattern IDs
PATTERNS = {
    # (Alternating bits: 10101010 01010101)
    "Alternating": b"\xAA\x55", #* (self.blockSize // 2),
    "Zeroes": b"\x00\x00", #* (self.blockSize // 2),
    "Ones": b"\xFF\xFF" #* (self.blockSize // 2)
}

#Data storage standard units, dictionary ID refers to the powers of 10
Units = {
    0: "",
    3: "K",
    6: "M",
    9: "G",
    12: "T",
}

class Drive():
    def __init__(self, blockSize):
        self.initialised = True
        self.blockSize = blockSize
        self.DRIVE_PATH = self.get_physical_drives()
        self.driveSize = self.get_drive_capacity(self.DRIVE_PATH)
        print(f"Drive Size: {self.convertUnits(self.driveSize)}")
        
    
    def get_physical_drives(self):
        '''
        Gets all physical drives connected to the device with powershell subprocess, 
        outputs data as JSON and returns the next physical drive path after system drive
        '''
        ps_command = (
            "Get-Disk | Select-Object Number, FriendlyName, Size, BusType | ConvertTo-Json"
        )
        
        # Run the command silently in the background
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_command], 
            capture_output=True, 
            text=True
        )
        
        if not result.stdout.strip():
            return []

        # Parse the JSON string from PowerShell into a Python dictionary
        disks = json.loads(result.stdout)
        
        # If only one disk is found, PS returns a dict instead of a list. Wrap it.
        if isinstance(disks, dict):
            disks = [disks]

        available_drives = []
        for disk in disks:
            # Convert raw byte size to Terabytes for easier validation
            size_tb = disk.get('Size', 0) / (1024**4) # Value defaults to 0 if operation failed to get
            
            available_drives.append({
                "number": disk.get('Number'),
                "model": disk.get('FriendlyName'),
                "size_tb": round(size_tb, 2),
                "bus": disk.get('BusType')
            })
        for drive in available_drives:
            # Safety Check: Never select the OS drive (usually Disk 0)
            if drive['number'] == 0:
                continue
                
            return rf"\\.\PhysicalDrive{drive['number']}"
        return None


    def get_drive_capacity(self, target_drive_path):
        """Queries the Windows kernel for the exact byte size of a physical drive."""
        try:
            # Ask Windows for the Name and Size of all attached physical drives
            output = subprocess.check_output(
                ['wmic', 'diskdrive', 'get', 'Name,Size', '/value'], 
                universal_newlines=True
            )
            current_name = None  
            # Parse the WMI output to find our specific drive
            for line in output.strip().splitlines():
                line = line.strip()
                if line.startswith("Name="):
                    current_name = line.split("=")[1]
                elif line.startswith("Size=") and current_name.upper() == target_drive_path.upper():
                    return int(line.split("=")[1])
                    
            print(f"[!] Drive {target_drive_path} not found in WMI query.")
            return 0
            
        except Exception as e:
            print(f"[!] Error querying drive size: {e}")
            return 0
        
    def write(self, drive_handler, LBA=None, chunk=None, flush=False):
        try:
            # 1. Seek the LBA if its provided
            if not LBA == None:
                drive_handler.seek(LBA * self.blockSize)
            # 2. Write on the current LBA
            drive_handler.write(chunk)
            # Flushes RAM buffer if flush is true for accurate transfer speeds and prevent RAM overflow
            if (flush):
                fd = drive_handler.fileno()
                os.fsync(fd)
        except OSError as e:
            # 4. The End-of-Disk Catch
            if "space" in str(e).lower() or e.errno == 28:
                print(f"\n[*] Hit physical end of disk platters!")
            else:
                # If it's a different hardware error (like a disconnected cable)
                print(f"\n[!] Hardware Error during write: {e}")
                raise

    def read(self, drive_handle, LBA=None, read_size=None):
        try:
            # 1. Seek the LBA if its provided
            if LBA is not None:
                drive_handle.seek(LBA * self.blockSize)
                
            # 2. Determine the payload size
            if read_size is None:
                read_size = self.blockSize
                
            # 3. Read and return
            return drive_handle.read(read_size)
            
        except Exception as e:
            print(f"\nFATAL ERROR: {e}")
            raise
        
    def writeReadVerify(self, startLBA=0, endLBA=None, patternID=None):
        # Sets endLBA to last LBA of drive if not set
        if endLBA is None:
            endLBA = self.driveSize // self.blockSize
            
        # Chunk generation
        if patternID is None:
            chunk = os.urandom(self.blockSize)
        else:
            chunk = PATTERNS[patternID] * (self.blockSize // 2)

        # Initialization
        start_time = time.time()
        last_time = start_time
        total_chunk_writes = 0
        curr_chunk_writes = 0
        
        writelba = startLBA
        readlba = startLBA
        
        # THE BATCH TARGET: 25,000 chunks is exactly 100MB (assuming 4096-byte blocks).
        # This is the perfect sweet spot: big enough to get fast sequential speeds, 
        # but small enough that it will never choke the RAM or the SATA controller.

        # 100 MB = 100 * 1024 * 1024 bytes
        TARGET_RAM_BYTES = 100 * 1024 * 1024
        BATCH_SIZE = TARGET_RAM_BYTES // self.blockSize

        print("Commencing Write/Read Verify (100MB Batches):")
        
        try:
            with open(self.DRIVE_PATH, 'rb+') as drive:
                fd = drive.fileno()

                # Main overarching loop
                while writelba < endLBA:
                    
                    # --- 1. THE WRITE PHASE ---
                    # Calculate exactly where this batch should stop.
                    # The min() function acts as your absolute safety brake so you never pass endLBA!
                    write_target = min(writelba + BATCH_SIZE, endLBA)
                    first_write = True # seek once before write
                    first_read = True # seek once before read
                    
                    while writelba < write_target:
                        
                        if first_write:
                            self.write(drive_handler=drive, LBA=writelba, chunk=chunk, flush=False)
                            first_write = False
                        else:
                            self.write(drive_handler=drive, chunk=chunk, flush=False)
                        writelba += 1
                        curr_chunk_writes += 1
                    
                    first_write = True # reset first_write
                    # --- 2. THE FLUSH PHASE ---
                    # 100MB is sitting perfectly in RAM. Whip it to the physical platters in one clean burst.
                    os.fsync(fd)

                    # --- 3. THE VERIFY PHASE ---
                    # Catch the read head up to where the write head just stopped
                    while readlba < writelba:
                        if first_read:
                            read_chunk = self.read(drive_handle=drive, LBA=readlba)
                            first_read = False
                        else:
                            read_chunk = self.read(drive_handle=drive)
                        
                        if read_chunk != chunk:
                            print(f"\n[!] CORRUPTION DETECTED at LBA {readlba} during verification. Exiting.")
                            return
                            
                        readlba += 1 

                    first_read = True # reset first_read

                    # --- 4. THE UI TIMER ---
                    curr_time = time.time()
                    time_delta = curr_time - last_time # Find exactly how many seconds passed
                    
                    if time_delta >= 1:
                        total_chunk_writes += curr_chunk_writes
                        
                        # THE FIX: Divide the chunks by the seconds to get True Velocity!
                        chunks_per_sec = int(curr_chunk_writes / time_delta)
                        
                        print(f"Total bytes verified: {self.printChunkToBytes(total_chunk_writes)}/{self.printChunkToBytes(endLBA-startLBA)}")
                        
                        # Pass the calculated speed into your formatter, NOT the batch volume
                        print(f"Current verifying speed: {self.printChunkToBytes(chunks_per_sec)} per second") 
                        
                        print(f"Time elapsed: {self.printTimeHHMMSS(curr_time - start_time)}\n")
                        
                        last_time = curr_time  
                        curr_chunk_writes = 0
                        
        except OSError as e:
            print(f"\n[!] Hardware Error during verify: {e}")
            
        finally:
            # Catch any leftover math when the final loop finishes
            total_chunk_writes += curr_chunk_writes
            final_time = time.time()
            print("\n--- VERIFY COMPLETE ---")
            print(f"Total bytes verified: {self.printChunkToBytes(total_chunk_writes)}/{self.printChunkToBytes(endLBA-startLBA)}")
            if (final_time - start_time) > 0:
                print(f"Average speed: {self.printChunkToBytes(total_chunk_writes // (final_time - start_time))} per second")
            print(f"Total time elapsed: {self.printTimeHHMMSS(final_time - start_time)}\n")
    ## DONE LOG
    def sequentialWrite(self, startLBA=0, endLBA=None, patternID=None, hour=None, min=None, sec=None, logger=None):
        # Sets endLBA to last LBA of drive if not set
        if (endLBA == None):
            endLBA = self.driveSize // self.blockSize
        # Chunk generation for the written chunk
        if (patternID == None):
            chunk = os.urandom(self.blockSize)
        else:
            chunk = PATTERNS[patternID] * (self.blockSize // 2)
        # Generate super chunk
        multiplier = 1048576 // self.blockSize 
        super_chunk = chunk * multiplier
        # Setup timer if required
        hasTime = False
        if not (hour==None and min==None and sec==None):
            hasTime = True
            totalSeconds = self.convertToSeconds(hour=hour,min=min,second=sec)
        # Initialise variables
        start_time = time.time()
        total_chunk_writes = 0
        curr_chunk_writes = 0
        last_time = start_time
        curr_time = start_time
        flush = True

        print("Commencing sequential write:")
        
        # TRACKING VARIABLES
        curr_lba = startLBA
        error_printed = False 
        
        # OUTER LOOP: Keeps the thread alive and tries to reconnect to the drive
        while curr_lba < endLBA:
            try:
                # Attempt to open the drive. (If offline, this instantly throws an exception)
                with open(self.DRIVE_PATH, 'rb+', buffering=0) as drive:
                    
                    # If we just recovered from a crash, reset the flag
                    if error_printed:
                        print(f"\n[*] Drive reconnected! Resuming write at LBA {curr_lba}...", flush=True)
                        error_printed = False

                    #Inner loop
                    while curr_lba < endLBA:
                        
                        if flush:
                            # Use the wrapper for the 1-second flush/seek
                            self.write(drive_handler=drive, LBA=curr_lba, chunk=super_chunk, flush=True)
                            flush = False
                        else:
                            # INLINED HOT PATH: Dump 1MB directly to the OS
                            drive.write(super_chunk)
                            
                        # Because we wrote 1MB, we must increment our LBA and Chunk trackers by the multiplier!
                        curr_chunk_writes += multiplier 
                        curr_lba += multiplier

                        # --- THE SPEED FIX ---
                        # Only interrupt the hardware to check the clock every 1,000 chunks!
                        if curr_chunk_writes % multiplier == 0:
                            curr_time = time.time()
                            
                            # 1-Second Print & Log Block
                            if curr_time - last_time >= 1:

                                # Dump cache once a second
                                os.fsync(drive.fileno())

                                total_chunk_writes += curr_chunk_writes
                                print(f"Total bytes written: {self.printChunkToBytes(total_chunk_writes)}/{self.printChunkToBytes(endLBA-startLBA)}")
                                print(f"Current write speed: {self.printChunkToBytes(curr_chunk_writes)} per second")
                                
                                if logger is not None:
                                    logger.record(isWriting=True, bytes=self.chunkToBytes(curr_chunk_writes))
                                    
                                last_time = curr_time
                                curr_chunk_writes = 0
                                flush = True # Flush the OS buffer every 1 second
                                
                                if hasTime:
                                    print(f"Time elapsed: {self.printTimeHHMMSS(curr_time - start_time)}\n")
                                    
                            # Test Timer Expiration Check
                            if hasTime and (curr_time - start_time >= totalSeconds):
                                duration = time.time() - start_time
                                print("\n--- WRITE COMPLETE ---")
                                print(f"Total Written : {self.printChunkToBytes(total_chunk_writes)}")
                                print(f"Time Elapsed  : {duration:.2f} seconds")
                                print(f"Average Speed : {self.printChunkToBytes(total_chunk_writes // duration)} per second\n")
                                return
                        # Successfully wrote the chunk, move to the next one!
                        curr_lba += 1

            except Exception as e:
                # CRASH HANDLER
                # Only print the error if the flag is False
                if not error_printed:
                    print(f"\n[FATAL] Drive disconnected: {e}", flush=True)
                    print("[*] Pausing write thread and waiting for reconnect...", flush=True)
                    error_printed = True # Set flag to True so it doesn't print again
                logger.record(isWriting=True, bytes=e, isError=True)
                # Wait 2 seconds before the outer loop tries to open the drive again
                time.sleep(2)
                
                # Make sure the test timer can still expire while the drive is disconnected!
                if hasTime and (time.time() - start_time >= totalSeconds):
                    print("\n--- WRITE TEST TIME EXPIRED WHILE DRIVE WAS OFFLINE ---")
                    return

    def sequentialRead(self, startLBA=0, endLBA=None, hour=None, min=None, sec=None, logger=None):
        hasTime = False
        if not (hour==None and min==None and sec==None):
            hasTime = True
            totalSeconds = self.convertToSeconds(hour=hour,min=min,second=sec)
            
        if endLBA == None:
            endLBA = self.driveSize // self.blockSize
            
        # Multiplier for super chunk
        multiplier = 1048576 // self.blockSize 
        read_size = self.blockSize * multiplier

        # Initialise variables
        curr_chunk_reads = 0
        total_chunk_reads = 0
        start_time = time.time()  
        last_time = start_time
        curr_time = start_time
        
        print("Commencing sequential read:")

        curr_lba = startLBA
        error_printed = False
        
        # This tells the wrapper to align the head on the very first loop
        requires_seek = True 

        # OUTER LOOP
        while curr_lba <= endLBA:
            try:
                # Unbuffered I/O 
                with open(self.DRIVE_PATH, 'rb+', buffering=0) as drive:
                    
                    if error_printed:
                        print(f"\n[*] Drive reconnected! Resuming read at LBA {curr_lba}...", flush=True)
                        error_printed = False
                        requires_seek = True # Re-align the head after a crash

                    # INNER LOOP
                    while curr_lba <= endLBA:
                        
                        seek_target = curr_lba if requires_seek else None
                        
                        _ = self.read(drive_handle=drive, LBA=seek_target, read_size=read_size)
                        
                        requires_seek = False # Turn off seeking until the next crash/restart

                        curr_chunk_reads += multiplier
                        curr_lba += multiplier
                        
                        # Multiplier fix
                        if curr_chunk_reads % multiplier == 0:
                            curr_time = time.time()
                            time_elapsed = curr_time - last_time
                            
                            # 1-Second Print & Log Block
                            if time_elapsed >= 1.0:
                                total_chunk_reads += curr_chunk_reads
                                
                                true_speed_chunks = int(curr_chunk_reads / time_elapsed)
                                
                                print(f"Total bytes read: {self.printChunkToBytes(total_chunk_reads)}/{self.printChunkToBytes(endLBA-startLBA)}")
                                print(f"Current read speed: {self.printChunkToBytes(true_speed_chunks)} per second")
                                
                                if logger is not None:
                                    logger.record(isWriting=False, bytes=self.chunkToBytes(curr_chunk_reads))
                                    
                                last_time = curr_time
                                curr_chunk_reads = 0
                                
                                if hasTime:
                                    print(f"Time elapsed: {self.printTimeHHMMSS(curr_time - start_time)}\n")
                                
                            if hasTime and (curr_time - start_time >= totalSeconds):
                                duration = time.time() - start_time
                                print("\n--- TEST COMPLETE ---")
                                print(f"Total Read    : {self.printChunkToBytes(total_chunk_reads)} ")
                                print(f"Time Elapsed  : {duration:.2f} seconds")
                                print(f"Average Speed : {self.printChunkToBytes(total_chunk_reads // duration)} per second\n")
                                return 

            except PermissionError:
                print("\nFATAL ERROR: Access Denied. You must run this terminal as Administrator.", flush=True)
                return 
            except Exception as e:
                # CRASH HANDLER
                if not error_printed:
                    print(f"\n[FATAL] Drive disconnected during read: {e}", flush=True)
                    print("[*] Pausing read thread and waiting for reconnect...", flush=True)
                    error_printed = True
                logger.record(isWriting=False, bytes=e, isError=True)
                time.sleep(2)
                
                if hasTime and (time.time() - start_time >= totalSeconds):
                    print("\n--- READ TEST TIME EXPIRED WHILE DRIVE WAS OFFLINE ---")
                    return
            
    def randomWrite(self, startLBA=0, endLBA=None, patternID=None, hour=None, min=None, sec=None, logger=None):
        if (endLBA == None):
            endLBA = self.driveSize // self.blockSize # End LBA of drive
        if (patternID == None):
            chunk = os.urandom(self.blockSize)
        else:
            chunk = PATTERNS[patternID] * (self.blockSize // 2)
        hasTime = False
        if not (hour==None and min==None and sec==None):
            hasTime = True
            totalSeconds = self.convertToSeconds(hour=hour,min=min,second=sec)
        start_time = time.time()
        total_chunk_writes = 0
        curr_chunk_writes = 0
        active = True
        try:
            with open(self.DRIVE_PATH, 'rb+') as drive:
            
                print("[*] Commencing random write...")
                last_time = start_time
                curr_time = start_time

                # Grab id tag
                fd = drive.fileno()

                # Write Loop
                while (active):

                    # Generate random LBA to write to and move to LBA on drive
                    randLBA = random.randrange(startLBA, endLBA)
                    drive.seek(randLBA * self.blockSize)

                    drive.write(chunk)
                    curr_chunk_writes += 1
                    curr_time = time.time()
                    if curr_time - last_time >= 1:
                        os.fsync(fd)
                        total_chunk_writes += curr_chunk_writes
                        print(f"Total bytes written: {self.printChunkToBytes(total_chunk_writes)}/{self.printChunkToBytes(endLBA-startLBA)}")
                        print(f"Current write speed: {self.printChunkToBytes(curr_chunk_writes)} per second")
                        if logger is not None:
                            logger.record(isWriting=True, bytes=self.chunkToBytes(curr_chunk_writes))
                        if (hasTime):
                            print(f"Time elapsed: {self.printTimeHHMMSS(curr_time - start_time)}\n")
                        last_time = curr_time
                        curr_chunk_writes = 0
                        if hasTime and (curr_time - start_time >= totalSeconds):
                            duration = time.time() - start_time
                            print("\n--- WRITE COMPLETE ---")
                            print(f"Total Written :{self.printChunkToBytes(total_chunk_writes)} ")
                            print(f"Time Elapsed  : {duration:.2f} seconds")
                            print(f"Average Speed : {self.printChunkToBytes(total_chunk_writes // duration)} per second\n")
                            break
                        
        except OSError as e:
            # 4. The End-of-Disk Catch
            if "space" in str(e).lower() or e.errno == 28:
                print(f"\n[*] Hit physical end of disk platters!")
            else:
                # If it's a different hardware error (like a disconnected cable)
                print(f"\n[!] Hardware Error during write: {e}")
                logger.record(isWriting=True, bytes=e, isError=True)

    def randomRead(self, startLBA=0, endLBA=None, patternID=None, hour=None, min=None, sec=None, logger=None):
        if (endLBA == None):
            endLBA = self.driveSize // self.blockSize # End LBA of drive
        hasTime = False
        if not (hour==None and min==None and sec==None):
            hasTime = True
            totalSeconds = self.convertToSeconds(hour=hour,min=min,second=sec)
        start_time = time.time()
        total_chunk_reads = 0
        curr_chunk_reads = 0
        active = True
        try:
            with open(self.DRIVE_PATH, 'rb+') as drive:
            
                print("[*] Commencing random read...")
                last_time = start_time
                curr_time = start_time

                # Grab id tag
                fd = drive.fileno()

                # Write Loop
                while (active):
                    
                    # Generate random LBA to write to and move to LBA on drive
                    randLBA = random.randrange(startLBA, endLBA)
                    drive.seek(randLBA * self.blockSize)

                    drive.read(self.blockSize)
                    curr_chunk_reads += 1
                    curr_time = time.time()
                    if curr_time - last_time >= 1:
                        total_chunk_reads += curr_chunk_reads
                        print(f"Total bytes read: {self.printChunkToBytes(total_chunk_reads)}/{self.printChunkToBytes(endLBA-startLBA)}")
                        print(f"Current read speed: {self.printChunkToBytes(curr_chunk_reads)} per second")
                        if logger is not None:
                            logger.record(isWriting=True, bytes=self.chunkToBytes(curr_chunk_reads))
                        if (hasTime):
                            print(f"Time elapsed: {self.printTimeHHMMSS(curr_time - start_time)}\n")
                        last_time = curr_time
                        curr_chunk_reads = 0
                        if hasTime and (curr_time - start_time >= totalSeconds):
                            duration = time.time() - start_time
                            print("\n--- READ COMPLETE ---")
                            print(f"Total Read :{self.printChunkToBytes(total_chunk_reads)} ")
                            print(f"Time Elapsed  : {duration:.2f} seconds")
                            print(f"Average Speed : {self.printChunkToBytes(total_chunk_reads // duration)} per second\n")
                            break
                        
        except OSError as e:
            # 4. The End-of-Disk Catch
            if "space" in str(e).lower() or e.errno == 28:
                print(f"\n[*] Hit physical end of disk platters!")
            else:
                # If it's a different hardware error (like a disconnected cable)
                print(f"\n[!] Hardware Error during read: {e}")
                logger.record(isWriting=False, bytes=e, isError=True)

    def printChunkToBytes(self, chunkCount):
        totalBytes = chunkCount * self.blockSize
        return self.convertUnits(totalBytes)
    
    def chunkToBytes(self, chunkCount):
        return chunkCount * self.blockSize
    
    def convertUnits(self, totalBytes):
        powers_of_ten = 0
        while (totalBytes > 1000):
            totalBytes /= 1000
            powers_of_ten += 3
        return f"{totalBytes:.2f}{Units[powers_of_ten]}B"

    def printTimeHHMMSS(self, totalSec):
        totalSec = int(totalSec)
        seconds = totalSec % 60
        minutes = (totalSec // 60) % 60
        hours = totalSec // 3600
        return (f"{hours:02d}:{minutes:02d}:{seconds:02d}")
    
    def convertToSeconds(self, hour=0, min=0, second=0):
        return ((hour or 0) * 3600) + ((min or 0) * 60) + (second or 0) # If none become 0
