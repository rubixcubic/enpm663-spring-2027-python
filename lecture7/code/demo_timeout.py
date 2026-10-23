"""L7 demo 3: Timeout around a leaf that waits for valid readings.

Usage: demo_timeout.py normal | silent | malfunction
The mock tester publishes every 0.1 s, as voltage_tester_plugin.cpp
does. 'malfunction' sends voltage -1 with MALFUNCTIONING, as the
ARIAC 2025 code does; 'silent' sends nothing, as the ARIAC docs
say. Tick period 0.05 s and time limit 2.0 s: chosen for this demo.
"""
import sys
import time

import py_trees
from py_trees.common import Status

OPERATIONAL, MALFUNCTIONING = 1, 2  # OperationStates.msg
PERIOD, TICK, LIMIT, NEEDED = 0.1, 0.05, 2.0, 10


class MockTester:
    """Stands in for /voltage_tester_1/voltage."""

    def __init__(self, mode):
        self.mode, self.start, self.sent = mode, time.monotonic(), 0

    def poll(self):
        """The (voltage, status) messages sent since the last poll."""
        due = int((time.monotonic() - self.start) / PERIOD)
        new, self.sent = due - self.sent, due
        if self.mode == "silent":
            return []
        if self.mode == "malfunction":
            return [(-1.0, MALFUNCTIONING)] * new
        return [(3.62, OPERATIONAL)] * new


class ReadVoltage(py_trees.behaviour.Behaviour):
    """The act leaf of check-voltage: averages 10 valid readings."""

    def __init__(self, name, tester):
        super().__init__(name)
        self.tester = tester

    def initialise(self):
        self.valid, self.skipped, self.messages = [], 0, 0

    def update(self):
        for volts, status in self.tester.poll():
            self.messages += 1
            if status != OPERATIONAL or volts < 0:
                self.skipped += 1  # MALFUNCTIONING or -1
                continue
            self.valid.append(volts)
        if len(self.valid) < NEEDED:
            return Status.RUNNING
        average = sum(self.valid) / len(self.valid)
        self.feedback_message = f"average {average:.2f} V"
        return Status.SUCCESS


tester = MockTester(sys.argv[1])
read = ReadVoltage("read voltage", tester)
root = py_trees.decorators.Timeout("timeout", read, duration=LIMIT)
start = time.monotonic()
while True:
    root.tick_once()
    if root.status != Status.RUNNING:
        break
    time.sleep(TICK)
now = time.monotonic()
print(f"{sys.argv[1]}: {root.status.name} after {now - start:.2f} s"
      f" {read.feedback_message}".rstrip())
print(f"  messages {read.messages}, valid {len(read.valid)}, "
      f"skipped {read.skipped}")
