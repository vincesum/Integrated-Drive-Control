'''
Timer.py: Implements a Timer class for managing countdown timers in HH:MM format for ESPEC ovens and an internal Python timer in HH:MM:SS format.
'''


import time
import threading

#Class used for controlling a countdown timer for ESPEC ovens
class ProgTimer:
    def __init__(self):
        self.minutes = None
        #Uses threading event to manage timer state
        self.stop_event = threading.Event() 

    def setTimer(self, duration):
        self.minutes = self.hhmm_to_minutes(duration)
        return

    def hhmm_to_minutes(self, time_string):
        """
        Converts an HH:MM format string to total minutes (integer).
        Handles single-digit hours correctly.
        """
        try:
            # Split the string into hours and minutes
            hours_str, minutes_str = time_string.split(':')
            
            # Convert the string components to integers
            hours = int(hours_str)
            minutes = int(minutes_str)
        
            # Calculate the total minutes
            total_minutes = hours * 60 + minutes
            return total_minutes
        
        except ValueError:
            return "Invalid format. Use 'HH:MM' (e.g., '02:40' or '2:40')."

    def timerFinished(self):
        print("Timer finished!")
        # Signal that the timer has finished
        self.stop_event.set()
        self.minutes = None
        return

    def startTimer(self):
        if self.minutes is None:
            raise ValueError("Timer duration not set. Call setTimer() first.")
        # Cancel any existing timer
        if hasattr(self, "timer") and self.timer is not None:
            self.timer.cancel()
        # Clear the stop event before starting the timer
        self.stop_event.clear() 
        self.timer = threading.Timer(self.minutes * 60, self.timerFinished)
        self.timer.start()
        return
    
#Class used for controlling a simple countdown timer in HH:MM:SS format in python
class PyTimer():
    def __init__(self):
        self.hours = 0
        self.minutes = 0
        self.seconds = 0
        self.stop_event = threading.Event()
        
    def setTimer(self, hours, minutes, seconds):
        self.hours = hours
        self.minutes = minutes
        self.seconds = seconds
        return
    
    #Overload setTimer method with a way to set timer using only seconds
    #Handles the conversion to HH:MM:SS internally
    def setTimerSeconds(self, seconds):
        self.hours = seconds // 3600
        self.minutes = (seconds % 3600) // 60
        self.seconds = seconds % 60
            
    def getTimerSeconds(self, hours, minutes, seconds):
        return hours * 3600 + minutes * 60 + seconds
    
    #Timer tick function that ticks every second
    #Main driver of timer countdown
    def timerTick(self):
        if self.stop_event.is_set():
            return
        print(f"Time left: {self.hours:02}:{self.minutes:02}:{self.seconds:02}")
        if self.seconds > 0:
            self.seconds -= 1
        elif self.minutes > 0:
            self.minutes -= 1
            self.seconds = 59
        elif self.hours > 0:
            self.hours -= 1
            self.minutes = 59
            self.seconds = 59
        else:
            print("Timer finished!")
            self.stop_event.set()
            return
        # Schedule the next tick after 1 second
        threading.Timer(1, self.timerTick).start()
        return
    
    def runTimer(self):
        self.stop_event.clear()
        self.timerTick()
        return
    
    def pauseTimer(self):
        self.stop_event.set()
        return