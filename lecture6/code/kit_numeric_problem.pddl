; Voltages chosen for this example (the c1 to c6 of select_cells.py,
; without c4, which is out of range).
(define (problem kit-window) (:domain kit-numeric)
  (:objects c1 c2 c3 c5 c6 - cell agv1 - agv)
  (:init (free c1) (free c2) (free c3) (free c5) (free c6)
    (= (volts c1) 3.75) (= (volts c2) 3.78) (= (volts c3) 3.72)
    (= (volts c5) 3.45) (= (volts c6) 3.52)
    (= (total agv1) 0) (= (placed agv1) 0))
  (:goal (and (= (placed agv1) 4)
              (>= (total agv1) 14.25) (<= (total agv1) 14.55))))
