from concurrent.futures import thread
import os
from flask import Flask, render_template, url_for, request, redirect, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, time
from ESPEC import SH241
import threading
import webbrowser
import time

oven = SH241(address=1)
oven.OpenChannel()

oven_status = {
    "task_name": "Task",
    "mode": "STANDBY",
    "temp": 0,
    "state": "IDLE",
    "task_done": False,
}   


basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'test.db')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
current_task = None
oven_thread = None
task_started = False
oven_connected = False
cycle_id = 0 #keeps track of each half cycle to reset timer for cycling mode

class TaskList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    temp = db.Column(db.Float, default=0)
    temp1 = db.Column(db.Float, default=0) #For cycling mode
    hour = db.Column(db.Integer, default=0)
    min = db.Column(db.Integer, default=0)
    sec = db.Column(db.Integer, default=0)
    type = db.Column(db.String(50), default="Task")
    start_time = db.Column(db.Float, default=0)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    cycles = db.Column(db.Integer, default=0) #For cycling mode
    currCycles = db.Column(db.Integer, default=1)

@app.route('/', methods=['POST', 'GET'])
def index():
    tasks = TaskList.query.order_by(TaskList.date_created).all()
    return render_template('index.html', tasks=tasks, current_task=current_task)

@app.route('/cycle', methods=['POST', 'GET'])
def cycle():
    tasks = TaskList.query.order_by(TaskList.date_created).all()
    return render_template('cycling mode.html', tasks=tasks, current_task=current_task)

@app.route('/api/add_task', methods=['POST', 'GET'])
def add_task_route():
    if request.method == 'GET':
        tasks = TaskList.query.order_by(TaskList.date_created).all()
        return render_template('index.html', tasks=tasks, current_task=current_task)

    if request.method == 'POST':
        try:
            if request.is_json:
                data = request.json
                
                #For Task type "soak"
                t_mode = data.get('mode')
                if t_mode == "soak":
                    #Extract Data
                    t_temp = float(data.get('temp'))
                    t_h = int(data.get('hours', 0))
                    t_m = int(data.get('minutes', 0))
                    t_s = int(data.get('seconds', 0))

                    #Add to DATABASE (Logging)
                    new_db_task = TaskList(temp=t_temp, hour=t_h, min=t_m, sec=t_s, type="Task")
                    db.session.add(new_db_task)
                    db.session.commit()
                    
                    #Send to Oven
                    oven.AddTask(t_temp, t_h, t_m, t_s, taskname="Task", db_id=new_db_task.id)

                    return jsonify({"status": "success", "message": "Task added to Oven & DB"})
                
                #For Task type "cycle"
                elif t_mode == "cycle":
                    #Extract Data
                    t_temp1 = float(data.get('temp1'))
                    t_temp2 = float(data.get('temp2'))
                    t_h = int(data.get('hours', 0))
                    t_m = int(data.get('minutes', 0))
                    t_s = int(data.get('seconds', 0))
                    t_cycles = int(data.get('cycles', 1))

                    #Add to DATABASE (Logging)
                    new_db_task = TaskList(temp=t_temp1, temp1=t_temp2, cycles=t_cycles, hour=t_h, min=t_m, sec=t_s, type="Cycle")
                    db.session.add(new_db_task)
                    db.session.commit()
                    
                    #Send to Oven
                    oven.AddCycle(t_temp1, t_temp2, t_h, t_m, t_s, t_cycles, taskname="Cycle", db_id=new_db_task.id)

                    return jsonify({"status": "success", "message": "Cycle Task added to Oven & DB"})

            else:
                #Fallback for standard HTML Forms
                return "Error: Please use the JavaScript interface."

        except Exception as e:
            print(f"Error: {e}")
            return jsonify({"status": "error", "message": str(e)}), 400
        
@app.route('/api/delete/<int:id>')
def del_task_route(id):
    #Tries to get taskid
    task_to_delete = TaskList.query.get_or_404(id)
    try:
        db.session.delete(task_to_delete)
        db.session.commit()
        oven.deleteTask(id)
        return redirect('/')
    except Exception as e:
        print(f"CRITICAL ERROR: {e}") 
        return f'There was a problem deleting that task: {e}'
    
@app.route('/api/start')
def start_task_route():
    global current_task
    global task_started
    global oven_thread
    with app.app_context():
        if db.session.query(TaskList).count() == 0:
            current_task = None
            task_started = False
            return "No tasks in the database to start."
        try:
            task_to_start = db.session.query(TaskList).first()
            current_task = task_to_start
            current_task.start_time = -1  # Initialize start_time to -1 to indicate it hasn't started yet
            db.session.delete(task_to_start)
            db.session.commit()
            if task_started == False:
                oven_thread = threading.Thread(target=oven.startTask)
                oven_thread.start()
                task_started = True
            else:
                return "Oven is already running a task. Cannot start another one until it's done."
            return "Task Started", 200
        
        except Exception as e:
            return f'There was a problem starting the task: {e}'
    
@app.route('/api/stop')
def stop_task_route():
    global current_task
    if current_task is None:
        return "No tasks in the database to stop."
    
    try:
        global oven_thread
        global task_started
        current_task = None
        oven.stopTask()
        oven_thread = None
        task_started = False
        return redirect('/')
    except Exception as e:
        return f'There was a problem stopping the task: {e}' 
    
@app.route('/api/rs232')
def switch_to_rs232():
    try:
        oven.SetRS32()
        return "Switched to RS232 mode."
    except Exception as e:
        return f'Error switching to RS232 mode: {e}'

@app.route('/api/rs485')
def switch_to_rs485():
    try:
        oven.SetRS485()
        return "Switched to RS485 mode."
    except Exception as e:
        return f'Error switching to RS485 mode: {e}'

def update_status_loop():
    while True:
        oven_status['mode'] = oven.mode
        oven_status["temp"] = oven.temperature
        oven_status["state"] = oven.state
        oven_status["task_done"] = oven.task_done
        
        #Check for heartbeat every 1 second to fix server not closing after browser close bug
        global last_heartbeat
        #70s leeway
        if time.time() - last_heartbeat > 70:
            print("Browser closed or lost connection! Shutting down...")
            
            #Safely stop the oven before quitting
            try:
                if 'oven_connected' in globals() and oven_connected:
                    oven.stopTask()
            except:
                pass
                
            #Kill the invisible background server
            os._exit(0)
            
        threading.Event().wait(1)  # Update every 1 seconds
        global current_task
        global task_started
        
        if oven_status["task_done"]:
            current_task = None
            oven.task_done = False
            start_task_route()
            
        global cycle_id
        if oven.halfCycle != cycle_id and current_task:
            current_task.start_time = -1
            cycle_id = oven.halfCycle
            
        if oven_status["state"] == "SOAKING" and current_task and current_task.start_time == -1:
            current_task.start_time = datetime.now().timestamp()
            

@app.route('/api/status')
def get_status():
    global current_task
    
    # 1. If the queue is empty or no task is loaded
    queue = db.session.query(TaskList).all()
    
    queue_data = []
    for t in queue:
        queue_data.append({
            "id": t.id,
            "type": t.type,
            "temp": t.temp,
            "temp1": t.temp1 if t.type == "Cycle" else None,
            "hour": t.hour,
            "min": t.min,
            "sec": t.sec,
            "cycles": t.cycles if t.type == "Cycle" else None
        })
    
    if current_task is None:
        return jsonify({
            "state": "IDLE", 
            "start_time": -1, 
            "duration": 0,
            "temperature": oven.temperature if hasattr(oven, 'temperature') else "-",
            "type": "None",
            "id": -1,
            "queue": queue_data
        })
    
    # 2. Calculate the total duration in seconds safely
    # (Assuming current_task is a dictionary. If it's an object, use current_task.hour instead)
    total_seconds = (current_task.hour * 3600) + \
                    (current_task.min * 60) + \
                    current_task.sec
    
    # 3. Send back the live facts
    return jsonify({
        "state": oven.state,  # Make sure this points to your oven's live hardware state
        "start_time": current_task.start_time if hasattr(current_task, 'start_time') else -1,
        "duration": total_seconds,
        "hour": current_task.hour if hasattr(current_task, 'hour') else 0,
        "min": current_task.min if hasattr(current_task, 'min') else 0,
        "sec": current_task.sec if hasattr(current_task, 'sec') else 0,
        "temperature": oven.temperature if hasattr(oven, 'temperature') else "-",
        "set_temp": current_task.temp if hasattr(current_task, 'temp') else -1,
        "set_temp1": current_task.temp1 if hasattr(current_task, 'temp1') else -1,
        "cycles": current_task.cycles if hasattr(current_task, 'cycles') else -1,
        "currCycles": oven.currentCycle,
        "type": current_task.type if hasattr(current_task, 'type') else "None",
        "id": current_task.id if hasattr(current_task, 'id') else -1,
        "queue": queue_data
    })
    
@app.route('/api/shutdown')
def shutdown_server():
    print("Shutting down the server...")
    
    # Safety Check: Stop the oven before quitting!
    try:
        if oven_connected:
            oven.stopTask()
    except Exception as e:
        print(f"Could not stop oven: {e}")

    # This instantly kills the invisible Python process and all background loops
    os._exit(0)
    
# Heartbeat to detect if browser is still open in order to stop server when browser closes
last_heartbeat = time.time()
@app.route('/api/heartbeat')
def heartbeat():
    global last_heartbeat
    last_heartbeat = time.time() # Reset the clock!
    return "OK", 200


    
def open_browser():
    #This automatically opens the default web browser with the local server
    webbrowser.open_new("http://127.0.0.1:5000/")
    
    
if __name__ == '__main__':
    with app.app_context():
        print(f"DATABASE LOG: Looking for DB at: {db_path}")
        
        #Wipe it and recreate it to fix the 'type' column error
        db.drop_all() 
        db.create_all()
        print("DATABASE LOG: Tables recreated successfully!")
        try:
            num_deleted = db.session.query(TaskList).delete()
            db.session.commit()
            print(f"Startup Cleanup: Deleted {num_deleted} old tasks from the database.")
        except Exception as e:
            print(f"Cleanup Error: {e}")
            db.session.rollback()
        update_status_loop_thread = threading.Thread(target=update_status_loop, daemon=True)
        update_status_loop_thread.start()
        threading.Timer(1, open_browser).start()  # Open browser after a short delay
    app.run(debug=False)