
from workflow_engine import can_transition

def test_technician_forward():
    assert can_transition("TECHNICIAN","ORDERED","IN_PROGRESS").allowed
    assert can_transition("TECHNICIAN","IN_PROGRESS","EXAM_COMPLETED").allowed

def test_technician_cannot_go_back():
    assert not can_transition("TECHNICIAN","IN_PROGRESS","ORDERED").allowed
    assert not can_transition("TECHNICIAN","EXAM_COMPLETED","IN_PROGRESS").allowed

def test_reception_only_books_to_order():
    assert can_transition("RECEPTION","BOOKED","ORDERED").allowed
    assert not can_transition("RECEPTION","ORDERED","IN_PROGRESS").allowed

def test_supervisor_override():
    assert can_transition("SUPER_ADMIN","EXAM_COMPLETED","BOOKED",override=True).allowed
