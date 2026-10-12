# 跨作品术语对照：首轮 SGI 范围

## 后续人物与世界观范围

首轮SGI记录保留如下。后续已审查110个人物、地点、组织和设定用词，并记录到结构术语表及根GLOSSARY.md；101项本作中文词面已定、9项待定。系列同一性与本作用词定稿是不同字段，当前确认继承0项、自动合并ID0项。525个结构名称已另行语义审查，暂不据候选直接回写。

| 韩文完整词面 | 固定参考行 | 复用中文词面 | 语义核对状态 |
|---|---:|---|---|
| 칼린츠 | 25 | 卡林兹 | 本作全名卡林兹·杰尔比南及第7组身份独立记录，同名不确认同人 |
| 라드린느 | 192 | 拉德琳娜 | 本作全名含莫蕾·伦·吉拉特，参考全名含米莉娅·欧文，不合并身份 |
| 지라트 | 142 | 吉拉特 | 本作王国，参考人物/商店语境，不能强制当作相同实体 |
| 마라카트 | 183 | 马拉卡特 | 本作政治集团与太阳纹章关系，跨作品对应待复核 |
| 바이에르 | 157 | 拜耶尔 | 本作政治集团与月之纹章关系，不按地名/魔法师标签自动确认 |
| 카르타 | 229 | 卡尔塔 | 本作力量承载/组合及象形文字，与参考系统机制需语义比对 |
| 마그나 카르타 | 389 | 真名法典 | 标题词面与本作禁忌仪式意义分离，不把全部卡尔塔替为标题 |
| 마그나카르타 | 167 | 真名法典 | 无空格源形独立记录，不合并资源ID |
| 신기 | 168 | 神器 | 本作力量承载武器状态与参考含卡恩融合物意义分别保留 |

仅复用中文词面不标记“继承自《真红的圣痕》”。每项保留实际FPB上下文ID及固定参考行；疑点不借字符串相似度消除。源文已明示妖石、灵印和灵印士的汉字时按源证据记录，不能用未核实英文二次命名覆盖。

## 固定来源

- 仓库：[jyh9521/Magna-Carta-Tears-Of-Blood-CN](https://github.com/jyh9521/Magna-Carta-Tears-Of-Blood-CN)。文件：[固定版本 GLOSSARY.md](https://github.com/jyh9521/Magna-Carta-Tears-Of-Blood-CN/blob/7c1d155ced5770458d02e2bd7d61b865565a3996/GLOSSARY.md)。
- commit：`7c1d155ced5770458d02e2bd7d61b865565a3996`。
- 下载文件 SHA-256：`9263d0138d1698c25f49f5a5f4015a9bfeec9915a8b2deb936c0947c62615507`。锁定数据在 `locales/zh-CN/reference-terms.json`。
- 仅读取此版本，没有修改参考项目文件或已统一译名。完整参考副本只保存在忽略的 build/ 中，不另维护上游译名副本。

参考表的“已统一”视为既定译名，但不自动证明跨作品概念同一性。完整短语优先，同名异义分开；显示名、内部 identifier 和资源 ID 不自动合并。普通词与不同系统机制按实际语义判断，不直接套用。

## 本轮实际输入与结果

2026-10-12 本轮输入为原版 `Sgi/0000.sgi`，不是写入“中文”的探针文件。SHA-256：`13adf18b88d94bcddd1c444e4ce11175c1a0390396ee475ccae94a17f62fa0a8`。

- 87 个名称原样提取，保存 resource、ordinal、identifier、独立记录 ID、字段偏移、原始 CP949 十六进制和解码文本，target 初始为空。原始字节往返一致，不裁剪名称空白。
- 固定参考的主术语表解析 2,021 条记录；其他性别/代词表不按名称表混入。
- 完整源文精确匹配候选 0，已确认共享概念 0，自动合并 ID 0。87 条全部保持 pending，不能从此结果推导两作没有共同术语或全部武器都是本作新增。
- 本轮不做子串、相似度、大小写或括号后缀归一化匹配。拼写变体、英文名称和实际含义待单独核对，候选为空不跳过语义复核。
- 已建立本作 [GLOSSARY.md](../GLOSSARY.md) 初表；诊断武器名称尚未定稿，其他专名仍待资源定位。人物、地点、组织、种族、道具与世界观概念的首次完整对照尚未完成，大规模翻译继续保持未开始状态。

## 构建与校对命令

Python 3.12 以上，无新增依赖。参考文件必须与锁定 SHA-256 一致；在线变化不会静默改变本项目结果。

```powershell
Invoke-WebRequest -Uri https://raw.githubusercontent.com/jyh9521/Magna-Carta-Tears-Of-Blood-CN/7c1d155ced5770458d02e2bd7d61b865565a3996/GLOSSARY.md -OutFile build/reference-GLOSSARY.md
python tools/audit_series_terms.py --sgi ORIGINAL/Sgi/0000.sgi --glossary build/reference-GLOSSARY.md --lock locales/zh-CN/reference-terms.json --catalog build/sgi-catalog.json --report build/series-comparison.json
python -m unittest discover -s tests -p "test_*.py"
```

输出文件必须为新路径。工具只提取与比较，不修改游戏、参考表或资源 ID，不启动游戏。完整 catalog 和复核报告不提交；记录级来源及决策保留为后续翻译输入。

## 已确认概念的自动一致性检查

显式决策通过 `--decisions DECISIONS.json` 输入，待检查译文通过 `--translations TRANSLATIONS.json` 输入。两者为列表；所有 id 必须来自当前 catalog，不接受重复或未知 ID。

```json
{
  "id": "RESOURCE:name:ORDINAL:IDENTIFIER",
  "relation": "confirmed_shared",
  "source": "EXACT_CURRENT_SOURCE",
  "reference_line": 0,
  "reference_source": "EXACT_REFERENCE_SOURCE",
  "evidence": "CONCEPT_MATCH_EVIDENCE"
}
```

上述为格式示例，不是已确认关联；reference_line 须填写实际固定版本的行号。确认必须附概念匹配依据并保留原名；参考项必须为“已统一”。工具从参考项取得既定中文，不接受英文译名覆盖既定中文，也不从相同字符串自动生成确认决策。

译文列表项格式为 `{"id":"RECORD_ID","target":"TARGET_TEXT"}`。已确认共享项使用不同中文时写入 conflicts 并返回退出码 2；待复核项不强制套用参考译名。源文或参考定位变化时拒绝旧决策，要求重新复核。当前实际输入没有确认项，因此没有真实译文冲突；冲突行为已通过独立样本回归验证。

## 自动验证与后续

原有 119 项通过，新增 15 项覆盖固定哈希、完整 commit、主表识别、转义分隔符、同名异义、完整词匹配、证据要求、旧决策拒绝、已统一状态、继承一致性与冲突、待复核不强制、重复 ID 及原始字段保护，合计 134 项通过。

后续依次定位其他专名资源、补英文/语义依据、人工确认共享概念、更新本作术语表及决策记录，再接入正式翻译导入。完整简体字字库与编码适配、对话控制符及两套字体游戏验收继续独立推进。
