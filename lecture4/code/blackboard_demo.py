"""Blackboard keys for one GP1 cell decision, and access checks.

Stand-in leaves, no robot. Tester readings are chosen for this
example; each cell's five readings average to the value shown.
"""
import textwrap

import py_trees
from py_trees.common import Access, Status
from py_trees.composites import Selector, Sequence

READINGS = [
    [3.54, 3.57, 3.55, 3.53, 3.56],  # averages 3.55 V
    [3.86, 3.84, 3.85, 3.85, 3.85],  # averages 3.85 V
    [3.63, 3.61, 3.62, 3.60, 3.64],  # averages 3.62 V
]
LOW, HIGH = 3.4, 3.8  # Li-Ion: 3.6 V plus or minus 0.2 V


class AverageVoltage(py_trees.behaviour.Behaviour):
    def __init__(self):
        super().__init__("average_voltage")
        self.bb = self.attach_blackboard_client(self.name)
        self.bb.register_key("/tester1/voltage", Access.WRITE)
        self.cells = iter(READINGS)

    def update(self):
        readings = next(self.cells)
        self.bb.set("/tester1/voltage", sum(readings) / 5)
        return Status.SUCCESS


class VoltageInRange(py_trees.behaviour.Behaviour):
    def __init__(self):
        super().__init__("voltage_in_range")
        self.bb = self.attach_blackboard_client(self.name)
        self.bb.register_key("/tester1/voltage", Access.READ)

    def update(self):
        v = self.bb.get("/tester1/voltage")
        return Status.SUCCESS if LOW <= v <= HIGH else Status.FAILURE


class PlaceInSlot(py_trees.behaviour.Behaviour):
    def __init__(self):
        super().__init__("place_in_slot")
        self.bb = self.attach_blackboard_client(self.name)
        self.bb.register_key("/tester1/voltage", Access.READ)
        self.bb.register_key("/kit/slots_filled", Access.WRITE)
        self.bb.register_key("/kit/total", Access.WRITE)

    def update(self):
        # The pick-and-place skill would run here; then the keys
        # are written, only after it succeeded.
        bb = self.bb
        bb.set("/kit/slots_filled", bb.get("/kit/slots_filled") + 1)
        total = bb.get("/kit/total") + bb.get("/tester1/voltage")
        bb.set("/kit/total", total)
        return Status.SUCCESS


class RecycleCell(py_trees.behaviour.Behaviour):
    def update(self):
        return Status.SUCCESS


setup = py_trees.blackboard.Client(name="setup")
for key in ("/kit/slots_filled", "/kit/total"):
    setup.register_key(key, Access.WRITE)
setup.set("/kit/slots_filled", 0)
setup.set("/kit/total", 0.0)

check, place = VoltageInRange(), PlaceInSlot()
recycle = RecycleCell("recycle_cell")
root = Sequence("handle_cell", True, [
    AverageVoltage(),
    Selector("place_or_recycle", False, [
        Sequence("place_if_good", True, [check, place]),
        recycle,
    ]),
])
viewer = py_trees.blackboard.Client(name="viewer")
for key in ("/tester1/voltage", "/kit/slots_filled", "/kit/total"):
    viewer.register_key(key, Access.READ)

for cell in (1, 2, 3):
    root.tick_once()
    placed = place.status == Status.SUCCESS
    action = "placed" if placed else "recycled"
    print(f"cell {cell}: {viewer.get('/tester1/voltage'):.2f} V,"
          f" {action}; slots_filled="
          f"{viewer.get('/kit/slots_filled')},"
          f" kit total {viewer.get('/kit/total'):.2f} V")

print("A reader tries to write:")
try:
    check.bb.set("/tester1/voltage", 0.0)
except AttributeError as error:
    print("  AttributeError:")
    print(textwrap.fill(str(error), 60, initial_indent="    ",
                        subsequent_indent="    "))
