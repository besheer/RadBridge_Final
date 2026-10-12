"""Runtime-bound application.components.inventory; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

def install_0020(_rb):
    def _order_direct_consumable_cost(o):
        nr=_rb.NursingConsumableEntry.query.filter_by(order_id=o.id,confirmed=True).all()
        if nr:return sum(_rb._money(n.actual_qty)*_rb._money(n.consumable.unit_cost if n.consumable else 0) for n in nr)
        return sum(_rb._money(x.qty)*_rb._money(x.consumable.unit_cost if x.consumable else 0) for x in _rb.OrderConsumable.query.filter_by(order_id=o.id).all())
    return _order_direct_consumable_cost


def install_0058(_rb):
    def _record_stock_movement(item,qty,movement_type,reason='',reference_type='',reference_id='',branch_id=None,user_id=None):
        before=float(item.stock_qty or 0)
        after=before+float(qty or 0)
        item.stock_qty=after
        row=_rb.StockMovement(
          consumable_id=item.id,branch_id=branch_id,movement_type=movement_type,
          qty=float(qty or 0),before_qty=before,after_qty=after,
          reference_type=reference_type,reference_id=str(reference_id or ''),
          reason=reason,created_by=user_id
        )
        _rb.db.session.add(row)
        if _rb.ERP_SYNC_ENABLED:
            _rb.queue_erp_event('STOCK_MOVEMENT','stock_movement','pending', {
              'ris_item_code':item.code,'qty':float(qty or 0),'movement_type':movement_type,
              'reference_type':reference_type,'reference_id':str(reference_id or ''),
              'branch_id':branch_id,'reason':reason
            })
        return row
    return _record_stock_movement


def install_0059(_rb):
    def seed_default_consumables():
        added=0
        for x in _rb.DEFAULT_CONSUMABLE_CATALOG:
            c=_rb.Consumable.query.filter_by(code=x['code']).first()
            if c: continue
            c=_rb.Consumable(code=x['code'],barcode=x['barcode'],name=x['name_en'],name_en=x['name_en'],
                         name_ar=x['name_ar'],category=x['category'],unit=x['unit'],stock_qty=0,
                         reorder_level=0,unit_cost=0,selling_price=0,expiry_tracking=False,active=True)
            _rb.db.session.add(c);added+=1
        _rb.db.session.flush()
        return added
    return seed_default_consumables


def install_0060(_rb):
    def inventory_row(c):
        return {
          'code':c.code,'barcode':c.barcode or '','name_en':c.name_en or c.name or '',
          'name_ar':c.name_ar or '','category':c.category or '','unit':c.unit or 'unit',
          'stock_qty':float(c.stock_qty or 0),'reorder_level':float(c.reorder_level or 0),
          'unit_cost':float(c.unit_cost or 0),'selling_price':float(c.selling_price or 0),
          'expiry_tracking':1 if c.expiry_tracking else 0,'active':1 if c.active else 0
        }
    return inventory_row


def install_0061(_rb):
    def queue_erp_event(event_type,reference_type='',reference_id='',payload=None):
        row=_rb.ERPSyncQueue(event_type=event_type,reference_type=reference_type,
                         reference_id=str(reference_id or ''),payload_json=_rb.json.dumps(payload or {},ensure_ascii=False),
                         status='PENDING',attempts=0)
        _rb.db.session.add(row)
        return row
    return queue_erp_event


def install_0062(_rb):
    def _erp_headers():
        h={'Content-Type':'application/json'}
        if _rb.ERP_API_TOKEN:h['Authorization']='Bearer '+_rb.ERP_API_TOKEN
        return h
    return _erp_headers


def install_0063(_rb):
    def send_erp_queue_item(row):
        row.attempts=int(row.attempts or 0)+1
        if not _rb.ERP_SYNC_ENABLED:
            row.status='DISABLED';row.last_error='ERP sync disabled';return False
        if not _rb.ERP_BASE_URL:
            row.status='FAILED';row.last_error='ERP_BASE_URL is empty';return False
        try:
            payload=_rb.json.loads(row.payload_json or '{}')
            payload.update({'event_type':row.event_type,'reference_type':row.reference_type,'reference_id':row.reference_id,'provider':_rb.ERP_PROVIDER})
            r=_rb.requests.post(_rb.ERP_BASE_URL+'/ris/events',json=payload,headers=_rb._erp_headers(),timeout=_rb.ERP_TIMEOUT)
            r.raise_for_status()
            row.status='SENT';row.sent_at=_rb.datetime.utcnow();row.last_error=''
            return True
        except Exception as e:
            row.status='FAILED';row.last_error=str(e)[:1000]
            return False
    return send_erp_queue_item


def install_0064(_rb):
    def process_erp_queue(limit=50):
        rows=_rb.ERPSyncQueue.query.filter(_rb.ERPSyncQueue.status.in_(['PENDING','FAILED']),_rb.ERPSyncQueue.attempts<5).order_by(_rb.ERPSyncQueue.id.asc()).limit(limit).all()
        for row in rows:_rb.send_erp_queue_item(row)
        _rb.db.session.commit()
        return len(rows)
    return process_erp_queue


def install_0283(_rb):
    def _warehouse_code_part(value):
        import re
        value=(value or '').strip().upper()
        value=re.sub(r'[^A-Z0-9]+','-',value).strip('-')
        return value[:30] or 'BRANCH'
    return _warehouse_code_part


def install_0284(_rb):
    def ensure_main_warehouse():
        main=_rb.Warehouse.query.filter_by(warehouse_type='MAIN',active=True).order_by(_rb.Warehouse.id).first()
        if main:
            return main,False
        code='MAIN'
        existing=_rb.Warehouse.query.filter_by(code=code).first()
        if existing:
            existing.warehouse_type='MAIN'
            existing.active=True
            existing.branch_id=None
            return existing,False
        main=_rb.Warehouse(code='MAIN',name='Main Warehouse',warehouse_type='MAIN',branch_id=None,parent_id=None,active=True)
        _rb.db.session.add(main)
        _rb.db.session.flush()
        return main,True
    return ensure_main_warehouse


def install_0285(_rb):
    def ensure_branch_warehouses():
        main,main_created=_rb.ensure_main_warehouse()
        created=[]
        reused=[]
        branches=_rb.Branch.query.filter_by(active=True).order_by(_rb.Branch.id).all()

        for branch in branches:
            current=_rb.Warehouse.query.filter_by(branch_id=branch.id,warehouse_type='BRANCH',active=True).order_by(_rb.Warehouse.id).first()
            if current:
                if not current.parent_id:
                    current.parent_id=main.id
                reused.append(current)
                continue

            base='BR-'+_rb._warehouse_code_part(getattr(branch,'code',None) or branch.name or str(branch.id))
            code=base
            n=1
            while _rb.Warehouse.query.filter_by(code=code).first():
                n+=1
                code=f'{base[:25]}-{n}'

            wh=_rb.Warehouse(
                code=code,
                name=f'{branch.name} Warehouse',
                warehouse_type='BRANCH',
                branch_id=branch.id,
                parent_id=main.id,
                active=True
            )
            _rb.db.session.add(wh)
            _rb.db.session.flush()
            created.append(wh)

        return {
            'main':main,
            'main_created':main_created,
            'created':created,
            'reused':reused,
            'branches':branches
        }
    return ensure_branch_warehouses


def install_0287(_rb):
    def default_warehouse_for_order(order):
        row=_rb.Warehouse.query.filter_by(branch_id=order.branch_id,warehouse_type='BRANCH',active=True).order_by(_rb.Warehouse.id).first()
        if row:return row
        return _rb.Warehouse.query.filter_by(branch_id=order.branch_id,active=True).order_by(_rb.Warehouse.id).first()
    return default_warehouse_for_order


def install_0288(_rb):
    def stock_lots(warehouse_id,item_id):
        from datetime import date as _date
        return _rb.InventoryLot.query.filter_by(warehouse_id=warehouse_id,item_id=item_id).filter(
            _rb.InventoryLot.qty_on_hand>0,
            _rb.db.or_(_rb.InventoryLot.expiry_date.is_(None),_rb.InventoryLot.expiry_date>=_date.today())
        ).order_by(_rb.db.case((_rb.InventoryLot.expiry_date.is_(None),1),else_=0),
            _rb.InventoryLot.expiry_date,_rb.InventoryLot.id).populate_existing().with_for_update().all()
    return stock_lots


def install_0289(_rb):
    def inventory_available_qty(warehouse_id,item_id):
        from datetime import date as _date
        rows=_rb.InventoryLot.query.filter_by(warehouse_id=warehouse_id,item_id=item_id).filter(
            _rb.db.or_(_rb.InventoryLot.expiry_date.is_(None),_rb.InventoryLot.expiry_date>=_date.today())
        ).all()
        return round(sum(max(0,float(x.qty_on_hand or 0)-float(x.qty_reserved or 0)) for x in rows),4)
    return inventory_available_qty


def install_0290(_rb):
    def inventory_on_hand_qty(warehouse_id,item_id):
        return round(sum(float(x.qty_on_hand or 0) for x in _rb.InventoryLot.query.filter_by(warehouse_id=warehouse_id,item_id=item_id).all()),4)
    return inventory_on_hand_qty


def install_0291(_rb):
    def inventory_move(warehouse,item,qty,movement_type,lot=None,unit_cost=None,reference_type='',reference_id=None,notes='',user=None):
        qty=float(qty or 0)
        if qty==0:return None
        user=user or _rb.current_user()
        lot=lot or _rb.InventoryLot.query.filter_by(warehouse_id=warehouse.id,item_id=item.id,lot_no='').first()
        if not lot:
            lot=_rb.InventoryLot(item_id=item.id,warehouse_id=warehouse.id,lot_no='',unit_cost=float(unit_cost or item.default_cost or 0),qty_on_hand=0)
            _rb.db.session.add(lot);_rb.db.session.flush()
        if unit_cost is not None:lot.unit_cost=float(unit_cost or 0)
        lot.qty_on_hand=float(lot.qty_on_hand or 0)+qty
        if lot.qty_on_hand < -1e-9:
            raise ValueError(f'Insufficient stock for {item.name} in {warehouse.name}')
        m=_rb.WarehouseStockMovement(warehouse_id=warehouse.id,item_id=item.id,lot_id=lot.id,movement_type=movement_type,
            qty=qty,unit_cost=float(lot.unit_cost or item.default_cost or 0),reference_type=reference_type,
            reference_id=reference_id,notes=notes,created_by=getattr(user,'id',None))
        _rb.db.session.add(m)
        return m
    return inventory_move


def install_0292(_rb):
    def consume_inventory(order,item,qty,usage_type='USED',source='MANUAL',reason='',warehouse=None,user=None):
        warehouse=warehouse or _rb.default_warehouse_for_order(order)
        if not warehouse:raise ValueError('No active warehouse is configured for this branch.')
        from inventory_safety import quantity,lock_order
        qty=quantity(qty)
        lock_order(order)
        user=user or _rb.current_user()
        lots=_rb.stock_lots(warehouse.id,item.id)
        available_total=sum(max(0,float(lot.qty_on_hand or 0)-float(lot.qty_reserved or 0)) for lot in lots)
        if qty>available_total+1e-9:raise ValueError('Insufficient unexpired available stock. / المخزون المتاح غير المنتهي لا يكفي.')
        remaining=qty; usages=[]
        for lot in lots:
            available=max(0,float(lot.qty_on_hand or 0)-float(lot.qty_reserved or 0))
            take=min(available,remaining)
            if take<=0:continue
            movement_type='WASTE' if usage_type=='WASTE' else 'CONSUMPTION'
            _rb.inventory_move(warehouse,item,-take,movement_type,lot=lot,reference_type='ORDER',reference_id=order.id,notes=reason,user=user)
            usage=_rb.OrderConsumableUsage(order_id=order.id,warehouse_id=warehouse.id,item_id=item.id,lot_id=lot.id,
                qty=take,usage_type=usage_type,source=source,reason=reason,
                unit_cost=float(lot.unit_cost or item.default_cost or 0),created_by=user.id)
            _rb.db.session.add(usage);usages.append(usage);remaining-=take
            if remaining<=1e-9:break
        if remaining>1e-9:raise ValueError(f'Insufficient available stock for {item.name}. Short by {remaining:g} {item.unit}.')
        return usages
    return consume_inventory


def install_0293(_rb):
    def return_inventory(order,item,qty,warehouse=None,reason='',user=None):
        from inventory_safety import return_to_original_lots
        return return_to_original_lots(order,item,qty,warehouse=warehouse,reason=reason,user=user)
    return return_inventory


def install_0294(_rb):
    def order_consumable_cost(order):
        cost=0.0
        for x in _rb.OrderConsumableUsage.query.filter_by(order_id=order.id).all():
            sign=-1 if x.usage_type=='RETURN' else 1
            cost+=sign*float(x.qty or 0)*float(x.unit_cost or 0)
        return round(cost,2)
    return order_consumable_cost


def install_0295(_rb):
    def order_default_consumables(order):
        rows=_rb.ProcedureConsumableDefault.query.filter_by(procedure_id=order.procedure_id,active=True).all()
        used={}
        for u in _rb.OrderConsumableUsage.query.filter_by(order_id=order.id).all():
            if u.usage_type in ('USED','EXTRA','WASTE'):
                used[u.item_id]=used.get(u.item_id,0)+float(u.qty or 0)
            elif u.usage_type=='RETURN':
                used[u.item_id]=used.get(u.item_id,0)-float(u.qty or 0)
        return [{'rule':r,'used':used.get(r.item_id,0)} for r in rows]
    return order_default_consumables


def install_0296(_rb):
    def low_stock_rows(warehouse_id=None):
        q=_rb.WarehouseStockPolicy.query.filter_by(active=True)
        if warehouse_id:q=q.filter_by(warehouse_id=warehouse_id)
        rows=[]
        for p in q.all():
            available=_rb.inventory_available_qty(p.warehouse_id,p.item_id)
            if available<=float(p.reorder_level or p.min_level or 0):
                rows.append({'policy':p,'available':available,'shortage':max(0,float(p.target_level or 0)-available)})
        return rows
    return low_stock_rows

