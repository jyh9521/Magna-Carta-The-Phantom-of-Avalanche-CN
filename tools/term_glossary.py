"""Validate and render explicit concept decisions, without automatic ID merging."""
import argparse
import json
from pathlib import Path

STATUSES = {'继承自《真红的圣痕》','本作新增','待复核'}


def validate(data):
    if data.get('schema') != 1 or not isinstance(data.get('terms'),list):
        raise ValueError('unsupported term glossary schema')
    ids = set()
    for term in data['terms']:
        if not term.get('id') or term['id'] in ids:
            raise ValueError('duplicate or empty concept ID')
        ids.add(term['id'])
        if not term.get('source') or not term.get('meaning') or term['status'] not in STATUSES:
            raise ValueError('incomplete concept decision')
        if len(term['resource_ids']) != len(set(term['resource_ids'])):
            raise ValueError('duplicate resource occurrence ID')
        excluded=set()
        for item in term.get('excluded_occurrences',[]):
            key=item.get('resource_id');sha=item.get('source_sha256','')
            if (not key or key in excluded or key in term['resource_ids'] or not item.get('reason')
                    or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha)):
                raise ValueError('invalid, duplicate or overlapping term exclusion')
            excluded.add(key)
        if term['status'] == '继承自《真红的圣痕》':
            refs=term.get('reference_candidates',[])
            confirmed=term.get('confirmed_reference_line')
            selected=[r for r in refs if r['line']==confirmed and r['status']=='已统一']
            if (term.get('relation') != 'confirmed_shared' or len(selected)!=1
                    or not term.get('concept_match_evidence') or term.get('target')!=selected[0]['target']):
                raise ValueError('inheritance requires explicit semantic evidence and locked target')
        elif term.get('relation') == 'confirmed_shared':
            raise ValueError('shared concept must inherit the locked reference')
        if term.get('translation_state') == 'approved' and not term.get('target'):
            raise ValueError('approved term requires a target')
    return data


def matches(text, resource_id, terms):
    """Longest complete phrase first, only inside explicitly reviewed resource IDs."""
    eligible=sorted((t for t in terms if resource_id in t['resource_ids']),
                    key=lambda t:(-len(t['source']),t['id']))
    if any(not t['source'] for t in eligible):
        raise ValueError('empty term cannot be matched')
    hits=[];offset=0
    while offset<len(text):
        candidates=[t for t in eligible if text.startswith(t['source'],offset)]
        if candidates:
            term=candidates[0];hits.append(dict(offset=offset,term=term));offset+=len(term['source'])
        else:offset+=1
    return hits


def conflicts(source, target, resource_id, terms):
    result=[]
    for hit in matches(source,resource_id,terms):
        term=hit['term']
        if term['translation_state']=='approved' and term['target'] not in target:
            result.append(dict(resource_id=resource_id,term_id=term['id'],expected=term['target'],
                               source_offset=hit['offset'],kind='review_required_not_automatic_replacement'))
    return result


def cell(value):
    return str(value or '待核实').replace('|','\\|').replace('\r',' ').replace('\n',' ')


def render(data):
    validate(data)
    ref=data['reference'];terms=data['terms']
    lines=['# 《真名法典：冰之魅影》简体中文术语表','',
           '结构化来源：`locales/zh-CN/terms.json`；使用 `tools/term_glossary.py` 生成本表。完整原文上下文留在本地构建目录，不提交整份商业剧情文本。','',
           f'参考仓库：[《真红的圣痕》]({ref["repository"]})，固定 commit `{ref["commit"]}`，SHA-256 `{ref["sha256"]}`。参考项目只读。','',
           '相同世界观概念使用相同译名，不同概念不得为了统一而强行合并。完整短语优先，韩文拼写、英文名、含义与来源分别记录；同名不证明同一概念，资源ID不合并，内部名不按显示名直接改写。','',
           f'当前收录 {len(terms)} 项；其中 {sum(t["translation_state"]=="approved" for t in terms)} 项本作用词已定，其余为建议译名。跨作品关系“待复核”与本作用词是否定稿分别记录；没有参考精确匹配也不自动证明“本作新增”。词面复用与概念继承分别记录。物品、技能及角色结构名称持续补充。','',
           '| 韩文原名 | 英文参考 | 中文译名 | 分类 | 系列状态 | 本作用词 | 实际含义与依据 | 资源位置 |',
           '|---|---|---|---|---|---|---|---|']
    for term in terms:
        resources=term['resource_ids'];locations=', '.join(resources[:4])
        if len(resources)>4:locations+=f'；另{len(resources)-4}项见结构数据'
        note=term['meaning']
        if term.get('reference_candidates'):note+='；参考完整词面相同，概念关系：'+term['relation']
        values=[term['source'],term.get('english_reference'),term.get('target'),term['category'],term['status'],
                '已定' if term['translation_state']=='approved' else '待定',note,locations]
        lines.append('| '+' | '.join(cell(v) for v in values)+' |')
    lines+=['','“中文”仅为SGI资源显示探针，不是武器译名。未确定译名、未判明用途的内部标签及疑似拼写错误保持复核状态，不由生成器自动裁定。','']
    return '\n'.join(lines)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--terms',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.terms.resolve()==a.output.resolve():
        raise ValueError('output must not overwrite structured term input')
    data=json.loads(a.terms.read_text('utf8'));text=render(data)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(text,encoding='utf8',newline='\n')
    print(f'TERM_GLOSSARY PASS concepts={len(data["terms"])} confirmed_shared='+str(sum(t['status']=='继承自《真红的圣痕》' for t in data['terms']))+' auto_merged_ids=0 game_started=false')
