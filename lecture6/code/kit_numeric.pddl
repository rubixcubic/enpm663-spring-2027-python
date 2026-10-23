; ENPM663 L6: the kit window as numeric PDDL (PDDL 2.1 fluents).
(define (domain kit-numeric)
  (:requirements :strips :typing :numeric-fluents)
  (:types cell agv)
  (:predicates (free ?c - cell) (on ?c - cell ?a - agv))
  (:functions (volts ?c - cell) (total ?a - agv)
              (placed ?a - agv))
  (:action place
    :parameters (?c - cell ?a - agv)
    :precondition (and (free ?c) (< (placed ?a) 4))
    :effect (and (on ?c ?a) (not (free ?c))
                 (increase (total ?a) (volts ?c))
                 (increase (placed ?a) 1))))
