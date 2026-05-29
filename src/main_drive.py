import os
import time
from Drive import Drive

drive = Drive(blockSize=65536)
#drive.randomWrite(startLBA=0, endLBA=None, min=1, patternID="Alternating")
drive.sequentialWrite(hour=1, min=5)
#drive.writeReadVerify()
#drive.randomRead()

#write read verify test -> verify data integrity -> sequential + random ??????????
#random write + random read with startlba, endlba, blocksize, write without pattern = write from buffer #
#Put default values of startLBA as 0, endLBA as max LBA of drive #
#Pattern should have a default value -> write from buffer #
#random with replacement #
#Specify time instead of numofEdits. If not set, then run forever till stopped #
#Display transfer rate after a set time #
#Write function just writes #
#Write/read function runs until end of disk if time not set #
#read function just reads, no need to check #

# Write base functions to read write verify one specific lba with set blocksize
# Write secondary functions to do this sequentially/randomly
# Modularise write and read functions to do single lba level