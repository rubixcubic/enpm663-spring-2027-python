#!/usr/bin/env python3
"""L11 demo: Timeout stops a skill that hangs (py_trees 2.6.0).

A stand-in pick skill never finishes (it returns RUNNING forever).
Timeout fails it after 0.5 s, and the selector moves on to a
fallback that reports the failure up to the planner. The tree is
ticked every 0.2 s. Both durations are chosen for this example.
"""
import time

import py_trees
from py_trees.common import Status

PERIOD = 0.2     # seconds between ticks
LIMIT = 0.5      # Timeout duration, seconds


class HangingSkill(py_trees.behaviour.Behaviour):
    def update(self):
        return Status.RUNNING

    def terminate(self, new_status):
        if new_status == Status.INVALID and \
                self.status == Status.RUNNING:
            print("        pick_cell: stopped by its parent")


pick = HangingSkill("pick_cell")
timeout = py_trees.decorators.Timeout("timeout_0.5s", pick,
                                      duration=LIMIT)
report = py_trees.behaviours.Success("report_to_planner")
root = py_trees.composites.Selector(
    "pick_or_report", memory=True, children=[timeout, report])

start = time.monotonic()
for n in range(1, 7):
    print(f"tick {n} at {time.monotonic() - start:.1f} s")
    root.tick_once()
    print(f"        {timeout.name}: {timeout.status.name},"
          f" {root.name}: {root.status.name}")
    if root.status != Status.RUNNING:
        print(f"        {root.name} finished through"
              f" {root.current_child.name}")
        break
    time.sleep(PERIOD)
