#!/usr/bin/env python3
import ast,glob,re,sys
from pathlib import Path
from jinja2 import Environment,FileSystemLoader,TemplateSyntaxError

root=Path(__file__).resolve().parent
source=(root/'app.py').read_text(encoding='utf-8')
tree=ast.parse(source)

funcs=[]
route_eps=set()
routes=set()
for n in tree.body:
    if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
        funcs.append(n.name)
        for d in n.decorator_list:
            if isinstance(d,ast.Call) and isinstance(d.func,ast.Attribute) and d.func.attr=='route':
                route_eps.add(n.name)
                if d.args and isinstance(d.args[0],ast.Constant):
                    routes.add(d.args[0].value)

dups=sorted({x for x in funcs if funcs.count(x)>1})

env=Environment(loader=FileSystemLoader(str(root/'templates')))
jinja_errors=[]
for p in sorted((root/'templates').glob('*.html')):
    try:
        env.parse(p.read_text(encoding='utf-8'))
    except TemplateSyntaxError as e:
        jinja_errors.append(f'{p.name}:{e.lineno}:{e.message}')

refs=set()
for p in glob.glob(str(root/'templates'/'*.html')):
    refs.update(re.findall(r"url_for\(['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]",Path(p).read_text(encoding='utf-8')))
missing_eps=sorted(x for x in refs-route_eps if x!='static')

critical_routes=[
    '/',
    '/patients',
    '/patients/new',
    '/orders',
    '/orders/new',
    '/orders/<int:order_id>',
    '/appointments',
    '/doctor',
    '/reports',
    '/reports/<int:order_id>',
    '/reports/<int:order_id>/word',
    '/reports/<int:order_id>/upload',
    '/accounting/receivables',
    '/accounting/reports',
    '/analytics',
    '/admin',
    '/admin/assignment',
    '/assignment/unassigned',
    '/admin/diagnostics',
    '/api/reporting/health',
]
missing_routes=[x for x in critical_routes if x not in routes]

required_source=[
    "assigned_doctor_id = db.Column",
    "assigned_at = db.Column",
    "priority = db.Column",
    "assigned_doctor = db.relationship",
    "def assignable_doctors(",
    "Role.code.in_(['RADIOLOGIST','SUPER_ADMIN'])",
]
missing_source=[x for x in required_source if x not in source]

print('Duplicate route functions:',dups or 'None')
print('Jinja syntax errors:',jinja_errors or 'None')
print('Missing template endpoints:',missing_eps or 'None')
print('Missing critical routes:',missing_routes or 'None')
print('Missing assignment model/code:',missing_source or 'None')

if dups or jinja_errors or missing_eps or missing_routes or missing_source:
    sys.exit(1)
print('STATIC PREFLIGHT PASSED')
