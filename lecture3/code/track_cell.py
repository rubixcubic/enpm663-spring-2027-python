"""Track one cell from events, the way a GP1 tree must.

ARIAC publishes no pose for a cell, so the world model follows each
cell from events: the team's own inspection report, the break beam,
each skill result and the tester readings. The events are stand-ins,
not ARIAC messages. The step names follow the L4 starter tree and
the blackboard keys follow L4's table. The kit is the L3 example
kit (c1 to c3 in slots 1 to 3, 10.87 V); cell c4 is the new cell.

Chosen for this example: c4's true voltage, 3.58 V; seed 91. Each
average uses five readings, as L4's wait_for_voltage collects. The
reading noise is ARIAC's: standard deviation 0.05 V
(voltage_tester/model.sdf). The range with margins, 3.47 V to 3.59 V,
is the one kit_views.py prints for five readings. Step 7 follows GP1
Task 4: place the cell only if the four-cell total can still land in
14.25 V to 14.55 V; otherwise recycle it. With averages, a total
within the 0.09 V kit margin of an edge cannot be called, so the safe
call is to recycle.

Run: python3 track_cell.py   (plain Python, no packages)
"""
import random

TRUE_V, NOISE, READINGS, SEED = 3.58, 0.05, 5, 91
LOW, HIGH = 3.47, 3.59        # fourth-cell range with margins (V)
WIN_LOW, WIN_HIGH, MARGIN = 14.25, 14.55, 0.09   # kit window (V)


def main():
    rng = random.Random(SEED)
    wm = {"c4.location": "unknown", "/tester1/cell": None,
          "/kit/slots_filled": 3, "/kit/total": 10.87}

    def show(n, event, key, value, kind):
        wm[key] = value
        if isinstance(value, float):
            value = f"{value:.3f}"
        print(f"{n} {event:<24} {key} = {value}  [{kind}]")

    show(1, "submit_report(passed)", "c4.inspection", "passed",
         "your report")
    show(2, "beam: object_detected", "c4.location", "at beam",
         "inferred")
    show(3, "pick_from_conveyor: OK", "c4.location", "gripper 1",
         "inferred")
    show(4, "place_on_tester(1): OK", "/tester1/cell", "c4",
         "inferred")
    volts = [rng.gauss(TRUE_V, NOISE) for _ in range(READINGS)]
    print(f"5 tester 1: {READINGS} readings, {min(volts):.3f} V"
          f" to {max(volts):.3f} V  [observed]")
    avg = sum(volts) / READINGS
    show(5, "average of 5", "/tester1/voltage", avg, "inferred")
    fits = LOW <= avg <= HIGH
    print(f"  {avg:.3f} V inside {LOW:.2f} V to {HIGH:.2f} V: {fits}")
    total = wm["/kit/total"] + avg
    edge = min(total - WIN_LOW, WIN_HIGH - total)
    print(f"  total {total:.3f} V inside {WIN_LOW} V to {WIN_HIGH} V:"
          f" {WIN_LOW <= total <= WIN_HIGH}")
    print(f"  {edge:.3f} V from an edge, under the {MARGIN} V margin:"
          f" {edge < MARGIN}")
    show(6, "pick_from_tester(1): OK", "/tester1/cell", None,
         "inferred")
    if fits:
        show(7, "place_in_slot(4): OK", "c4.location", "agv1 s4",
             "inferred")
        show(7, "", "/kit/slots_filled", 4, "inferred")
        show(7, "", "/kit/total",
             wm["/kit/total"] + avg, "inferred")
    else:
        show(7, "recycle_cell: OK", "c4.location", "recycling bin",
             "inferred")
    print(f"kit on agv1: {wm['/kit/slots_filled']} cells,"
          f" {wm['/kit/total']:.2f} V; slot 4 still open:"
          f" {wm['/kit/slots_filled'] < 4}")


if __name__ == "__main__":
    main()
