"""Validate the documentation milestone; this does not run the game."""
import argparse
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
p.add_argument('--expect', choices=['baseline', 'modified'], required=True)
a = p.parse_args()
root = a.root.resolve()
paths = ['docs/MODERNIZATION_ROADMAP.md', 'docs/RUNTIME_RESEARCH.md', 'docs/RUNTIME_TESTING.md']
tech = (root / 'TECHNICAL.md').read_text(encoding='utf-8')
marker = '# 本作现代 Windows 与无盘运行路线'
checks = 0

def check(value):
    global checks
    checks += 1
    if not value:
        raise SystemExit(f'DOCS_CHECK FAIL check={checks}')

if a.expect == 'baseline':
    check(marker not in tech)
    for name in paths:
        check(not (root / name).exists())
else:
    check(tech.count(marker) == 1)
    for name in paths:
        check((root / name).is_file())
        check(Path(name).name in tech)
    roadmap, research, testing = [(root / name).read_text(encoding='utf-8') for name in paths]
    for token in ['P0', 'P1', 'P2', 'P3', 'MC_PLAY', '1280×720', '1366×768', '1600×900', '1920×1080', '2560×1440', '3840×2160', '16:10', '21:9', 'Magna Carta Configuration', '回滚', '复制保护']:
        check(token in roadmap)
    for token in ['9ce77cace0d717f5ad75bb2910517802e55932c8', 'DDrawCompat', 'dgVoodoo2', 'cnc-ddraw', 'DxWnd', '未验证', '尚未选定']:
        check(token in research)
    for name in ['README.md', 'LICENSING.md', 'TECHNICAL.md', 'docs/RUNTIME_RESEARCH.md']:
        content = (root / name).read_text(encoding='utf-8')
        check('magnacarta-installguide' not in content and '安装指南' not in content)
    check('https://github.com/Nejuf/magnacarta' in (root / 'README.md').read_text(encoding='utf-8'))
    for token in ['CD-01', 'CD-02', 'CD-03', 'CD-04', 'CD-05', 'CD-06', 'CD-07', '未执行', '原生', '模拟', '失焦', 'DPI', '回滚']:
        check(token in testing)
print(f'DOCS_CHECK {a.expect.upper()} PASS checks={checks}')
