import glob

for path in glob.glob('*.py'):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    s = content.strip()
    if s.startswith('```python'):
        s = s[len('```python'):].lstrip('\n')
    elif s.startswith('```'):
        s = s[3:].lstrip('\n')
    if s.endswith('```'):
        s = s[:-3].rstrip('\n')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(s + '\n')
    print(f'Fixed: {path}')
