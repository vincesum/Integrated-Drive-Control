from ESPEC import SH241
import time
from datetime import datetime

#Only runs when executed directly

if __name__ == '__main__':
    test = SH241(address=1)
    test.OpenChannel()
    
    test.SetModeStandby()
    
    test.AddCycle(25, 30, 0, 0, 30, 2)
    
    
    test.PrintTaskList()
    test.startTask()
    
    
    

