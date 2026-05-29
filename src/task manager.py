from Tasks import LinkedList
from Tasks import Task
from ESPEC import SH241
from Drive import Drive
import threading

class TaskManager():
    def __init__(self):
        self._tasklist = LinkedList()
        self._oven = SH241()

        # Initialise signals to start next task or cancel current task
        self.is_running = False
        self.current_task = None
        # Boolean flags that control task operations
        self.signal_task_complete = threading.Event()
        self.signal_task_cancel = threading.Event()


    def addtask(self, db_id=None, **kwargs):
            
        # Pass the standard variables, plus unpack all additional kwargs directly into Task
        task = Task(db_id=db_id, **kwargs)
        
        self._tasklist.enqueue(task)

    def add_oven_task(self, temp, hour, min, sec, taskname="Task", db_id="None"):
        self.addtask(temp=temp, hour=hour, min=min, sec=sec, taskname=taskname, db_id=db_id)

    def add_oven_cycle(self, temp1, temp2, hour, min, sec, totalCycles, taskname="Cycle", db_id="None"):
        self.addtask(temp=temp1, temp2=temp2, hour=hour, minute=min, sec=sec, totalCycles=totalCycles, taskname=taskname, db_id=db_id)

    def add_drive_sq_write(self, startLBA=0, endLBA=None, patternID=None, hour=None, min=None, sec=None, logger=None, taskname="sequentialWrite", db_id=None):
        self.addtask(db_id=db_id, taskname=taskname, 
                     startLBA=startLBA, endLBA=endLBA, patternID=patternID, 
                     hour=hour, min=min, sec=sec, logger=logger)

    def add_drive_sq_read(self, startLBA=0, endLBA=None, hour=None, min=None, sec=None, logger=None, taskname="sequentialRead", db_id=None):
        self.addtask(db_id=db_id, taskname=taskname, 
                     startLBA=startLBA, endLBA=endLBA, 
                     hour=hour, min=min, sec=sec, logger=logger)

    def add_drive_rnd_write(self, startLBA=0, endLBA=None, patternID=None, hour=None, min=None, sec=None, taskname="randomWrite", db_id=None):
        self.addtask(db_id=db_id, taskname=taskname, 
                     startLBA=startLBA, endLBA=endLBA, patternID=patternID, 
                     hour=hour, min=min, sec=sec)

    def add_drive_rnd_read(self, startLBA=0, endLBA=None, patternID=None, hour=None, min=None, sec=None, taskname="randomRead", db_id=None):
        self.addtask(db_id=db_id, taskname=taskname, 
                     startLBA=startLBA, endLBA=endLBA, patternID=patternID, 
                     hour=hour, min=min, sec=sec)
        
    def start_task(self):
        node = self._tasklist.head
        task = node.data

    #def start_task_loop(self):
        
