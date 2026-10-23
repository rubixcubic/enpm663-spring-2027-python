; ENPM663 L6: a PDDL domain for part of ARIAC 2025 Task 1.
; The names are example names for this lecture, not the GP3 spec.
(define (domain task1)
  (:requirements :strips :typing)
  (:types cell robot tester agv slot station)
  (:constants inspection shipping - station
              s1 s2 s3 s4 - slot)       ; every tray has 4 slots
  (:predicates
    (at-door ?c - cell)                 ; past the door, on the belt
    (on-tester ?c - cell ?t - tester)
    (tester-free ?t - tester)
    (holding ?r - robot ?c - cell)
    (hand-free ?r - robot)
    (in-slot ?c - cell ?a - agv ?s - slot)
    (slot-free ?a - agv ?s - slot)
    (agv-at ?a - agv ?st - station)
    (voltage-ok ?c - cell)              ; 3.4 V to 3.8 V
    (voltage-bad ?c - cell)             ; outside 3.4 V to 3.8 V
    (recycled ?c - cell)
    (kit-checked ?a - agv)
    (submitted ?a - agv)
    (serves ?r - robot ?t - tester)     ; fixed: robot reaches tester
    (picks-conveyor ?r - robot)         ; fixed: inspection_robot_1
    (loads-agv ?r - robot))             ; fixed: inspection_robot_2

  ; Step 1b: inspection_robot_1 picks a cell off the conveyor
  (:action pick-from-conveyor
    :parameters (?r - robot ?c - cell)
    :precondition (and (picks-conveyor ?r) (at-door ?c)
                       (hand-free ?r))
    :effect (and (holding ?r ?c) (not (hand-free ?r))
                 (not (at-door ?c))))

  ; Step 1b: ... and places it in a voltage tester
  (:action place-on-tester
    :parameters (?r - robot ?c - cell ?t - tester)
    :precondition (and (serves ?r ?t) (holding ?r ?c)
                       (tester-free ?t))
    :effect (and (on-tester ?c ?t) (not (tester-free ?t))
                 (hand-free ?r) (not (holding ?r ?c))))

  ; Step 1d: inspection_robot_2 picks the tested cell
  (:action pick-from-tester
    :parameters (?r - robot ?c - cell ?t - tester)
    :precondition (and (serves ?r ?t) (on-tester ?c ?t)
                       (hand-free ?r))
    :effect (and (holding ?r ?c) (not (on-tester ?c ?t))
                 (tester-free ?t) (not (hand-free ?r))))

  ; Step 1d: a good cell goes on the tray of an AGV at inspection
  (:action place-in-slot
    :parameters (?r - robot ?c - cell ?a - agv ?s - slot)
    :precondition (and (loads-agv ?r) (holding ?r ?c)
                       (voltage-ok ?c) (slot-free ?a ?s)
                       (agv-at ?a inspection))
    :effect (and (in-slot ?c ?a ?s) (not (slot-free ?a ?s))
                 (hand-free ?r) (not (holding ?r ?c))))

  ; Step 1d: an out-of-range cell goes to the recycling bin
  (:action recycle
    :parameters (?r - robot ?c - cell)
    :precondition (and (loads-agv ?r) (holding ?r ?c)
                       (voltage-bad ?c))
    :effect (and (recycled ?c) (hand-free ?r)
                 (not (holding ?r ?c))))

  ; Step 1d: ARIAC's /{agv_name}/check_kit_quality service
  (:action check-kit
    :parameters (?a - agv ?c1 ?c2 ?c3 ?c4 - cell)
    :precondition (and (agv-at ?a inspection)
                       (in-slot ?c1 ?a s1) (in-slot ?c2 ?a s2)
                       (in-slot ?c3 ?a s3) (in-slot ?c4 ?a s4))
    :effect (kit-checked ?a))

  ; Step 1e: ARIAC's /{agv_name}/move action
  (:action move-agv
    :parameters (?a - agv ?from - station ?to - station)
    :precondition (agv-at ?a ?from)
    :effect (and (agv-at ?a ?to) (not (agv-at ?a ?from))))

  ; Step 1e: ARIAC's /submit_kitting_order service
  (:action submit-kit
    :parameters (?a - agv)
    :precondition (and (kit-checked ?a) (agv-at ?a shipping))
    :effect (submitted ?a)))
