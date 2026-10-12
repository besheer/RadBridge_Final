"""Static coupling inventory; never imports the application or reads runtime data.

Counts are evidence locations, not defects, executed calls or completion percentages.
"""
import argparse
import ast
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def inventory():
    ris=ROOT/'ris'
    contracts=json.loads((ris/'application/port_contracts.json').read_text(encoding='utf-8'))
    manifest=json.loads((ris/'application/component_manifest.json').read_text(encoding='utf-8'))
    runtime_imports=[];namespace_calls=[];service_framework_imports=[]
    for layer in ('domain','application','infrastructure','web'):
        for path in sorted((ris/layer).rglob('*.py')):
            tree=ast.parse(path.read_text(encoding='utf-8-sig'))
            is_service=path.is_relative_to(ris/'application/services')
            for node in ast.walk(tree):
                if isinstance(node,ast.ImportFrom) and node.module=='application.legacy_runtime':
                    runtime_imports.append(dict(file=path.relative_to(ROOT).as_posix(),line=node.lineno,
                        layer=layer,names=[alias.name for alias in node.names]))
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='namespace':
                    namespace_calls.append(dict(file=path.relative_to(ROOT).as_posix(),line=node.lineno,layer=layer))
                if is_service:
                    imports=[alias.name for alias in node.names] if isinstance(node,ast.Import) else [node.module or ''] if isinstance(node,ast.ImportFrom) else []
                    for name in imports:
                        if name.split('.')[0] in {'flask','sqlalchemy','requests','web','infrastructure'}:
                            service_framework_imports.append(dict(file=path.relative_to(ROOT).as_posix(),line=node.lineno,module=name))
    return dict(interpretation='Static imports and namespace calls; review each location. No vulnerability/completion/runtime-execution claim.',
        explicit_service_count=len(contracts['services']),original_function_ownership_count=len(manifest),
        declared_dependencies_per_original_function=dict(min=min(len(e['dependencies']) for e in manifest),
            max=max(len(e['dependencies']) for e in manifest),total_references=sum(len(e['dependencies']) for e in manifest)),
        runtime_import_file_count=len({e['file'] for e in runtime_imports}),runtime_import_count=len(runtime_imports),
        namespace_call_count=len(namespace_calls),legacy_runtime_imports=runtime_imports,namespace_calls=namespace_calls,
        service_framework_import_count=len(service_framework_imports),service_framework_imports=service_framework_imports)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,help='Optional JSON inventory path; does not contain environment values or clinical data')
    args=parser.parse_args();result=inventory()
    if args.output:
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({key:value for key,value in result.items() if key not in ('legacy_runtime_imports','namespace_calls','service_framework_imports')},ensure_ascii=False))


if __name__=='__main__':main()
