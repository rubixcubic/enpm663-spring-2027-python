#!/usr/bin/env python3
"""L11 demo: a voltage tester watcher that treats a MALFUNCTIONING
status and silence both as failure.

No ROS and no simulator: the readings are synthetic, labeled here.
  - 10 readings per second, as the ARIAC tester publishes
    (voltage_tester_plugin.cpp, 0.1 s timer)
  - a Li-Ion cell at 3.60 V (chosen for this example) with noise of
    standard deviation 0.05 V (voltage_tester/model.sdf)
  - tester 1 fails from 180 s to 225 s (START_TIME 180, DURATION 45
    in the ARIAC docs' example trial file)

Run 1 sends what the ARIAC code sends during a malfunction: voltage
-1 with status MALFUNCTIONING. Run 2 sends nothing, which is what
the ARIAC docs say happens. The limits are chosen for this example.
"""
import random

OPERATIONAL, MALFUNCTIONING = 1, 2   # OperationStates.msg
STALE_AFTER = 0.5     # seconds without a reading: tester is down
NO_CELL_BELOW = 0.5   # volts: an empty tester reads about 0 V
WINDOW = 5            # valid readings in the average


class TesterWatcher:
    def __init__(self, name):
        self.name = name
        self.up = True
        self.last_msg = None
        self.window = []

    def set_state(self, now, up, reason):
        if up != self.up:
            self.up = up
            word = "UP" if up else "DOWN"
            print(f"  t = {now:6.1f} s  {self.name} {word}: {reason}")

    def on_reading(self, now, voltage, status):
        """Called for every message on /voltage_tester_N/voltage."""
        self.last_msg = now
        if status == MALFUNCTIONING:
            self.window.clear()
            self.set_state(now, False, f"status MALFUNCTIONING,"
                           f" voltage {voltage:.0f}")
            return
        self.set_state(now, True, "status OPERATIONAL again")
        if voltage < NO_CELL_BELOW:
            self.window.clear()    # no cell on the tester
            return
        self.window = (self.window + [voltage])[-WINDOW:]

    def on_timer(self, now):
        """Called by a 0.1 s timer, with or without a reading."""
        if self.last_msg is not None and \
                now - self.last_msg > STALE_AFTER:
            self.window.clear()
            self.set_state(now, False, f"no reading for more than"
                           f" {STALE_AFTER} s")

    def average(self):
        if not self.up or len(self.window) < WINDOW:
            return None
        return sum(self.window) / len(self.window)


def run(title, silent):
    print(title)
    rng = random.Random(11)
    w = TesterWatcher("tester_1")
    for k in range(1750, 2301):          # t = 175.0 s to 230.0 s
        now = k / 10
        broken = 180.0 <= now < 225.0
        if broken and not silent:
            w.on_reading(now, -1.0, MALFUNCTIONING)
        elif not broken:
            v = 3.60 + rng.gauss(0.0, 0.05)
            w.on_reading(now, v, OPERATIONAL)
        w.on_timer(now)
        if k in (1795, 2000, 2295):
            avg = w.average()
            text = "none" if avg is None else f"{avg:.2f} V"
            print(f"  t = {now:6.1f} s  average of last"
                  f" {WINDOW}: {text}")
    print()


def averages(readings):
    naive = sum(readings) / len(readings)
    good = [v for v in readings if v >= NO_CELL_BELOW]
    return naive, sum(good) / len(good)


if __name__ == "__main__":
    run("Run 1: the code's behavior (-1 and MALFUNCTIONING)", False)
    run("Run 2: the docs' behavior (no messages)", True)
    window = [3.62, 3.58, 3.61, -1.0]
    naive, checked = averages(window)
    print(f"Readings {window}")
    print(f"  average with -1 kept:     {naive:.4f} V")
    print(f"  average with -1 rejected: {checked:.4f} V")
