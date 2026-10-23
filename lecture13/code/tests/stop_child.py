"""For check_stops_in_container.sh: a demo that starts a child the way er_session.py starts
ARIAC (Popen, no new session). The child runs on the system Python, so demo_inner.sh's venv
sweep cannot stop it: only the process-group stop can. The child starts a grandchild, as
ros2 launch starts Gazebo.

Run: stop_child.py exit | wait | ignore_int   (under demo_inner.sh --no-sim LIMIT)"""
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2].parent / "lecture8" / "code"))
from sim_session import start_watchdog  # noqa: E402

mode = sys.argv[1]
start_watchdog()
ignore = "signal.signal(signal.SIGINT, signal.SIG_IGN); " if mode == "ignore_int" else ""
child = ("import signal, subprocess, time; " + ignore +
         "subprocess.Popen(['sleep', '3031']); time.sleep(3030)")
subprocess.Popen(["/usr/bin/python3", "-c", child])
print("child started", flush=True)
if mode == "exit":
    sys.exit(0)
if mode == "ignore_int":
    signal.signal(signal.SIGINT, signal.SIG_IGN)
time.sleep(3000)
