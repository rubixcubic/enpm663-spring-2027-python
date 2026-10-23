"""When the course skill catches a cell on the moving conveyor, or refuses.

A model of pick_from_conveyor in the course skills package, v0.2.0
(commit 6fa0563). The arm waits at one fixed pose, its open fingers
across the belt at catch_x, and the cell rides into them.

  plan_catch():  enpm663_skills/conveyor.py, lines 26 to 63
  wait():        enpm663_skills/inspection_robot_1.py, _belt_change and
                 _wait_until, lines 57 to 98

Numbers from the package (v0.2.0):
  beam at x = 0.6 m            config/team_config.yaml, line 8
  catch_x = 1.40 m             enpm663_skills/config/skills.yaml, line 247
  side_lead_time = 3.925 s     skills.yaml, line 271 (measured)
  close_delay = -0.15 s        skills.yaml, line 297 (measured)
  max_trigger_age = 8.0 s      skills.yaml, line 302
  stopped_tolerance = 0.005 m  skills.yaml, line 306
  belt speed 0.1 m/s           team_config.yaml, line 2; the largest speed
                               ARIAC allows (user_config_schema.json)
Times are seconds of simulation time after the beam fired. Chosen for
this example: when each goal is sent, and when the belt stops in run C.
"""

BEAM_X = 0.6
CATCH_X = 1.40
SIDE_LEAD_TIME = 3.925
CLOSE_DELAY = -0.15
MAX_TRIGGER_AGE = 8.0
STOPPED_TOLERANCE = 0.005
SPEED = 0.1


class Refused(Exception):
    """PRECONDITION_FAILED, sent before any motion."""


def plan_catch(beam_x, speed, trigger, now):
    """Return (arrival, close_time), or raise Refused, as conveyor.py."""
    age = now - trigger
    if age < 0:
        raise Refused("beam trigger is in the future")
    if age > MAX_TRIGGER_AGE:
        raise Refused(f"trigger {age:.1f} s old, limit {MAX_TRIGGER_AGE} s")
    if speed == 0.0:
        if abs(beam_x - CATCH_X) > STOPPED_TOLERANCE:
            raise Refused("belt stopped, beam not at the catch x")
        ready = now + SIDE_LEAD_TIME
        return ready, ready
    arrival = trigger + (CATCH_X - beam_x) / speed
    if arrival < now + SIDE_LEAD_TIME:
        raise Refused(f"cell due in {arrival - now:.2f} s, "
                      f"arm needs {SIDE_LEAD_TIME} s")
    return arrival, arrival + CLOSE_DELAY


def speed_at(speeds, t):
    """The belt speed at time t, from a list of (start time, speed)."""
    v = speeds[0][1]
    for t0, s in speeds:
        if t0 <= t:
            v = s
    return v


def wait(speeds, now, close_time, plan_speed):
    """Return the time the belt changed while waiting, or None."""
    for t0, s in speeds:
        if now < t0 <= close_time and s != plan_speed:
            return t0
    return None


def run(name, speeds, now):
    print(name)
    speed = speed_at(speeds, now)
    try:
        arrival, close = plan_catch(BEAM_X, speed, 0.0, now)
    except Refused as why:
        print(f"  refused, no motion: {why}")
        return
    print(f"  cell at the catch x at t = {arrival:.2f} s; "
          f"close at t = {close:.2f} s")
    changed = wait(speeds, now, close, speed)
    if changed is None:
        print("  belt kept its speed: caught, holding CELL")
        return
    where = BEAM_X + speed * changed
    print(f"  t = {changed:.1f} s, belt changed: PRECONDITION_FAILED, "
          f"not closed")
    moved = "stopped" if speed_at(speeds, changed) == 0.0 else "was"
    print(f"  cell {moved} at x = {where:.2f} m; "
          f"the beam saw it at x = {BEAM_X:.2f} m")


def main():
    print(f"beam x = {BEAM_X:.2f} m, catch x = {CATCH_X:.2f} m, "
          f"belt at {SPEED} m/s")
    run("A. goal sent at t = 2.0 s", [(0.0, SPEED)], 2.0)
    run("B. goal sent at t = 5.0 s", [(0.0, SPEED)], 5.0)
    run("C. goal sent at t = 2.0 s, belt stops at t = 6.0 s",
        [(0.0, SPEED), (6.0, 0.0)], 2.0)
    run("D. goal sent at t = 7.0 s, belt stopped since t = 6.0 s",
        [(0.0, SPEED), (6.0, 0.0)], 7.0)
    feed_rate = 0.1  # cells per second, team_config.yaml line 3
    gap_t = 1 / feed_rate
    print(f"one cell every {gap_t:.0f} s at {SPEED} m/s: "
          f"{SPEED * gap_t:.1f} m apart")


if __name__ == "__main__":
    main()
