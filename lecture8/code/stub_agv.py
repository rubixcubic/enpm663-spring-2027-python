"""A stand-in for ARIAC's AGV move action (/agvN/move). No simulator.

The rules come from ARIAC 2025:
ariac_plugins/src/agv_motion_plugin.cpp, goal_recieved_cb (lines 248
to 282). A goal to the AGV's own station is rejected, and only the
seven paths in PATHS are accepted. Station ids come from
AgvStations.msg. The factory state is chosen for this example: three
AGVs (agv1 to agv3), each with a count of filled slots.
"""

STATIONS = {"INSPECTION": 1, "ASSEMBLY": 2, "SHIPPING": 3,
            "RECYCLING": 4}

PATHS = {
    ("INSPECTION", "ASSEMBLY"), ("ASSEMBLY", "INSPECTION"),
    ("INSPECTION", "SHIPPING"), ("SHIPPING", "INSPECTION"),
    ("INSPECTION", "RECYCLING"), ("RECYCLING", "INSPECTION"),
    ("SHIPPING", "RECYCLING"),
}


def example_factory():
    """The state used by every L8 demo (chosen for this example)."""
    return {
        1: {"station": "INSPECTION", "cells": 4},
        2: {"station": "INSPECTION", "cells": 3},
        3: {"station": "RECYCLING", "cells": 0},
    }


def move_agv(factory, agv, station):
    """Imitate /agv{agv}/move with station_id STATIONS[station]."""
    here = factory[agv]["station"]
    if (here, station) not in PATHS:
        return {"status": "REJECTED",
                "reason": f"no ARIAC path {here} to {station}"}
    factory[agv]["station"] = station
    return {"status": "SUCCEEDED", "agv": agv, "station": station}
