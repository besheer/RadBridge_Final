"""Runtime-bound web.routes.inventory; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

def install_0169(_rb):
    @_rb.app.route('/nursing/<int:order_id>',methods=['GET','POST'])
    @_rb.require_perm('consumables.use')
    def nursing_case(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        defaults=_rb.ProcedureConsumable.query.filter_by(procedure_id=order.procedure_id).all() if order.procedure_id else []
        if _rb.request.method=='POST':
            if _rb.NursingConsumableEntry.query.filter_by(order_id=order.id,confirmed=True).first():
                _rb.flash('Consumables are already confirmed. Supervisor correction is required for changes.','warning')
                return _rb.redirect(_rb.url_for('nursing_case',order_id=order.id))
            for pc in defaults:
                qty=max(0,float(_rb.request.form.get('qty_'+str(pc.consumable_id)) or 0))
                n=_rb.NursingConsumableEntry.query.filter_by(order_id=order.id,consumable_id=pc.consumable_id).first()
                if not n:
                    n=_rb.NursingConsumableEntry(order_id=order.id,consumable_id=pc.consumable_id); _rb.db.session.add(n)
                n.default_qty=pc.qty; n.actual_qty=qty; n.confirmed=True
                n.confirmed_by=_rb.current_user().id; n.confirmed_at=_rb.datetime.utcnow()
                oc=_rb.OrderConsumable.query.filter_by(order_id=order.id,consumable_id=pc.consumable_id).first()
                if not oc:
                    oc=_rb.OrderConsumable(order_id=order.id,consumable_id=pc.consumable_id,qty=qty,source='NURSING',created_by=_rb.current_user().id); _rb.db.session.add(oc)
                else: oc.qty=qty; oc.source='NURSING'
                item=_rb.Consumable.query.get(pc.consumable_id)
                if item:
                    _rb._record_stock_movement(item,-qty,'NURSING_USAGE',reason='Actual nursing usage',
                        reference_type='order',reference_id=order.id,branch_id=order.branch_id,user_id=_rb.current_user().id)
            _rb.audit('NURSING_CONSUMABLES_CONFIRMED','order',order.id,'Actual quantities confirmed and deducted from stock')
            _rb.db.session.commit(); _rb.flash('Consumables confirmed and stock updated.','success')
            return _rb.redirect(_rb.url_for('nursing_worklist'))
        entries={x.consumable_id:x for x in _rb.NursingConsumableEntry.query.filter_by(order_id=order.id).all()}
        warehouse=_rb.default_warehouse_for_order(order)
        inventory_items=[]
        if warehouse:
            for item in _rb.InventoryItem.query.filter_by(active=True).order_by(_rb.InventoryItem.name).all():
                inventory_items.append({'id':item.id,'name':item.name,'code':item.code,'unit':item.unit,
                                        'available':_rb.inventory_available_qty(warehouse.id,item.id)})
        return _rb.render_template(
            'nursing_case.html',
            order=order,
            defaults=defaults,
            entries=entries,
            inv_wh=warehouse,
            inventory_items=inventory_items,
            image_url=_rb.clinical_image_only_url(order),
            attachments=(
                _rb.Attachment.query
                .filter_by(order_id=order.id)
                .order_by(_rb.Attachment.created_at.desc())
                .all()
            ),
            clinical_notes=(
                _rb.ClinicalNote.query
                .filter_by(order_id=order.id)
                .order_by(_rb.ClinicalNote.created_at.desc())
                .limit(10)
                .all()
            ),
        )
    return nursing_case


def install_0170(_rb):
    @_rb.app.post('/nursing/<int:order_id>/correct')
    @_rb.require_perm('consumables.correct')
    def nursing_consumable_correct(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        reason=_rb.request.form.get('reason','').strip()
        if len(reason)<5:
            _rb.flash('Correction requires a reason.','danger'); return _rb.redirect(_rb.url_for('nursing_case',order_id=order.id))
        entries=_rb.NursingConsumableEntry.query.filter_by(order_id=order.id,confirmed=True).all()
        for n in entries:
            qty=max(0,float(_rb.request.form.get('qty_'+str(n.consumable_id)) or n.actual_qty or 0))
            old=float(n.actual_qty or 0); n.actual_qty=qty; n.corrected_by=_rb.current_user().id; n.corrected_at=_rb.datetime.utcnow(); n.correction_reason=reason
            oc=_rb.OrderConsumable.query.filter_by(order_id=order.id,consumable_id=n.consumable_id).first()
            if oc: oc.qty=qty; oc.source='NURSING_CORRECTION'
            item=_rb.Consumable.query.get(n.consumable_id)
            if item:
                _rb._record_stock_movement(item,(old-qty),'NURSING_CORRECTION',reason=reason,
                    reference_type='order',reference_id=order.id,branch_id=order.branch_id,user_id=_rb.current_user().id)
            _rb.audit('CONSUMABLE_CORRECTION','order',order.id,f'item={n.consumable_id} {old}->{qty}; stock_delta={old-qty}; reason={reason}')
        _rb.db.session.commit(); _rb.flash('Consumable correction saved and audited.','success')
        return _rb.redirect(_rb.url_for('nursing_case',order_id=order.id))
    return nursing_consumable_correct


def install_0171(_rb):
    @_rb.app.route('/admin/procedures/<int:procedure_id>/consumables',methods=['GET','POST'])
    @_rb.require_perm('inventory.manage')
    def procedure_consumables(procedure_id):
        proc=_rb.Procedure.query.get_or_404(procedure_id)
        if _rb.request.method=='POST':
            cid=_rb.request.form.get('consumable_id',type=int); qty=max(0,float(_rb.request.form.get('qty') or 0))
            row=_rb.ProcedureConsumable.query.filter_by(procedure_id=proc.id,consumable_id=cid).first()
            if not row: row=_rb.ProcedureConsumable(procedure_id=proc.id,consumable_id=cid); _rb.db.session.add(row)
            row.qty=qty; _rb.audit('PROCEDURE_CONSUMABLE_DEFAULT','procedure',proc.id,f'consumable={cid} qty={qty}'); _rb.db.session.commit()
            return _rb.redirect(_rb.url_for('procedure_consumables',procedure_id=proc.id))
        return _rb.render_template('procedure_consumables.html',procedure=proc,
          rows=_rb.ProcedureConsumable.query.filter_by(procedure_id=proc.id).all(),
          items=_rb.Consumable.query.filter_by(active=True).order_by(_rb.Consumable.name).all())
    return procedure_consumables


def install_0172(_rb):
    @_rb.app.post('/admin/procedures/<int:procedure_id>/consumables/<int:row_id>/delete')
    @_rb.require_perm('inventory.manage')
    def procedure_consumable_delete(procedure_id,row_id):
        row=_rb.ProcedureConsumable.query.filter_by(id=row_id,procedure_id=procedure_id).first_or_404()
        _rb.audit('PROCEDURE_CONSUMABLE_DEFAULT_DELETE','procedure',procedure_id,f'consumable={row.consumable_id}')
        _rb.db.session.delete(row); _rb.db.session.commit(); _rb.flash('Default consumable removed.','success')
        return _rb.redirect(_rb.url_for('procedure_consumables',procedure_id=procedure_id))
    return procedure_consumable_delete


def install_0181(_rb):
    @_rb.app.post('/technician/<int:order_id>/consume')
    @_rb.require_perm('consumables.use')
    def technician_case_consume(order_id):
        order = _rb.Order.query.get_or_404(order_id)
        from technician_queue import scoped_order, mutable_return
        scoped_order(_rb._reporting_support_sys.modules[_rb.__name__],order)
        mutable_return(_rb._reporting_support_sys.modules[_rb.__name__],order)
        tasks_only=__import__('procedure_staff_workflow').policy(_rb._reporting_support_sys.modules[_rb.__name__],order)['mode']=='TASKS'

        exam_status = (order.exam_status or 'ORDERED').upper()

        # RB_TECHNICIAN_CONSUME_DURING_EXAM_ONLY_V1
        if exam_status != 'IN_PROGRESS' and not tasks_only:
            _rb.flash(
                'Start the examination before recording consumables.',
                'danger',
            )
            return _rb.redirect(_rb.url_for(
                'technician_case_workspace',
                order_id=order.id,
            ))

        try:
            item_id = int(_rb.request.form.get('item_id') or 0)
            qty = float(_rb.request.form.get('qty') or 0)
        except (TypeError, ValueError):
            _rb.flash('Invalid consumable or quantity.', 'danger')
            return _rb.redirect(_rb.url_for(
                'technician_case_workspace',
                order_id=order.id,
            ))

        item = _rb.InventoryItem.query.get_or_404(item_id)
        warehouse = _rb.default_warehouse_for_order(order)
        reason = (_rb.request.form.get('reason') or '').strip()

        try:
            _rb.consume_inventory(
                order,
                item,
                qty,
                usage_type='USED',
                source='MANUAL',
                reason=reason,
                warehouse=warehouse,
                user=_rb.current_user(),
            )
            _rb.audit(
                'TECHNICIAN_CONSUMABLE_USED',
                'order',
                order.id,
                f'item={item.code}; qty={qty:g}; unit={item.unit}',
            )
            _rb.db.session.commit()
            _rb.flash('Actual consumable usage recorded.', 'success')
        except Exception as exc:
            _rb.db.session.rollback()
            _rb.flash(str(exc), 'danger')

        return _rb.redirect(_rb.url_for(
            'technician_case_workspace',
            order_id=order.id,
        ))
    return technician_case_consume


def install_0563(_rb):
    @_rb.app.route('/admin/inventory',methods=['GET','POST'])
    @_rb.require_perm('inventory.manage')
    def admin_inventory():
        if _rb.request.method=='POST':
            name_en=(_rb.request.form.get('name_en') or _rb.request.form.get('name') or '').strip()
            name_ar=(_rb.request.form.get('name_ar') or '').strip()
            c=_rb.Consumable(code=_rb.request.form['code'].strip().upper(),barcode=(_rb.request.form.get('barcode') or '').strip(),
                         name=name_en or name_ar,name_en=name_en,name_ar=name_ar,category=(_rb.request.form.get('category') or '').strip(),
                         unit=_rb.request.form.get('unit','unit'),stock_qty=float(_rb.request.form.get('stock_qty') or 0),
                         reorder_level=float(_rb.request.form.get('reorder_level') or 0),unit_cost=float(_rb.request.form.get('unit_cost') or 0),
                         selling_price=float(_rb.request.form.get('selling_price') or 0),
                         expiry_tracking=_rb.request.form.get('expiry_tracking')=='1',active=True)
            _rb.db.session.add(c); _rb.audit('CONSUMABLE_CREATE','consumable','',c.code); _rb.db.session.commit(); _rb.flash('Consumable added.','success')
        return _rb.render_template('admin_inventory.html',items=_rb.Consumable.query.order_by(_rb.Consumable.name).all())
    return admin_inventory


def install_0564(_rb):
    @_rb.app.post('/admin/inventory/<int:item_id>/edit')
    @_rb.require_perm('inventory.manage')
    def admin_inventory_edit(item_id):
        c=_rb.Consumable.query.get_or_404(item_id)
        c.name_en=(_rb.request.form.get('name_en') or c.name_en or c.name).strip()
        c.name_ar=(_rb.request.form.get('name_ar') or c.name_ar or '').strip()
        c.name=c.name_en or c.name_ar or c.name
        c.barcode=(_rb.request.form.get('barcode') or c.barcode or '').strip()
        c.category=(_rb.request.form.get('category') or c.category or '').strip()
        c.unit=_rb.request.form.get('unit',c.unit).strip() or c.unit
        c.reorder_level=max(0,float(_rb.request.form.get('reorder_level') or 0))
        c.unit_cost=max(0,float(_rb.request.form.get('unit_cost') or 0))
        c.selling_price=max(0,float(_rb.request.form.get('selling_price') or 0))
        c.expiry_tracking=_rb.request.form.get('expiry_tracking')=='1'
        c.active=_rb.request.form.get('active')=='1'
        _rb.audit('CONSUMABLE_EDITED','consumable',c.id,f'{c.code} active={c.active}')
        _rb.db.session.commit(); _rb.flash('Consumable updated.','success')
        return _rb.redirect(_rb.url_for('admin_inventory'))
    return admin_inventory_edit


def install_0565(_rb):
    @_rb.app.post('/admin/inventory/<int:item_id>/adjust')
    @_rb.require_perm('inventory.manage')
    def admin_inventory_adjust(item_id):
        c=_rb.Consumable.query.get_or_404(item_id)
        delta=float(_rb.request.form.get('delta') or 0)
        reason=_rb.request.form.get('reason','').strip()
        if not reason or len(reason)<5:
            _rb.flash('Stock adjustment requires a reason.','danger'); return _rb.redirect(_rb.url_for('admin_inventory'))
        before=float(c.stock_qty or 0)
        _rb._record_stock_movement(c,delta,'ADJUSTMENT',reason=reason,reference_type='manual_adjustment',
                               reference_id=c.id,user_id=_rb.current_user().id)
        _rb.audit('STOCK_ADJUSTMENT','consumable',c.id,f'{before}->{c.stock_qty}; delta={delta}; reason={reason}')
        _rb.db.session.commit(); _rb.flash('Stock adjustment saved and audited.','success')
        return _rb.redirect(_rb.url_for('admin_inventory'))
    return admin_inventory_adjust


def install_0566(_rb):
    @_rb.app.post('/admin/inventory/seed-defaults')
    @_rb.require_perm('inventory.manage')
    def admin_inventory_seed_defaults():
        added=_rb.seed_default_consumables()
        _rb.audit('CONSUMABLE_DEFAULT_CATALOG_SEED','consumable','',f'added={added}')
        _rb.db.session.commit();_rb.flash(f'Default consumable catalog: {added} item(s) added.','success')
        return _rb.redirect(_rb.url_for('admin_inventory'))
    return admin_inventory_seed_defaults


def install_0567(_rb):
    @_rb.app.route('/admin/inventory/export/<fmt>')
    @_rb.require_perm('inventory.manage')
    def admin_inventory_export(fmt):
        items=_rb.Consumable.query.order_by(_rb.Consumable.code).all()
        if fmt=='csv':
            out=_rb.io.StringIO();w=_rb.csv.DictWriter(out,fieldnames=_rb.INVENTORY_IMPORT_COLUMNS);w.writeheader()
            for c in items:w.writerow(_rb.inventory_row(c))
            return _rb.send_file(_rb.io.BytesIO(out.getvalue().encode('utf-8-sig')),as_attachment=True,download_name='inventory-master.csv',mimetype='text/csv')
        if fmt=='xlsx':
            wb=_rb.Workbook();ws=wb.active;ws.title='Inventory Master';ws.append(_rb.INVENTORY_IMPORT_COLUMNS)
            for c in items:
                row=_rb.inventory_row(c);ws.append([row[x] for x in _rb.INVENTORY_IMPORT_COLUMNS])
            for cell in ws[1]:cell.font=_rb.Font(bold=True,color='FFFFFF');cell.fill=_rb.PatternFill('solid',fgColor='1F4E78')
            for i in range(1,len(_rb.INVENTORY_IMPORT_COLUMNS)+1):ws.column_dimensions[_rb.get_column_letter(i)].width=20
            buf=_rb.io.BytesIO();wb.save(buf);buf.seek(0)
            return _rb.send_file(buf,as_attachment=True,download_name='inventory-master.xlsx',
              mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        _rb.abort(400)
    return admin_inventory_export


def install_0568(_rb):
    @_rb.app.route('/admin/inventory/import-template')
    @_rb.require_perm('inventory.manage')
    def admin_inventory_import_template():
        wb=_rb.Workbook();ws=wb.active;ws.title='Inventory Import';ws.append(_rb.INVENTORY_IMPORT_COLUMNS)
        for x in _rb.DEFAULT_CONSUMABLE_CATALOG[:3]:
            row={k:'' for k in _rb.INVENTORY_IMPORT_COLUMNS}
            row.update(x);row.update({'stock_qty':0,'reorder_level':0,'unit_cost':0,'selling_price':0,'expiry_tracking':0,'active':1})
            ws.append([row[c] for c in _rb.INVENTORY_IMPORT_COLUMNS])
        for cell in ws[1]:cell.font=_rb.Font(bold=True,color='FFFFFF');cell.fill=_rb.PatternFill('solid',fgColor='1F4E78')
        for i in range(1,len(_rb.INVENTORY_IMPORT_COLUMNS)+1):ws.column_dimensions[_rb.get_column_letter(i)].width=22
        buf=_rb.io.BytesIO();wb.save(buf);buf.seek(0)
        return _rb.send_file(buf,as_attachment=True,download_name='inventory-import-template.xlsx',
          mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    return admin_inventory_import_template


def install_0569(_rb):
    @_rb.app.post('/admin/inventory/import')
    @_rb.require_perm('inventory.manage')
    def admin_inventory_import():
        f=_rb.request.files.get('file')
        if not f or not f.filename:
            _rb.flash('Select CSV or XLSX file.','danger');return _rb.redirect(_rb.url_for('admin_inventory'))
        rows=[]
        name=f.filename.lower()
        if name.endswith('.csv'):
            content=f.read().decode('utf-8-sig')
            rows=list(_rb.csv.DictReader(_rb.io.StringIO(content)))
        elif name.endswith('.xlsx'):
            wb=_rb.load_workbook(f,read_only=True,data_only=True);ws=wb.active
            values=list(ws.iter_rows(values_only=True))
            if values:
                headers=[str(x or '').strip() for x in values[0]]
                rows=[dict(zip(headers,r)) for r in values[1:] if any(x is not None for x in r)]
        else:
            _rb.flash('Only CSV/XLSX supported.','danger');return _rb.redirect(_rb.url_for('admin_inventory'))

        created=updated=0
        for r in rows:
            code=str(r.get('code') or '').strip().upper()
            if not code:continue
            c=_rb.Consumable.query.filter_by(code=code).first()
            if not c:
                c=_rb.Consumable(code=code,name=str(r.get('name_en') or r.get('name_ar') or code));_rb.db.session.add(c);created+=1
            else:updated+=1
            c.barcode=str(r.get('barcode') or c.barcode or '').strip()
            c.name_en=str(r.get('name_en') or c.name_en or c.name or '').strip()
            c.name_ar=str(r.get('name_ar') or c.name_ar or '').strip()
            c.name=c.name_en or c.name_ar or c.name
            c.category=str(r.get('category') or c.category or '').strip()
            c.unit=str(r.get('unit') or c.unit or 'unit').strip()
            for fld in ['stock_qty','reorder_level','unit_cost','selling_price']:
                try:setattr(c,fld,float(r.get(fld) if r.get(fld) not in (None,'') else getattr(c,fld) or 0))
                except:pass
            c.expiry_tracking=str(r.get('expiry_tracking') or '0').strip().lower() in ('1','true','yes','y')
            c.active=str(r.get('active') if r.get('active') not in (None,'') else '1').strip().lower() in ('1','true','yes','y')
        _rb.audit('INVENTORY_IMPORT','consumable','',f'created={created} updated={updated} file={f.filename}')
        _rb.db.session.commit();_rb.flash(f'Import complete. Created {created}, updated {updated}.','success')
        return _rb.redirect(_rb.url_for('admin_inventory'))
    return admin_inventory_import


def install_0570(_rb):
    @_rb.app.route('/admin/inventory/movements')
    @_rb.require_perm('inventory.manage')
    def admin_inventory_movements():
        return _rb.render_template('inventory_movements.html',
          rows=_rb.StockMovement.query.order_by(_rb.StockMovement.id.desc()).limit(1000).all())
    return admin_inventory_movements


def install_0571(_rb):
    @_rb.app.route('/admin/inventory/batches',methods=['GET','POST'])
    @_rb.require_perm('inventory.manage')
    def admin_inventory_batches():
        if _rb.request.method=='POST':
            cid=_rb.request.form.get('consumable_id',type=int);item=_rb.Consumable.query.get_or_404(cid)
            batch=(_rb.request.form.get('batch_no') or '').strip()
            try:exp=_rb.date.fromisoformat(_rb.request.form.get('expiry_date')) if _rb.request.form.get('expiry_date') else None
            except:exp=None
            qty=max(0,float(_rb.request.form.get('qty') or 0));cost=max(0,float(_rb.request.form.get('unit_cost') or item.unit_cost or 0))
            row=_rb.InventoryBatch(consumable_id=item.id,batch_no=batch,expiry_date=exp,qty=qty,unit_cost=cost,
                               branch_id=_rb.request.form.get('branch_id',type=int),active=True)
            _rb.db.session.add(row)
            if qty:
                _rb._record_stock_movement(item,qty,'BATCH_RECEIPT',reason=f'Batch {batch}',reference_type='batch',reference_id=batch,
                                       branch_id=row.branch_id,user_id=_rb.current_user().id)
            _rb.audit('INVENTORY_BATCH_CREATE','consumable',item.id,f'batch={batch} qty={qty} exp={exp}')
            _rb.db.session.commit();_rb.flash('Batch saved.','success');return _rb.redirect(_rb.url_for('admin_inventory_batches'))
        return _rb.render_template('inventory_batches.html',
          rows=_rb.InventoryBatch.query.order_by(_rb.InventoryBatch.expiry_date.asc().nullslast(),_rb.InventoryBatch.id.desc()).limit(1000).all(),
          items=_rb.Consumable.query.filter_by(active=True).order_by(_rb.Consumable.name).all(),
          branches=_rb.Branch.query.order_by(_rb.Branch.name).all())
    return admin_inventory_batches


def install_0572(_rb):
    @_rb.app.route('/admin/erp',methods=['GET','POST'])
    @_rb.require_perm('inventory.manage')
    def admin_erp():
        if _rb.request.method=='POST':
            cid=_rb.request.form.get('consumable_id',type=int)
            code=(_rb.request.form.get('erp_item_code') or '').strip()
            if cid and code:
                row=_rb.ERPItemMapping.query.filter_by(consumable_id=cid).first()
                if not row:row=_rb.ERPItemMapping(consumable_id=cid,erp_item_code=code);_rb.db.session.add(row)
                row.erp_item_code=code;row.erp_warehouse_code=(_rb.request.form.get('erp_warehouse_code') or '').strip();row.active=True
                _rb.audit('ERP_ITEM_MAPPING','consumable',cid,f'erp={code}')
                _rb.db.session.commit()
            return _rb.redirect(_rb.url_for('admin_erp'))
        return _rb.render_template('admin_erp.html',
          mappings=_rb.ERPItemMapping.query.order_by(_rb.ERPItemMapping.id.desc()).all(),
          queue=_rb.ERPSyncQueue.query.order_by(_rb.ERPSyncQueue.id.desc()).limit(300).all(),
          items=_rb.Consumable.query.filter_by(active=True).order_by(_rb.Consumable.name).all(),
          erp_enabled=_rb.ERP_SYNC_ENABLED,erp_provider=_rb.ERP_PROVIDER,erp_base_url=_rb.ERP_BASE_URL)
    return admin_erp


def install_0573(_rb):
    @_rb.app.post('/admin/erp/process')
    @_rb.require_perm('inventory.manage')
    def admin_erp_process():
        count=_rb.process_erp_queue()
        _rb.flash(f'Processed {count} ERP queue item(s).','success')
        return _rb.redirect(_rb.url_for('admin_erp'))
    return admin_erp_process


def install_0574(_rb):
    @_rb.app.post('/admin/erp/sync-items')
    @_rb.require_perm('inventory.manage')
    def admin_erp_sync_items():
        count=0
        for c in _rb.Consumable.query.filter_by(active=True).all():
            mp=_rb.ERPItemMapping.query.filter_by(consumable_id=c.id,active=True).first()
            _rb.queue_erp_event('ITEM_MASTER','consumable',c.id,{
              'ris_item_code':c.code,'erp_item_code':mp.erp_item_code if mp else '',
              'barcode':c.barcode,'name_en':c.name_en or c.name,'name_ar':c.name_ar,
              'category':c.category,'unit':c.unit,'unit_cost':float(c.unit_cost or 0),
              'selling_price':float(c.selling_price or 0),'stock_qty':float(c.stock_qty or 0)
            });count+=1
        _rb.db.session.commit()
        _rb.flash(f'Queued {count} item master record(s) for ERP sync.','success')
        return _rb.redirect(_rb.url_for('admin_erp'))
    return admin_erp_sync_items


def install_0785(_rb):
    @_rb.app.route('/inventory/warehouses',methods=['GET','POST'])
    @_rb.require_perm('inventory.manage')
    def inventory_warehouses():
        if _rb.request.method=='POST':
            code=(_rb.request.form.get('code') or '').strip().upper()
            name=(_rb.request.form.get('name') or '').strip()
            if not code or not name:
                _rb.flash('Warehouse code and name are required.','danger'); return _rb.redirect(_rb.url_for('inventory_warehouses'))
            if _rb.Warehouse.query.filter_by(code=code).first():
                _rb.flash('Warehouse code already exists.','danger'); return _rb.redirect(_rb.url_for('inventory_warehouses'))
            row=_rb.Warehouse(code=code,name=name,warehouse_type=(_rb.request.form.get('warehouse_type') or 'BRANCH').upper(),
                branch_id=_rb.request.form.get('branch_id',type=int),parent_id=_rb.request.form.get('parent_id',type=int),active=True)
            _rb.db.session.add(row);_rb.db.session.commit()
            _rb.audit('WAREHOUSE_CREATE','warehouse',row.id,row.code)
            return _rb.redirect(_rb.url_for('inventory_warehouses'))
        return _rb.render_template('inventory_warehouses.html',
            rows=_rb.Warehouse.query.order_by(_rb.Warehouse.warehouse_type,_rb.Warehouse.name).all(),
            branches=_rb.Branch.query.filter_by(active=True).order_by(_rb.Branch.name).all())
    return inventory_warehouses


def install_0786(_rb):
    @_rb.app.route('/inventory/items',methods=['GET','POST'])
    @_rb.require_perm('inventory.manage')
    def inventory_items():
        if _rb.request.method=='POST':
            code=(_rb.request.form.get('code') or '').strip().upper()
            name=(_rb.request.form.get('name') or '').strip()
            if not code or not name:
                _rb.flash('Item code and name are required.','danger'); return _rb.redirect(_rb.url_for('inventory_items'))
            if _rb.InventoryItem.query.filter_by(code=code).first():
                _rb.flash('Item code already exists.','danger'); return _rb.redirect(_rb.url_for('inventory_items'))
            row=_rb.InventoryItem(code=code,name=name,category=(_rb.request.form.get('category') or 'GENERAL').upper(),
                unit=(_rb.request.form.get('unit') or 'EA').upper(),track_lot=_rb.request.form.get('track_lot')=='1',
                track_expiry=_rb.request.form.get('track_expiry')=='1',default_cost=max(0,_rb.request.form.get('default_cost',type=float) or 0),
                active=True)
            _rb.db.session.add(row);_rb.db.session.commit();_rb.audit('INVENTORY_ITEM_CREATE','inventory_item',row.id,row.code)
            return _rb.redirect(_rb.url_for('inventory_items'))
        return _rb.render_template('inventory_items.html',rows=_rb.InventoryItem.query.order_by(_rb.InventoryItem.category,_rb.InventoryItem.name).all())
    return inventory_items


def install_0787(_rb):
    @_rb.app.post('/inventory/migrate-legacy-items')
    @_rb.require_perm('inventory.manage')
    def inventory_migrate_legacy_items():
        added=0
        for c in _rb.Consumable.query.filter_by(active=True).all():
            code=(c.code or f'LEGACY-{c.id}').strip().upper()
            row=_rb.InventoryItem.query.filter_by(code=code).first()
            if not row:
                row=_rb.InventoryItem(code=code,name=(c.name_en or c.name or c.name_ar or code),
                    category=(c.category or 'GENERAL').upper(),unit=(c.unit or 'EA').upper(),
                    track_expiry=bool(c.expiry_tracking),default_cost=float(c.unit_cost or 0),active=True)
                _rb.db.session.add(row);_rb.db.session.flush();added+=1
        _rb.db.session.commit();_rb.audit('LEGACY_INVENTORY_ITEM_MIGRATION','inventory_item','',f'added={added}')
        _rb.flash(f'{added} legacy item(s) copied to multi-warehouse catalog.','success')
        return _rb.redirect(_rb.url_for('inventory_items'))
    return inventory_migrate_legacy_items


def install_0788(_rb):
    @_rb.app.route('/inventory/stock',methods=['GET','POST'])
    @_rb.require_perm('inventory.view')
    def inventory_stock():
        warehouse_id=_rb.request.args.get('warehouse_id',type=int) or _rb.request.form.get('warehouse_id',type=int)
        if _rb.request.method=='POST':
            if not _rb.has_perm('inventory.adjust_quantity'): _rb.abort(403)
            item_id=_rb.request.form.get('item_id',type=int); qty=_rb.request.form.get('qty',type=float) or 0
            movement=(_rb.request.form.get('movement_type') or 'RECEIPT').upper()
            reason=(_rb.request.form.get('reason') or '').strip()
            if not warehouse_id or not item_id or qty<=0 or not reason:
                _rb.flash('Warehouse, item, quantity and reason are required.','danger'); return _rb.redirect(_rb.url_for('inventory_stock',warehouse_id=warehouse_id))
            wh=_rb.Warehouse.query.get_or_404(warehouse_id);item=_rb.InventoryItem.query.get_or_404(item_id)
            lot_no=(_rb.request.form.get('lot_no') or '').strip()
            expiry=None
            if _rb.request.form.get('expiry_date'):
                try:expiry=_rb.datetime.strptime(_rb.request.form.get('expiry_date'),'%Y-%m-%d').date()
                except Exception:pass
            lot=_rb.InventoryLot.query.filter_by(item_id=item.id,warehouse_id=wh.id,lot_no=lot_no).first()
            if not lot:
                lot=_rb.InventoryLot(item_id=item.id,warehouse_id=wh.id,lot_no=lot_no,expiry_date=expiry,
                    unit_cost=_rb.request.form.get('unit_cost',type=float) or item.default_cost,qty_on_hand=0)
                _rb.db.session.add(lot);_rb.db.session.flush()
            delta=qty if movement in ('RECEIPT','RETURN','ADJUSTMENT_IN') else -qty
            _rb.inventory_move(wh,item,delta,'RECEIPT' if delta>0 else 'ADJUSTMENT',lot=lot,
                unit_cost=_rb.request.form.get('unit_cost',type=float),reference_type='MANUAL',notes=reason)
            _rb.db.session.commit();_rb.audit('WAREHOUSE_STOCK_ADJUST','warehouse',wh.id,f'{item.code} {delta}')
            return _rb.redirect(_rb.url_for('inventory_stock',warehouse_id=wh.id))
        warehouses=_rb.Warehouse.query.filter_by(active=True).order_by(_rb.Warehouse.name).all()
        rows=[]
        if warehouse_id:
            wh=_rb.Warehouse.query.get(warehouse_id)
            for item in _rb.InventoryItem.query.filter_by(active=True).order_by(_rb.InventoryItem.name).all():
                qty=_rb.inventory_on_hand_qty(warehouse_id,item.id);avail=_rb.inventory_available_qty(warehouse_id,item.id)
                policy=_rb.WarehouseStockPolicy.query.filter_by(warehouse_id=warehouse_id,item_id=item.id,active=True).first()
                rows.append({'item':item,'qty':qty,'available':avail,'policy':policy})
        return _rb.render_template('inventory_stock.html',warehouses=warehouses,warehouse_id=warehouse_id,rows=rows,
            items=_rb.InventoryItem.query.filter_by(active=True).order_by(_rb.InventoryItem.name).all())
    return inventory_stock


def install_0789(_rb):
    @_rb.app.route('/inventory/stock-policies',methods=['GET','POST'])
    @_rb.require_perm('inventory.manage')
    def inventory_stock_policies():
        if _rb.request.method=='POST':
            wh=_rb.request.form.get('warehouse_id',type=int);item=_rb.request.form.get('item_id',type=int)
            if not wh or not item:
                _rb.flash('Warehouse and item are required.','danger');return _rb.redirect(_rb.url_for('inventory_stock_policies'))
            row=_rb.WarehouseStockPolicy.query.filter_by(warehouse_id=wh,item_id=item).first()
            if not row:row=_rb.WarehouseStockPolicy(warehouse_id=wh,item_id=item);_rb.db.session.add(row)
            row.min_level=max(0,_rb.request.form.get('min_level',type=float) or 0)
            row.reorder_level=max(0,_rb.request.form.get('reorder_level',type=float) or 0)
            row.target_level=max(0,_rb.request.form.get('target_level',type=float) or 0);row.active=True
            _rb.db.session.commit();return _rb.redirect(_rb.url_for('inventory_stock_policies'))
        return _rb.render_template('inventory_stock_policies.html',rows=_rb.WarehouseStockPolicy.query.order_by(_rb.WarehouseStockPolicy.warehouse_id).all(),
            warehouses=_rb.Warehouse.query.filter_by(active=True).order_by(_rb.Warehouse.name).all(),
            items=_rb.InventoryItem.query.filter_by(active=True).order_by(_rb.InventoryItem.name).all(),
            low_rows=_rb.low_stock_rows())
    return inventory_stock_policies


def install_0790(_rb):
    @_rb.app.route('/inventory/procedure-defaults',methods=['GET','POST'])
    @_rb.require_perm('inventory.manage')
    def inventory_procedure_defaults():
        if _rb.request.method=='POST':
            proc=_rb.request.form.get('procedure_id',type=int);item=_rb.request.form.get('item_id',type=int)
            if not proc or not item:
                _rb.flash('Procedure and item are required.','danger');return _rb.redirect(_rb.url_for('inventory_procedure_defaults'))
            row=_rb.ProcedureConsumableDefault.query.filter_by(procedure_id=proc,item_id=item).first()
            if not row:row=_rb.ProcedureConsumableDefault(procedure_id=proc,item_id=item);_rb.db.session.add(row)
            row.qty=max(0.0001,_rb.request.form.get('qty',type=float) or 1);row.required=_rb.request.form.get('required')=='1';row.active=True
            _rb.db.session.commit();return _rb.redirect(_rb.url_for('inventory_procedure_defaults'))
        return _rb.render_template('inventory_procedure_defaults.html',rows=_rb.ProcedureConsumableDefault.query.order_by(_rb.ProcedureConsumableDefault.procedure_id).all(),
            procedures=_rb.Procedure.query.filter_by(active=True).order_by(_rb.Procedure.modality,_rb.Procedure.name).all(),
            items=_rb.InventoryItem.query.filter_by(active=True).order_by(_rb.InventoryItem.name).all())
    return inventory_procedure_defaults


def install_0791(_rb):
    @_rb.app.route('/inventory/transfers',methods=['GET','POST'])
    @_rb.require_perm('inventory.view')
    def inventory_transfers():
        if _rb.request.method=='POST':
            if not _rb.has_perm('inventory.transfer.request'): _rb.abort(403)
            source=_rb.request.form.get('source_warehouse_id',type=int);target=_rb.request.form.get('target_warehouse_id',type=int)
            if not source or not target or source==target:
                _rb.flash('Select different source and target warehouses.','danger');return _rb.redirect(_rb.url_for('inventory_transfers'))
            tr=_rb.StockTransfer(transfer_no=_rb.next_transfer_no(),source_warehouse_id=source,target_warehouse_id=target,
                status='REQUESTED',requested_by=_rb.current_user().id,notes=(_rb.request.form.get('notes') or '').strip())
            _rb.db.session.add(tr);_rb.db.session.flush()
            item_ids=_rb.request.form.getlist('item_id');qtys=_rb.request.form.getlist('qty')
            count=0
            for raw_item,raw_qty in zip(item_ids,qtys):
                try:item_id=int(raw_item);qty=float(raw_qty)
                except Exception:continue
                if qty<=0:continue
                _rb.db.session.add(_rb.StockTransferLine(transfer_id=tr.id,item_id=item_id,qty_requested=qty));count+=1
            if not count:
                _rb.db.session.rollback();_rb.flash('Add at least one transfer item.','danger');return _rb.redirect(_rb.url_for('inventory_transfers'))
            _rb.audit('STOCK_TRANSFER_REQUEST','stock_transfer',tr.id,tr.transfer_no);_rb.db.session.commit()
            return _rb.redirect(_rb.url_for('inventory_transfer_detail',transfer_id=tr.id))
        return _rb.render_template('inventory_transfers.html',
            rows=_rb.StockTransfer.query.order_by(_rb.StockTransfer.id.desc()).limit(300).all(),
            warehouses=_rb.Warehouse.query.filter_by(active=True).order_by(_rb.Warehouse.name).all(),
            items=_rb.InventoryItem.query.filter_by(active=True).order_by(_rb.InventoryItem.name).all())
    return inventory_transfers


def install_0792(_rb):
    @_rb.app.get('/inventory/transfers/<int:transfer_id>')
    @_rb.require_perm('inventory.view')
    def inventory_transfer_detail(transfer_id):
        row=_rb.StockTransfer.query.get_or_404(transfer_id)
        lines=_rb.StockTransferLine.query.filter_by(transfer_id=row.id).order_by(_rb.StockTransferLine.id).all()
        return _rb.render_template('inventory_transfer_detail.html',row=row,lines=lines)
    return inventory_transfer_detail


def install_0793(_rb):
    @_rb.app.post('/inventory/transfers/<int:transfer_id>/approve')
    @_rb.require_perm('inventory.transfer.approve')
    def inventory_transfer_approve(transfer_id):
        row=_rb.StockTransfer.query.get_or_404(transfer_id)
        workflow=_rb.app.extensions['radbridge_stock_transfer_workflow']
        try:
            workflow.approve(row,actor_id=_rb.current_user().id,occurred_at=_rb.datetime.utcnow())
        except workflow.error_type as e:
            _rb.flash(str(e),'warning');return _rb.redirect(_rb.url_for('inventory_transfer_detail',transfer_id=row.id))
        _rb.db.session.commit()
        return _rb.redirect(_rb.url_for('inventory_transfer_detail',transfer_id=row.id))
    return inventory_transfer_approve


def install_0794(_rb):
    @_rb.app.post('/inventory/transfers/<int:transfer_id>/reject')
    @_rb.require_perm('inventory.transfer.approve')
    def inventory_transfer_reject(transfer_id):
        row=_rb.StockTransfer.query.get_or_404(transfer_id)
        workflow=_rb.app.extensions['radbridge_stock_transfer_workflow']
        try:
            workflow.reject(row,actor_id=_rb.current_user().id,occurred_at=_rb.datetime.utcnow(),
                            reason=_rb.request.form.get('reason') or '')
        except workflow.error_type as e:
            _rb.flash(str(e),'warning');return _rb.redirect(_rb.url_for('inventory_transfer_detail',transfer_id=row.id))
        _rb.db.session.commit()
        return _rb.redirect(_rb.url_for('inventory_transfer_detail',transfer_id=row.id))
    return inventory_transfer_reject


def install_0795(_rb):
    @_rb.app.post('/inventory/transfers/<int:transfer_id>/dispatch')
    @_rb.require_perm('inventory.transfer.dispatch')
    def inventory_transfer_dispatch(transfer_id):
        row=_rb.StockTransfer.query.get_or_404(transfer_id)
        try:
            workflow=_rb.app.extensions['radbridge_stock_transfer_workflow']
            workflow.dispatch(row,actor_id=_rb.current_user().id,occurred_at=_rb.datetime.utcnow())
            _rb.db.session.commit()
        except Exception as e:
            _rb.db.session.rollback();_rb.flash(str(e),'danger')
        return _rb.redirect(_rb.url_for('inventory_transfer_detail',transfer_id=row.id))
    return inventory_transfer_dispatch


def install_0796(_rb):
    @_rb.app.post('/inventory/transfers/<int:transfer_id>/receive')
    @_rb.require_perm('inventory.transfer.receive')
    def inventory_transfer_receive(transfer_id):
        row=_rb.StockTransfer.query.get_or_404(transfer_id)
        workflow=_rb.app.extensions['radbridge_stock_transfer_workflow']
        try:
            workflow.receive(row,actor_id=_rb.current_user().id,occurred_at=_rb.datetime.utcnow())
        except workflow.error_type as e:
            _rb.flash(str(e),'danger');return _rb.redirect(_rb.url_for('inventory_transfer_detail',transfer_id=row.id))
        _rb.db.session.commit()
        return _rb.redirect(_rb.url_for('inventory_transfer_detail',transfer_id=row.id))
    return inventory_transfer_receive


def install_0797(_rb):
    @_rb.app.get('/orders/<int:order_id>/consumables/available-stock')
    @_rb.require_perm('inventory.view')
    def order_consumables_available_stock(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        warehouse=_rb.default_warehouse_for_order(order)
        if not warehouse:
            return _rb.jsonify({'ok':False,'warehouse':None,'items':[]})
        items=[]
        for item in _rb.InventoryItem.query.filter_by(active=True).order_by(_rb.InventoryItem.name).all():
            qty=_rb.inventory_available_qty(warehouse.id,item.id)
            items.append({'id':item.id,'code':item.code,'name':item.name,'unit':item.unit,'available':qty})
        return _rb.jsonify({'ok':True,'warehouse':{'id':warehouse.id,'name':warehouse.name},'items':items})
    return order_consumables_available_stock


def install_0798(_rb):
    @_rb.app.route('/orders/<int:order_id>/consumables',methods=['GET','POST'])
    @_rb.require_perm('inventory.view')
    def order_consumables(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        warehouse=_rb.default_warehouse_for_order(order)
        if _rb.request.method=='POST':
            action=(_rb.request.form.get('action') or 'CONSUME').upper()
            item=_rb.InventoryItem.query.get_or_404(_rb.request.form.get('item_id',type=int))
            qty=_rb.request.form.get('qty',type=float) or 0
            reason=(_rb.request.form.get('reason') or '').strip()
            try:
                if action=='EXTRA':
                    if not _rb.has_perm('inventory.add_extra_consumable'):_rb.abort(403)
                    if not reason:raise ValueError('Extra consumable requires a reason.')
                    _rb.consume_inventory(order,item,qty,usage_type='EXTRA',source='MANUAL',reason=reason,warehouse=warehouse)
                elif action=='WASTE':
                    if not _rb.has_perm('inventory.waste'):_rb.abort(403)
                    if not reason:raise ValueError('Waste requires a reason.')
                    _rb.consume_inventory(order,item,qty,usage_type='WASTE',source='MANUAL',reason=reason,warehouse=warehouse)
                elif action=='RETURN':
                    if not _rb.has_perm('inventory.return'):_rb.abort(403)
                    if not reason:raise ValueError('Return requires a reason.')
                    _rb.return_inventory(order,item,qty,warehouse=warehouse,reason=reason)
                else:
                    if not _rb.has_perm('inventory.consume'):_rb.abort(403)
                    _rb.consume_inventory(order,item,qty,usage_type='USED',source='MANUAL',reason=reason,warehouse=warehouse)
                _rb.db.session.commit();_rb.audit('ORDER_CONSUMABLE_'+action,'order',order.id,f'{item.code} x{qty} {reason}')
                _rb.flash('Consumable movement saved.','success')
            except Exception as e:
                _rb.db.session.rollback();_rb.flash(str(e),'danger')
            return _rb.redirect(_rb.url_for('order_consumables',order_id=order.id))
        usage=_rb.OrderConsumableUsage.query.filter_by(order_id=order.id).order_by(_rb.OrderConsumableUsage.id.desc()).all()
        return _rb.render_template('order_consumables.html',order=order,warehouse=warehouse,defaults=_rb.order_default_consumables(order),
            usage=usage,items=_rb.InventoryItem.query.filter_by(active=True).order_by(_rb.InventoryItem.name).all(),
            total_cost=_rb.order_consumable_cost(order))
    return order_consumables


def install_0799(_rb):
    @_rb.app.post('/orders/<int:order_id>/consumables/apply-defaults')
    @_rb.require_perm('inventory.consume')
    def order_consumables_apply_defaults(order_id):
        order=_rb.Order.query.get_or_404(order_id);warehouse=_rb.default_warehouse_for_order(order)
        if not warehouse:
            _rb.flash('No branch warehouse configured.','danger');return _rb.redirect(_rb.url_for('order_consumables',order_id=order.id))
        try:
            for x in _rb.order_default_consumables(order):
                needed=max(0,float(x['rule'].qty or 0)-float(x['used'] or 0))
                if needed>1e-9:
                    _rb.consume_inventory(order,x['rule'].item,needed,usage_type='USED',source='DEFAULT',
                        reason='Procedure default consumable',warehouse=warehouse)
            _rb.db.session.commit();_rb.audit('ORDER_DEFAULT_CONSUMABLES_APPLIED','order',order.id,warehouse.name)
            _rb.flash('Default consumables applied.','success')
        except Exception as e:
            _rb.db.session.rollback();_rb.flash(str(e),'danger')
        return _rb.redirect(_rb.url_for('order_consumables',order_id=order.id))
    return order_consumables_apply_defaults


def install_0802(_rb):
    @_rb.app.post('/inventory/warehouses/auto-create')
    @_rb.require_perm('inventory.manage')
    def inventory_warehouses_auto_create():
        result=_rb.ensure_branch_warehouses()
        _rb.db.session.commit()
        _rb.audit(
            'WAREHOUSE_AUTO_CREATE',
            'warehouse',
            result['main'].id,
            f"main_created={result['main_created']} branch_created={len(result['created'])} reused={len(result['reused'])}"
        )
        _rb.flash(
            f"Warehouse sync complete. Main: {result['main'].name}. "
            f"Created {len(result['created'])} branch warehouse(s); "
            f"{len(result['reused'])} existing warehouse(s) kept.",
            'success'
        )
        return _rb.redirect(_rb.url_for('inventory_warehouses'))
    return inventory_warehouses_auto_create


def install_0803(_rb):
    @_rb.app.post('/inventory/warehouses/create-for-branch/<int:branch_id>')
    @_rb.require_perm('inventory.manage')
    def inventory_create_for_branch(branch_id):
        branch=_rb.Branch.query.get_or_404(branch_id)
        main,_=_rb.ensure_main_warehouse()

        existing=_rb.Warehouse.query.filter_by(
            branch_id=branch.id,
            warehouse_type='BRANCH',
            active=True
        ).order_by(_rb.Warehouse.id).first()

        if existing:
            if not existing.parent_id:
                existing.parent_id=main.id
                _rb.db.session.commit()
            _rb.flash(f'{branch.name} already has warehouse: {existing.name}','info')
            return _rb.redirect(_rb.request.referrer or _rb.url_for('inventory_warehouses'))

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
        _rb.db.session.commit()
        _rb.audit('WAREHOUSE_CREATE_FOR_BRANCH','warehouse',wh.id,f'branch={branch.id}')
        _rb.flash(f'Warehouse created for {branch.name}: {wh.name}','success')
        return _rb.redirect(_rb.request.referrer or _rb.url_for('inventory_warehouses'))
    return inventory_create_for_branch
