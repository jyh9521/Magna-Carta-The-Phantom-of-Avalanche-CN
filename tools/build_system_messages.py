"""Compile source-bound system text rules; never rewrite commercial modules."""
import argparse,hashlib,json,re
from pathlib import Path
TOKENS=re.compile(r'%04d|%d|%s')
def sha(b):return hashlib.sha256(b).hexdigest()
def wide(s):
    return 'L"'+''.join(json.dumps(c)[1:-1] if ord(c)<128 else ('\\u%04x'%ord(c) if ord(c)<=65535 else '\\U%08x'%ord(c)) for c in s)+'"'
def compile_rules(raw,plan):
    if (plan.get('schema')!=1 or plan.get('source_sha256')!=sha(raw)
            or plan.get('source_size')!=len(raw) or plan.get('source_encoding')!='cp949'
            or plan.get('code_page')!=949):raise ValueError('unsupported system message source')
    fields=plan.get('fields');rules={};seen=set()
    if not isinstance(fields,list) or not fields:raise ValueError('empty system message fields')
    for row in fields:
        off=row.get('offset');expected=bytes.fromhex(row['expected_hex'])
        if (type(off) is not int or off<0 or off in seen or off+len(expected)>=len(raw)
                or raw[off:off+len(expected)+1]!=expected+b'\0' or not row.get('evidence')):
            raise ValueError('system field offset, bytes or evidence mismatch')
        seen.add(off);source=expected.decode('cp949');target=row['target']
        if (not isinstance(target,str) or not target or '\0' in target
                or TOKENS.findall(source)!=TOKENS.findall(target)
                or '%' in TOKENS.sub('',source) or '%' in TOKENS.sub('',target)):
            raise ValueError('system message format changed or unsupported')
        if source in rules and rules[source]!=target:raise ValueError('conflicting linked system targets')
        rules[source]=target
    return rules
def build(source,plans,output,module_candidate=None,domain_plans=None,font_package=None):
    source=Path(source).resolve(strict=True);plans=Path(plans).resolve(strict=True);output=Path(output).resolve()
    if output.exists() or any(p.is_relative_to(output) for p in (source,plans)):
        raise ValueError('system output must be new and separate')
    raw=source.read_bytes();data=plans.read_bytes();plan=json.loads(data);rules=compile_rules(raw,plan)
    snapshots={source:raw,plans:data};active=raw;mapping={}
    if font_package:
        from native_text_codec import validate
        p=Path(font_package).resolve(strict=True)/'overlay.json';snapshots[p]=p.read_bytes()
        mapping=json.loads(snapshots[p])['mapping'];validate(mapping)
    if module_candidate:
        if not domain_plans or not font_package:raise ValueError('candidate requires verified domain plan and matching font')
        from patch_text_domains import patch
        candidate=Path(module_candidate).resolve(strict=True);domains=Path(domain_plans).resolve(strict=True)
        snapshots[candidate]=candidate.read_bytes();snapshots[domains]=domains.read_bytes()
        expected,_=patch(raw,json.loads(snapshots[domains]),mapping)
        if expected!=snapshots[candidate]:raise ValueError('candidate differs from declared source-bound text patch')
        active=expected
        for r in plan['fields']:
            off=r['offset'];b=bytes.fromhex(r['expected_hex'])+b'\0'
            if active[off:off+len(b)]!=b:raise ValueError('candidate changed protected system source')
    elif domain_plans:raise ValueError('domain plan without candidate')
    if any(p.is_relative_to(output) for p in snapshots):raise ValueError('system output overlaps input')
    lines=['#pragma once',f'constexpr unsigned localeSystemCodePage = {plan["code_page"]};',
           f'constexpr char localeSystemSourceSha[] = "{sha(active)}";',
           'const SystemRule localeSystemRules[] = {']
    for a,b in rules.items():lines.append('{'+wide(a)+','+wide(b)+'},')
    lines+=['};','const SystemRule localeSystemEnvelopes[] = {']
    for r in plan.get('envelopes',[]):
        if not r['source'] or not r['target'] or '\0' in r['source']+r['target']:raise ValueError('invalid envelope')
        if r['source'][:-1].encode('cp949')+b'\0' not in raw:raise ValueError('envelope source not present')
        lines.append('{'+wide(r['source'])+','+wide(r['target'])+'},')
    if not plan.get('envelopes'):lines.append('{L"",L""},')
    lines+=['};','const SystemRule localeSystemCaptions[] = {']
    for r in plan.get('captions',[]):
        if not isinstance(r.get('source'),str) or not isinstance(r.get('target'),str) or not r['source'] or not r['target'] or '\0' in r['source']+r['target']:
            raise ValueError('invalid system caption')
        lines.append('{'+wide(r['source'])+','+wide(r['target'])+'},')
    if not plan.get('captions'):lines.append('{L"",L""},')
    lines+=['};']
    lines+=['const SystemRule localeSystemFixtureCases[] = {']
    for row in plan['fields']:
        source_text=bytes.fromhex(row['expected_hex']).decode('cp949');target=row['target']
        values=['0007' if t=='%04d' else 'sample' if t=='%s' else str(11+i) for i,t in enumerate(TOKENS.findall(source_text))]
        def example(s):
            it=iter(values);return TOKENS.sub(lambda _:next(it),s)
        lines.append('{'+wide(example(source_text))+','+wide(example(target))+'},')
    lines+=['};']
    lines+=['const SystemGlyph localeSystemGlyphs[] = {']
    for char,item in sorted(mapping.items(),key=lambda x:x[1]['encoded_hex']):
        lines.append('{0x'+item['encoded_hex']+','+wide(char)+'},')
    if not mapping:lines.append('{0,L""},')
    lines+=['};']
    if any(p.read_bytes()!=b for p,b in snapshots.items()):raise ValueError('system input drift')
    output.mkdir(parents=True);header=('\n'.join(lines)+'\n').encode('ascii');(output/'system_message_rules.h').write_bytes(header)
    report=dict(schema=1,source_sha256=sha(raw),active_module_sha256=sha(active),native_glyphs=len(mapping),plans_sha256=sha(data),header_sha256=sha(header),fields=len(plan['fields']),
                unique_rules=len(rules),source_unchanged=True,deployed=False,game_started=False)
    (output/'build.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n');return report
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for a in ('source','plans','output'):p.add_argument('--'+a,type=Path,required=True)
    for a in ('module-candidate','domain-plans','font-package'):p.add_argument('--'+a,type=Path)
    a=p.parse_args();r=build(a.source,a.plans,a.output,a.module_candidate,a.domain_plans,a.font_package)
    print(f'SYSTEM_MESSAGE_BUILD PASS fields={r["fields"]} rules={r["unique_rules"]} source_unchanged=true game_started=false')
