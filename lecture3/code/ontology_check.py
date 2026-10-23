"""A small ARIAC ontology: classes, relations and instances.

The program checks statements against the classes each relation
accepts. A subclass counts as its parent class: a LiIonCell is a
Cell. The classes and relations are the lecture's sketch; the robot,
AGV and tester names are ARIAC 2025 model names, and the cells and
the kit are named for this example.

Run: python3 ontology_check.py   (plain Python, no packages)
"""

PARENT = {  # class: the class it is a kind of
    "LiIonCell": "Cell", "NiMHCell": "Cell",
    "InspectionRobot": "Robot", "AssemblyRobot": "Robot",
    "GantryWelder": "Robot",
}
RELATIONS = {  # relation: the class of each argument, in order
    "inSlot": ("Cell", "AGV", "Slot"),
    "atStation": ("AGV", "Station"),
    "testedBy": ("Cell", "Tester"),
    "partOf": ("Cell", "Kit"),
}
INSTANCES = {  # instance: its class
    "c1": "LiIonCell", "c2": "LiIonCell", "c3": "LiIonCell",
    "agv1": "AGV", "s1": "Slot", "s2": "Slot",
    "inspection": "Station", "voltage_tester_2": "Tester",
    "inspection_robot_1": "InspectionRobot", "kit1": "Kit",
}


def kinds(cls):
    """The class, then each class above it."""
    chain = [cls]
    while chain[-1] in PARENT:
        chain.append(PARENT[chain[-1]])
    return chain


def a(word):
    return f"an {word}" if word[0] in "AEIOU" else f"a {word}"


def check(relation, *args):
    wrong, kind_of = [], []
    for arg, want in zip(args, RELATIONS[relation]):
        chain = kinds(INSTANCES[arg])
        if want not in chain:
            wrong.append(f"{arg} is {a(chain[0])}, not {a(want)}")
        elif chain[0] != want:
            kind_of.append(f"{arg} is {a(chain[0])}, a kind of {want}")
    verdict = "rejected" if wrong else "accepted"
    print(f"{relation}({', '.join(args)}): {verdict}")
    for note in wrong or kind_of:
        print(f"  {note}")


def main():
    check("inSlot", "c1", "agv1", "s1")
    check("atStation", "agv1", "inspection")
    check("testedBy", "c3", "voltage_tester_2")
    check("inSlot", "c2", "inspection", "s2")
    check("atStation", "c1", "inspection")
    check("partOf", "inspection_robot_1", "kit1")


if __name__ == "__main__":
    main()
