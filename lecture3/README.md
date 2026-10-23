# Lecture 3 scripts

Three managed scripts. None needs ROS 2 or a simulator.

A managed file is one that `tools/sync_course.py` keeps identical here and in
the course's slides and docs repositories (the slides repository only, for a
file the docs do not carry).

- **`kit_views.py`**: writes one kit state three ways (PDDL facts, text, and a
  JSON record in `kit_record.json`), checks the record and two bad copies
  against a JSON schema, and computes the voltage range for the kit's fourth
  cell, with and without margins for chance. Slide:
  "lecture3/code/kit_views.py (excerpt)". Writes `outputs/kit_views.txt` and
  `outputs/kit_record.json`.
- **`ontology_check.py`**: the lecture's ontology sketch as three
  dictionaries; checks six statements against it. Slide:
  "lecture3/outputs/ontology_check.txt". Writes `outputs/ontology_check.txt`.
- **`track_cell.py`**: tracks one cell from stand-in events and prints each
  world-model change. Slide: "lecture3/outputs/track_cell.txt". Writes
  `outputs/track_cell.txt`.
