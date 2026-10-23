"""One kit state, three views: PDDL facts, a JSON record checked
against a JSON schema, and a text description.

The kit values are chosen for this example. The limits come from
ARIAC 2025: three AGVs, four stations (AgvStations.msg), four tray
slots, the Li-Ion voltages in CellTypes.msg, and the tester noise
(standard deviation 0.05 V per reading, voltage_tester/model.sdf).
Each average uses five readings, the number L4's wait_for_voltage
collects.

Run: python3 kit_views.py   (needs the jsonschema package)
It writes kit_record.json in the folder it runs in.
"""

import copy
import json
import math

from jsonschema import Draft7Validator

KIT = {
    "agv": 1,
    "station": "INSPECTION",
    "cell_type": "LI_ION",
    "slots": [
        {"slot": 1, "cell": {"id": "c1", "voltage": 3.55}},
        {"slot": 2, "cell": {"id": "c2", "voltage": 3.62}},
        {"slot": 3, "cell": {"id": "c3", "voltage": 3.70}},
        {"slot": 4, "cell": None},
    ],
}

CELL = {
    "type": ["object", "null"],
    "required": ["id", "voltage"],
    "properties": {
        "id": {"type": "string"},
        "voltage": {"type": "number"},
    },
}
SCHEMA = {
    "type": "object",
    "required": ["agv", "station", "cell_type", "slots"],
    "properties": {
        "agv": {"type": "integer", "minimum": 1, "maximum": 3},
        "station": {
            "enum": ["INSPECTION", "ASSEMBLY", "SHIPPING", "RECYCLING"]
        },
        "cell_type": {"enum": ["LI_ION", "NIMH"]},
        "slots": {
            "type": "array",
            "minItems": 4,
            "maxItems": 4,
            "items": {
                "type": "object",
                "required": ["slot", "cell"],
                "properties": {
                    "slot": {
                        "type": "integer", "minimum": 1, "maximum": 4
                    },
                    "cell": CELL,
                },
            },
        },
    },
}


def pddl_facts(kit):
    agv = f"agv{kit['agv']}"
    facts = [f"(at {agv} {kit['station'].lower()})"]
    for s in kit["slots"]:
        slot = f"s{s['slot']}"
        if s["cell"] is None:
            facts.append(f"(slot-empty {agv} {slot})")
        else:
            c = s["cell"]["id"]
            # Inferred, not stored in KIT: a cell on the tray got
            # through the inspection door, so its report passed.
            facts += [f"(in-slot {c} {agv} {slot})", f"(passed {c})"]
    return facts


def text_view(kit):
    full = [s for s in kit["slots"] if s["cell"]]
    empty = [s["slot"] for s in kit["slots"] if not s["cell"]]
    volts = [f"{s['cell']['voltage']:.2f} V" for s in full]
    kind = "Li-Ion" if kit["cell_type"] == "LI_ION" else "Ni-MH"
    return [
        f"AGV {kit['agv']} is at the {kit['station'].lower()} "
        f"station. Kit type {kind}.",
        f"Slots {full[0]['slot']} to {full[-1]['slot']} hold cells "
        f"at {', '.join(volts[:-1])} and {volts[-1]}.",
        f"Slot {empty[0]} is empty.",
    ]


def record_text(kit):
    """The record as JSON text, one slot per line."""
    lines = ["{"]
    for key in ("agv", "station", "cell_type"):
        lines.append(f'  "{key}": {json.dumps(kit[key])},')
    lines.append('  "slots": [')
    rows = [f"    {json.dumps(s)}" for s in kit["slots"]]
    lines.append(",\n".join(rows))
    lines += ["  ]", "}"]
    return "\n".join(lines) + "\n"


def check(name, record):
    found = Draft7Validator(SCHEMA).iter_errors(record)
    errors = sorted(
        f"{'.'.join(map(str, e.absolute_path))}: "
        f"{e.validator} {e.validator_value}"
        for e in found
    )
    print(f"  {name}: {'valid' if not errors else 'rejected'}")
    for error in errors:
        print(f"    {error}")


def fourth_cell_range(kit, nominal=3.6, cell_tol=0.2, kit_tol=0.15,
                      margin=0.0, cell_margin=0.0):
    total = sum(s["cell"]["voltage"] for s in kit["slots"] if s["cell"])
    low = max(4 * nominal - kit_tol + margin - total,
              nominal - cell_tol + cell_margin)
    high = min(4 * nominal + kit_tol - margin - total,
               nominal + cell_tol - cell_margin)
    return total, low, high


def chance(noise=0.05, readings=5):
    """How far chance moves an average, and sums of averages."""
    one = noise / math.sqrt(readings)
    return one, math.sqrt(3) * one, math.sqrt(4) * one


def tail(z):
    """P(Z >= z) for a standard normal Z."""
    return 0.5 * math.erfc(z / math.sqrt(2))


def main():
    print("PDDL facts:")
    for fact in pddl_facts(KIT):
        print(f"  {fact}")
    print("Text:")
    for line in text_view(KIT):
        print(f"  {line}")
    with open("kit_record.json", "w") as fh:
        fh.write(record_text(KIT))
    print("JSON record: wrote kit_record.json")
    with open("kit_record.json") as fh:
        record = json.load(fh)
    print("JSON schema checks:")
    check("kit_record.json", record)
    bad_agv = copy.deepcopy(record)
    bad_agv["agv"] = 5
    check("agv 5", bad_agv)
    five_slots = copy.deepcopy(record)
    five_slots["slots"].append({"slot": 5, "cell": None})
    check("five slots", five_slots)
    total, low, high = fourth_cell_range(KIT)
    print(f"Three cells total {total:.2f} V.")
    print(f"The fourth cell must be from {low:.2f} V"
          f" to {high:.2f} V.")
    one, three, four = chance()
    print("Chance, 5 readings per cell, 0.05 V noise per reading:")
    print(f"  one average wanders by about {one:.4f} V")
    print(f"  a sum of 3 averages by about {three:.4f} V")
    print(f"  a sum of 4 averages by about {four:.4f} V")
    over = total + 3.75 - (4 * 3.6 + 0.15)
    z = over / four
    print(f"  with 3.75 V the kit reads {over:.2f} V over 14.55 V:"
          f" {z:.2f} spreads")
    print(f"  a true 14.55 V reads that high {100 * tail(z):.1f}%"
          f" of the time")
    m, cm = round(2 * four, 2), round(2 * one, 2)
    _, low, high = fourth_cell_range(KIT, margin=m, cell_margin=cm)
    print(f"Margins of {m:.2f} V (kit) and {cm:.2f} V (cell):")
    print(f"  the fourth cell should read {low:.2f} V"
          f" to {high:.2f} V.")


if __name__ == "__main__":
    main()
