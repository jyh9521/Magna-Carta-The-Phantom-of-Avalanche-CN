# 文件格式

## GID BSP与WRD绑定（2026-10-24）

GID原生加载器fb56先读1024保留字节和计数sublevel，每项3个DWORD及count×32顶点；随后为
节点数和前序树。叶记录2个DWORD，内部记录flag、22字节polygon、16字节平面、共面项计数及
count×22字节、前后子树。resource_gid.py验证计数、深度、浮点、节点数及EOF，polygon字段保持不透明。
WRD末尾16字节最后DWORD才是Guide资源ID，不保证与WRD同名；例如106→59、109→62、111→64。
内存树节点父指针+10用于命中平面定位，仅读子树/平面而不重建父指针会丢失反射法线。
证据、真实源查询和边界见[阻断问题调查](BLOCKER_TRACE.md)。

## SVD原声包装（2026-10-23）

magic为`19 93 12 25`。实查compact头56字节，storage=u32@8，filter=u32@12，
参数40字节@16，+4未知保留。旧SoftMax签名头物理payload为108，storage/filter@60/64。
filter18是无过滤器哨兵，不是编码编号。原生回调固定seek56，与旧头物理偏移分别记录。
工具`audit_dialogue_resources.py`按两种实证结构解析；见[真实对白链路](DIALOGUE_REAL_CHAIN.md)。

## 图片清理与跨块标题计划（2026-10-20）

`erase_rects_xyxy` 是半开旧字清理区，与 `mask_xyxy` 的新字排版区分离，两者使用
同一 `erase_mode`。`preserve_background_alpha` 仅保留清理目标的源 alpha；
`background_repairs` 在清理区内按显式源矩形拷贝/镜像 RGBA 或按行/列采样。
跨图捐赠资源包含路径与整份 `source_sha256`；`protected_rects_xyxy` 要求最终像素
与源相同，文字重叠拒绝发布。这些字段是自有构建计划，不改变 BGR 包装或 FDI。
0155–0164 的五个题头按 512×256 原坐标拼合后一次排版，再裁回原 256×256 块；
资源标识、包装、头尾、尺寸不改。证据见 [图片结构修复](IMAGE_INTEGRITY_REPAIR.md)。

## SGC1：自有缩放覆盖缓存（非游戏文件）

小端：`magic[4]="SGC1"`，u32版本=1、逻辑高度、栅格倍数、字形数，头共20字节。
随后为严格递增的u16字形ID表，再按表顺序存连续8位灰度覆盖；每字形边长为
`逻辑高度×倍数`。总长必须为 `20+count×2+count×(height×scale)^2`。
当前逻辑高度仅14/22，倍数1..4，字形数1..4096，读取上限64MiB；未知版本/尺寸/
重复ID/截断拒绝。外部manifest保存输入、源字体许可和每文件SHA256，覆盖按原BGRA
source-over合成。缓存不包含原游戏字体文件；C候选从共享fonts目录读取，摘要由生成头绑定自有模块。
试样与原生接入边界见[SCALED_FONT_COVERAGE.md](SCALED_FONT_COVERAGE.md)。

## Field事件尾部（2026-10-19）

Verified：既有静态前缀之后，原生RVA4ab93读取i32事件数，每事件依次读取非负i32次数限制、
i32条件数、条件数×60字节、i32动作数、动作数×60字节。每命令为i32 opcode和14个原样i32参数。
4b7a4检查正次数限制与已执行次数，0不限次数；4b5cb结束时增加已执行次数。解析器不修改该值。
tools/resource_field_script.py要求完整EOF、累计数量与边界守卫；未知opcode/参数不归一化。
597实样中565份同时通过该结构与原静态前缀，未通过者不据此判为损坏。
单命令语义按独立证据认定，不能把结构解码视作全部脚本或导航语义已理解。
0757具体条件与命令参考[楼梯事件](STAIRWELL_RETURN_HEIGHT.md)。

BGR、FPB、ITM、SGI、ABI 为实际样本及上游工具的调查对象。FPB 结构已按 606 个安装文件验证；其余格式的完整字段含义仍待核实。
每种格式记录平台、版本、magic、字节序、字段、偏移基址、长度单位、编码、终止符、对齐、压缩、校验、外部索引、未知字节和工具。
字段解释附证据等级，通用示例不作为本作发现。解析器检查边界、溢出和截断，构建器检查长度、偏移和元数据。
原样往返分别报告字节一致、结构等价或功能等价并解释差异，提取成功不代表支持重建。

## FPB：已验证的安装样本结构

- 所有数值为 u32 little-endian。非空表首先为记录数 N，随后为 N 组 `(tag, offset, length)`，每组 12 字节。
- 表尾为字符串区总字节数；字符串区从 `8 + 12*N` 开始。offset 相对于字符串区，length 包含尾部零字节。
- 606 个样本中 183 个空表仅为四个零字节，不包含表尾总长字段。
- 非空样本共 3,524 条记录，均通过范围、连续偏移、终止符和总长度检查；CP949 严格解码全部成功。此结果不单独证明运行时编码或中文字形映射。
- `tools/resource_fpb.py` 保留 tag、ordinal 和原始字节，全部 606 个文件原样重建字节一致。内部标识不自动合并。
- ITM、ABI、SGI 的单一样本满足 `8 + count*record_size`，record_size 分别为 264、344、164；数值验证不等于全部字段已理解。

上游字段线索来自 Nejuf/magnacarta 固定 commit `9ce77cace0d717f5ad75bb2910517802e55932c8` 的提取/重建脚本；当前 Python 实现独立编写，并按实际样本验证。

## Font DAT：MCAlpha 字库

固定头 100 字节，byte42 非零表示随后包含 count 字节的逐槽 advance 表，再接 1-bit 位图区。height=u16@88、pitch=u8@90、count=u32@92、bitmap_size=u32@96，实际样本满足 bitmap_size=count×height×pitch。每槽逐行 LSB-first，Eng0/1 存 advance、Kor/Chi 不存。
六个实际文件原样往返字节一致，未知头字段保留；尺寸、大小和槽边界不符拒绝。角色编码和固定索引常量必须一起核对，详见 [字体逆向](FONT_PIPELINE_RESEARCH.md)；该结构验证不是新字库游戏验收。

## SGI：受控名称探针

实际 0000.sgi 为头 8 字节加 87×164 字节。头第一项为 u32 记录数，第二项实际为 16、完整含义未确认；原样保留。记录开头 u32 为标识，随后 `[4,104)` 为上游指出的名称候选区，样本 87 项均可取得零终止 CP949 字符串；余下 60 字节属性含义不在本轮重解释。

`tools/resource_sgi.py` 保留完整记录及头部，不合并 ID，不裁剪空白，不重新打包属性。名称探针严格限于原字符串及其终止符占用的跨度，不将候选 100 字节长度视为已验证的运行时容量。定位、哈希、差异及实际验收边界见 [资源显示探针](TEXT_DISPLAY_PROBE.md)。

## ITM / ABI：结构化提取范围

ITM 实际 88×264 字节记录加头8字节；每记录 ID=u32@0，名称候选 `[4,104)`、说明候选 `[164,264)`，中间属性原样保留。ABI 实际205×344记录加头8字节，ID=u32@0、名称候选 `[4,64)`；后续属性不重新解释。头部第二u32的意义仍未全面确认，不按上游重建脚本的常量覆盖原值。

`tools/extract_text_catalog.py` 验证计数、文件长度、字段范围、零终止与严格 CP949 解码；空串和空白保留，名称与说明使用独立稳定ID。此阶段只读提取，不将字段宽度当成已证明的 UI 容量，也不自动改写可能仅内部使用的 ABI 动作标签。全部文本覆盖状态见 [全文管线](FULL_TRANSLATION_PIPELINE.md)。

## CHA：结构名称及存档关联

实际头8字节为 `(count=145, second=58)`，接145×267字节记录。ID=u32@0，名称100字节@[4,104)，其他字段原样保留。源SHA-256 `e288b79f95e5b72c2ea66c1695584f025ce44743157afa06b669b85e3ff8662a`。MCAlpha加载器 `0x520b216c` 按这三个区段读取；名称确有用户显示路径，但马车、车轮、粒子、敌方与变体对象同处表中，不能全部当作角色人名翻译。

读取既有存档时100字节名再次覆盖对象，保存也包含角色名称。名称提取与运行字节容量、全字段用途、存档兼容分开验证；当前解析器只读且标记用途复核，不自动更改模型路径或原存档。证据与消费者地址见 FULL_TRANSLATION_PIPELINE.md。

## BGR：已验证的图片包装

2026-10-23：战斗按钮原生读取 `32457` 已验证包装 offset 4 为矩形数量，
offset 8 起为 count×16 字节小端有符号 XYXY 表；GPU 资源对象 `+10/+14`
分别保存数量/矩形指针。FDI 装饰节点的 active/clickable 标记决定这些矩形是否
进入命中列表，图片宽高或 FDI 帧尺寸不必等于命中区域。当前结论绑定实际战斗
BGR 样本，不把所有未知包装字段扩展为同一种结构。见[原生战斗输入链](BATTLE_GAMEPAD_CHAIN_REPAIR.md)。

`tools/resource_image.py` 只接受本样本已验证的TGA/BMP形态，不按扩展名自动支持TXRS。

- 404 TGA：wrapper为12/24/40/56字节，payload固定18字节头、ID0、type2、32位BGRA、descriptor8、底行优先，尾部为26字节零扩展/开发者偏移和TRUEVISION-XFILE声明。坐标字段、包装、透明像素的RGB均保留。
- 18 BMP：wrapper24字节，BM、DIB40、像素偏移54、24位BI_RGB、正height、底行优先，行对齐4字节。实际payload在像素后还有2个零字节，bfSize包含该尾部；不能将其误作损坏或丢弃。未知头字段及行填充保留。
- 像素接口为左上原点RGBA，只能替换同尺寸像素；BMP不支持替换半透明alpha。未知方向、位深、压缩、长度、footer或多重候选均拒绝。

19项受控测试通过；实际422图片RGBA解码→存储像素重编码逐字节一致，并与独立Pillow像素422项一致，源摘要未变。该结果证明容器及像素回建，不证明图片文字重绘、中文布局或游戏显示通过。

```powershell
python tools/resource_image.py --source ORIGINAL_WORKSPACE/BGR --report build/bgr-roundtrip.json
```

报告必须为新的源目录外路径。命令只读，不启动游戏，不自动改写原图片。


## 固定显示字段：防御式回写

`tools/resource_fixed_text.py`复用已验证结构提取器，从原字节提取字段并核对catalog的ordinal、ID、offset、源字节与capacity，才写入独立候选。字段决策逐条保存源摘要、显示名称/说明/内部对象分类及依据；缺失、重复、漂移或内部对象误批准拒绝。

ITM/SGI/CHA名称使用39字节保守上限，双名称合计最多78，低于原取得物品格式的79字节预算；ABI最多59字节加NUL，保留60字节提取范围之外的4字节；ITM说明最多99字节加NUL。仅更新原字符串跨度与新跨度的并集。扩长若碰到未知非零填充则拒绝；头、ID、属性、其他填充及记录长度保持一致。新私有码通过实际NUL边界逆解码，不使用CP949解码修改后的槽。这不是布局或旧存档名称适配的游戏验收。

## Bink1容器及Unicode对话框

Verified：本作18个视频成员为BIKi；文件头44字节起含每轨12字节参数，随后是带低位关键帧标志的N+1个u32帧偏移。每帧音频依轨保存u32长度和载荷，余部为视频。resource_bink.py经全部原成员逐字节往返验证；重建不改音频包。MOV.pak串接完整成员，长度/偏移不能仅因压缩变小而移动。分布式帧尾零填充只取得受控FFmpeg解码证据，未取得游戏解码器验收。

Verified：设置资源为DLGTEMPLATEEX，控件起始DWORD对齐，标题/字体/控件文本为UTF-16LE，类和标题可为ordinal。resource_dialog.py完整原资源1,498字节往返一致，32控件元数据保留。回写只缩短原分配并更新资源目录Size，其他区段及可执行节不变。

## ANI骨骼动画只读布局

支持加载器2c88a绑定的布局：五个little-endian u32为opaque tag、总帧、步长、
采样数、骨骼数；按骨骼存(samples+1)个16float矩阵，首项为绑定参考；之后
逐骨骼为opaque父字段、子引用数和变长u32引用。根父字段可为0xcccccccc，
不得归一化为0。1,818份本地文件完整消费且SHA保持不变；第一字段无版本语义证明。
只读审计工具不回建该格式，不导出姿态数组；限制与反射发现见`ANIMATION_POSE_COVERAGE.md`。

## LPD1原型增量

Verified：LPD1魔数后是zlib流；解压数据含u64目标长度、u32操作数。操作0为u64原文件偏移和u64长度的源引用，操作1为u64长度及变更literal。64字节比较块合并连续同类操作。解码限制目标512MiB，验证压缩结束/尾部、操作边界、源范围、目标长度以及整体SHA-256；来源和目标完整摘要位于外部manifest.json。格式不包含原始游戏整包，生成内容不提交仓库。

Field当前版本的显示标签：offset252、容量18字节含NUL，对应FieldInfo+0x110，Level+0x10cc+0x110=0x11dc；新保存版本4后18字节为同一标签。其余Field布局未全面重解释，构建只锁定该槽及整份源SHA，见[UI_READABILITY_FIX.md](UI_READABILITY_FIX.md)。

翻页284/285/423/424的原128×128源像素中，非零alpha外框为91×21；存储尺寸与原标签绘图区分别记录，包装/动画元数据不改。源像素与截图对照见[UI_ALIGNMENT_FIX.md](UI_ALIGNMENT_FIX.md)。

## WRD 1.3 geometry subset and incremental atlas (2026-10-15)

The bounded reader explicitly accepts 1.300000 and 1.400000 headers with actual source version/hash retained; identical observed native field-read paths and complete EOF checks are documented in MAP_LEGACY_GEOMETRY.md. Five additional local 1.3 resources pass; two still fail index validation and are not silently repaired. Geometry coverage is not navigation coverage. Incremental atlas manifests record selected_ids and each accepted source_version.

## Field static prefix (2026-10-15)

The source-locked read-only prefix reader distinguishes file strides from runtime object strides, preserves unknown script tails and the map -1 sentinel, and never rewrites labels. Field offset0 maps to FieldInfo+4/scene+10d0 (WRD ID); offset8 is the PlayBook ID. Detailed native read evidence and bounded coverage are in FIELD_STATIC_PREFIX.md. This is not a full FLD decoder or navigation graph.

## Minidump MemoryInfoList (offline snapshot query)

Stream16 has a16-byte minimum header: uint32 header size, uint32 entry stride,
uint64 count. Each entry is at least48 bytes: uint64 base/allocation base,
uint32 allocation protection,4-byte padding, uint64 region size, uint32 state,
protection and type,4-byte padding. Validate header+stride*count within the stream,
64-bit region bounds and unambiguous address coverage. An absent stream or uncovered
address is unknown, not proof of free memory; region state describes capture time.
`Dump.memory_region` never queries or attaches to a live process.
## 自有离屏伤害绘制输入（DGP3）

此格式仅用于 `damage_projection_gpu_fixture`，不是商业游戏资源，不进入玩家包。
文件采用小端：`<7I48f6I` 头，依次保存魔数 `0x33504744`、表面宽高、viewport的x/y/w/h、
WORLD/VIEW/PROJECTION三组16浮点矩阵、primitive/count/纹理宽/纹理高/renderstate数/stagestate数。
随后依次保存 `count` 个32字节 `D3DLVERTEX`（`<3f3I2f`）、纹理宽×高个BGRA像素、
`renderstate数` 个 `<2I state,value>` 和 `stagestate数` 个 `<3I stage,state,value>`。
纹理保持原始BGR的存储行方向，UV由原生图形提交；不预先软件投影顶点。
矩阵、顶点、状态来自源锁回放，纹理上传元数据的受控边界由验证报告单独列明。
读取器限制尺寸/数量并拒绝非有限坐标；GPU读回BMP使用负高度记录顶向下行。
