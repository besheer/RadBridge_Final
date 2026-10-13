"""Original-lot returns over synthetic repository and movement ports."""
from types import SimpleNamespace as Row
from pathlib import Path
import subprocess
import sys

import pytest
from application.services.inventory.return_service import return_to_original_lots


class Repository:
    def __init__(self):
        self.rows=[Row(usage_type='USED',lot_id=10,unit_cost=5,qty=2),
                   Row(usage_type='EXTRA',lot_id=11,unit_cost=7,qty=2)]
        self.lots=[Row(id=10),Row(id=11)]
        self.events,self.added=[],[]
    def lock_order(self, order_id): self.events.append('order')
    def usage_rows(self,*args): return self.rows
    def locked_lots(self,*args): self.events.append('lots');return self.lots
    def create_usage(self,**values): return Row(**values)
    def add(self,usage): self.added.append(usage)


def execute(repo,qty,movements):
    def move(warehouse,item,take,kind,**values):
        row=Row(qty=take,kind=kind,lot_id=values['lot'].id)
        movements.append(row)
        return row
    return return_to_original_lots(repo,lambda order:None,lambda:None,move,
        Row(id=1),Row(id=2),qty,warehouse=Row(id=3),user=Row(id=4),reason='Synthetic return')


def test_original_lots_and_costs_are_preserved_across_a_split_return():
    repo=Repository();movements=[]
    result=execute(repo,3,movements)
    assert result is repo.added[0]
    assert [(r.lot_id,r.qty,r.unit_cost) for r in repo.added]==[(10,2,5),(11,1,7)]
    assert [(m.lot_id,m.qty,m.unit_cost) for m in movements]==[(10,2,5),(11,1,7)]
    assert repo.events==['order','lots']


def test_excess_return_is_rejected_before_lot_lock_or_movement():
    repo=Repository();movements=[]
    with pytest.raises(ValueError,match='Return exceeds'):execute(repo,5,movements)
    assert repo.events==['order'] and movements==[] and repo.added==[]


def test_missing_original_lot_is_rejected_before_any_stock_mutation():
    repo=Repository();movements=[];repo.lots=[Row(id=10)]
    with pytest.raises(ValueError,match='Original lot does not match'):execute(repo,3,movements)
    assert movements==[] and repo.added==[]


def test_previous_return_without_consumption_is_rejected():
    repo=Repository();movements=[]
    repo.rows.append(Row(usage_type='RETURN',lot_id=12,unit_cost=8,qty=1))
    with pytest.raises(ValueError,match='Previous returns'):execute(repo,1,movements)
    assert movements==[] and repo.added==[]


def test_service_import_has_no_storage_database_web_or_runtime():
    ris=str(Path(__file__).resolve().parents[1])
    code="import sys;sys.path.insert(0,%r);import application.services.inventory.return_service;assert not any(n == 'flask' or n == 'sqlalchemy' or n.startswith('infrastructure.') or n == 'application.legacy_runtime' for n in sys.modules)" % ris
    subprocess.run([sys.executable,'-c',code],check=True)
