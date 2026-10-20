"""Validate local OpenAPI references, navigation and Python examples."""
import ast
import json
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
spec = json.loads((root / 'openapi/reclip-v1.json').read_text())
config = json.loads((root / 'docs.json').read_text())
assert spec['openapi'] == '3.1.0'

def walk(value):
    if isinstance(value, dict):
        if '$ref' in value and value['$ref'].startswith('#/'):
            target = spec
            for part in value['$ref'][2:].split('/'):
                target = target[part.replace('~1', '/').replace('~0', '~')]
        for child in value.values(): walk(child)
    elif isinstance(value, list):
        for child in value: walk(child)
walk(spec)
for tab in config['navigation']['tabs']:
    for group in tab['groups']:
        for page in group['pages']:
            path = root / (page + '.mdx')
            assert path.exists(), str(path)
            content = path.read_text()
            op = re.search(r'^openapi: (\w+) (.+)$', content, re.M)
            if op: assert op[1].lower() in spec['paths'][op[2]]
            for link in re.findall(r'\]\((/[^)]+)\)', content):
                assert (root / (link.lstrip('/') + '.mdx')).exists(), link
for path in root.rglob('*.py'):
    if 'node_modules' not in path.parts: ast.parse(path.read_text())
expected_tools = {
    request['properties']['tool']['const'].replace('_', '-')
    for request in spec['components']['schemas']['JobRequestEnvelope']['oneOf']
}
actual_tools = {path.stem for path in (root / 'tools').glob('*.mdx')}
assert actual_tools == expected_tools, (actual_tools, expected_tools)
print('OpenAPI references, navigation, tool pages and Python syntax passed.')
