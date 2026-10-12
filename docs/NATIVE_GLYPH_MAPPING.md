# 原生私有字形映射候选

## 原因与边界

原版 CP949 支持部分汉字，不覆盖全部简体中文。不能把目标文本直接编码为 GBK/UTF-8，也不能靠终端能够输出某字符判断游戏支持。

既有 MCAlpha 静态证据确认：字节首部大于等于 CA 时，绘制及测量路径均消费两个字节，并将数值减去 CAA0 作为 Chi 槽索引。两套 Chi 的 count 均为13,151，指标固定14/22像素。对应路径及真实原版中文显示证据见 FONT_PIPELINE_RESEARCH.md 和 TEXT_DISPLAY_PROBE.md。

`tools/native_text_codec.py` 选择原生范围内、严格 CP949 解码失败的私有字节对，并保持索引在两套字库范围内。保留所有有效 CP949 代码；私有代码不是新的标准代码页，只能由对应映射表编码/解码。

代码范围为首字节 CA..FD、尾字节40..A0，排除反斜线与花括号，并排除负索引、有效CP949对与越界槽。尾字节不包含零、换行、`$`、`%`、尖括号，避免与现有格式指令混淆；ASCII和原控制标记按字节保持。实际源字库可规划4,795个槽，按Unicode码点排序确定映射，不随机编号。

原版数字索引间隙并不等于零位图：本轮检查高尾字节候选，没有两套字库同时为空的槽。因此不采用“空白槽自动可用”的假设，使用非CP949编码区域的显式私有映射。未知直接索引消费者及Windows字符串API仍需按使用路径核实，不能据此宣称全引擎适配已完成。

## 字形构建

`tools/build_font_overlay.py` 从显式提供且SHA-256锁定的轮廓字体生成两套1-bit LSB-first字形；保持100字节头、count、pitch、height、文件长度与其他槽不变。目标字符先检查cmap覆盖，再检查单格容纳和非空墨迹；不同尺寸独立生成，不以缩放后的屏幕大小代替原字体尺寸。

构建依赖见 tools/requirements-localization.txt：Pillow12.3.0、fonttools4.61.1，仅构建阶段使用，不添加玩家运行时依赖。字体来源、许可元数据、渲染库版本、原始/修改字库哈希、映射、每槽增量和编码结果写入 overlay.json。没有部署或自动游戏运行步骤。

初次局部样本使用本地非发行字体，随后改为可取得的固定来源：Google/fonts commit `bd8f81ddb5c74d5c8897b36ad88b440266245103`，`ofl/notosanssc/NotoSansSC[wght].ttf`，17,772,300字节，SHA-256 `a3041811a78c361b1de50f953c805e0244951c21c5bd412f7232ef0d899af0da`。来源锁位于 `assets/font-sources/noto-sans-sc.json`，SIL Open Font License 1.1 完整声明位于 `assets/licenses/NotoSansSC-OFL.txt`，其SHA-256为 `1c05c68c34f9708415aada51f17e1b0092d2cea709bf4a94cd38114f9e73d7d9`。字体软件与衍生字形不自动套用项目MIT。

可变字体明确选择 wght=500，不依赖轮廓字体默认的100细体。每次构建记录实际轴参数；未知轴保持来源默认值，越界权重拒绝。固定来源的两次构建字库及映射报告逐字节一致。

```powershell
python -m pip install -r tools/requirements-localization.txt
python tools/fetch_locked_asset.py --manifest assets/font-sources/noto-sans-sc.json --output build/font-source/NotoSansSC.ttf
python tools/build_font_overlay.py --source ORIGINAL/Font --font build/font-source/NotoSansSC.ttf --font-sha256 a3041811a78c361b1de50f953c805e0244951c21c5bd412f7232ef0d899af0da --weight 500 --text 中文测试汉龙 --output build/font-overlay-candidate
```

全文输入使用 `--translations TRANSLATIONS.json` 替代 `--text`，避免Windows命令行长度限制。文件为UTF-8行列表，每项至少有唯一非空字符串id和字符串target；缺译、重复ID及嵌入零字符拒绝。按稳定id排序汇集目标字符，来源摘要与行数进入报告，发布前再次检查输入文件未变。字库构建不自动批准译文语义，也不把候选变成定稿。

```json
[{"id":"RESOURCE:text:ORDINAL:IDENTIFIER","target":"目标文本"}]
```

已通过80,004个目标字符的文件输入及两次实际构建；两套字库和报告逐字节一致，输入含相同6字时也与短探针字库一致。新增3项覆盖大文件、缺译/重复/零字符和构建期间输入变化拒绝，当前总计194项通过；该大文件为受控重复文本，不是全文译文完成量。

生成完整原版格式的候选字库只保存在忽略的 build/ 中；不提交商业字库或完整修改文件。增量数据与原创构建脚本分开保存，原商业字段来源不因生成而改变。

## 静态结果

已生成 `中文测试汉龙` 6字、2套字体，原始文件未变；编码/解码、逐槽替换及重复构建字节一致分别验证。实际输出为私有编码，不通过CP949重新解码验证目标文字，而由 overlay.json 的对应映射验证。

编码器8项测试覆盖确定性、全部候选非CP949、索引/容量、保护字节、截断/终止符、重复映射、缺字和非法码点；构建器4项受控测试检查逐槽差异、源不变、来源哈希、缺字及输出复用拒绝；下载器7项检查摘要、大小、HTTPS及输出保护。当前合计161项单元测试通过。字形构建尚未游戏验收，也未把局部字形候选写入运行副本。

## 文本框步长差异：已确认阻断

MCAlpha SHA-256 `79e4c3d6af4afb2b75367a2b26fd8450ad25fa9f738612ea96809e312d33cb6f` 的 `0x5201efcd` 字符步长函数仅为 A4..C9 返回2，CA..FF返回1。`0x5205b9af` 自动换行逐次调用该函数累积前缀，再调用 Font 测宽；因此 CA..FD 私有码会被截成半个字符。字库绘制和直接标签支持双字节不代表文本框分段也支持。

静态证据为 `ev_d54a3925a053c39d8e4f8367c3f508429c4aca6231347e3df9ac3ce5f0711e28` 和 `ev_cec64502987d07a59107abb48bac53f1b67a78f9e6b9903e1f1c896af381b780`。步长兼容修正必须锁定版本、完整函数预期字节和调用边界；未补齐之前不把新编码写入完整对话。

后续已建立默认关闭的 [步长适配模块](TEXT_LAYOUT_COMPATIBILITY.md)，只修改受控进程内单个即时数值，不改变安装DLL；自建夹具及实际文件只读上下文验证通过，游戏对话验收未执行。

缓存路径 `0x52031bce` 使用 strlen/strcpy 后进入原生字体测量与字形绘制，静态所见没有Windows代码页转换；显示按像素渐显而非逐字截断。`$n` 与自动换行分别保留。上述静态结论不替代最终对话、混排和长文本游戏验收。

后续只使用全文实际译文集生成最终映射，不沿用局部探针的编号。编码变化必须同步重建全部译文资源、字库与显示适配，不能只换字库或只换文本；最终统一实际测试之前不启动游戏。
