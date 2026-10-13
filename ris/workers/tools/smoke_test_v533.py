from app import app,db,APP_VERSION,Order
fails=[]
def chk(n,c,d=''):
 print(('PASS' if c else 'FAIL'),n,d)
 if not c:fails.append(n)
with app.app_context():
 chk('version',APP_VERSION=='5.33.0-rc1',APP_VERSION)
 try: db.session.execute(db.text('SELECT 1')); chk('database',True)
 except Exception as e: chk('database',False,str(e))
 o=Order.query.order_by(Order.id.desc()).first()
 if o: print('INFO latest',o.id,o.accession,o.modality,o.pacs_status,o.pacs_image_count,o.study_instance_uid)
print('SMOKE_RESULT', 'PASS' if not fails else 'FAIL')
raise SystemExit(1 if fails else 0)
