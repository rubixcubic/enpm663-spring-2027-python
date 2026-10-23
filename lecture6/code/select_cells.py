"""L6 demo 6: the kit voltage window, in plain Python.

Li-Ion limits from ARIAC's CellTypes.msg: nominal 3.6 V, each cell
within 0.2 V, the kit of four within 0.15 V. The measured voltages
below are chosen for this example. They are averages of noisy
readings: "in range by the averages" is not a promise that ARIAC
accepts the kit (kit_margin.py measures how often it would not).
Sums are rounded to 0.01 V so that floating-point error does not
move a cell across a limit.
"""
NOMINAL, CELL_TOL, KIT_TOL = 3.6, 0.2, 0.15
LOW = round(NOMINAL - CELL_TOL, 2)                  # 3.4
HIGH = round(NOMINAL + CELL_TOL, 2)                 # 3.8
KIT_LOW = round(4 * NOMINAL - KIT_TOL, 2)           # 14.25
KIT_HIGH = round(4 * NOMINAL + KIT_TOL, 2)          # 14.55


def window(placed):
    """Range for the sum of the cells still to place."""
    total = round(sum(placed), 2)
    return round(KIT_LOW - total, 2), round(KIT_HIGH - total, 2)


def can_finish(placed):
    """True if cells in 3.4 V to 3.8 V can still complete the kit."""
    left = 4 - len(placed)
    lo, hi = window(placed)
    return left * LOW <= hi and left * HIGH >= lo


def fill_kit(arrivals, look_ahead):
    """Place cells on agv1 as they arrive; return the kit."""
    kit = []
    for cell, volts in arrivals:
        placed = [v for _, v in kit]
        if not LOW <= volts <= HIGH:
            print(f"  {cell} {volts:.2f} V: recycle (out of range)")
        elif look_ahead and not can_finish(placed + [volts]):
            print(f"  {cell} {volts:.2f} V: agv2 (blocks agv1)")
        else:
            kit.append((cell, volts))
            lo, hi = window(placed + [volts])
            rest = (f"rest must sum to {lo:.2f} to {hi:.2f} V"
                    if len(kit) < 4 else "kit full")
            print(f"  {cell} {volts:.2f} V: agv1 slot {len(kit)}; "
                  + rest)
        if len(kit) == 4 or not can_finish([v for _, v in kit]):
            break
    return kit


for n in (3, 2):
    lo, hi = window([3.75] * n)
    print(f"{n} cells at 3.75 V: rest must sum to {lo:.2f} to "
          f"{hi:.2f} V; can finish: {can_finish([3.75] * n)}")

ARRIVALS = [("c1", 3.75), ("c2", 3.78), ("c3", 3.72),
            ("c4", 3.86), ("c5", 3.45), ("c6", 3.52)]
for look_ahead in (False, True):
    print("look ahead:", look_ahead)
    kit = fill_kit(ARRIVALS, look_ahead)
    total = round(sum(v for _, v in kit), 2)
    if len(kit) == 4 and KIT_LOW <= total <= KIT_HIGH:
        print(f"  kit total {total:.2f} V: in range by the averages")
        for slot, (cell, _) in enumerate(kit, start=1):
            print(f"  goal: (in-slot {cell} agv1 s{slot})")
    else:
        print(f"  kit total {total:.2f} V: lost, agv1 to recycling")
