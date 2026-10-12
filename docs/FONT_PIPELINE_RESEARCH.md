# 文本与字体管线首轮逆向

## 范围与版本

显示组合已完成当前场景反馈：会话 session-20261012-141840-658 退出码 0，窗口观察器保存 41 个采样，1080 行候选报告无问题。该反馈不替代实际渲染目标测量或全流程 P1 验收。当前显示副本保留，后续 P0 回到最小中文技术管线。

静态分析对象为副本 MCAlpha.dll，SHA-256 `79e4c3d6af4afb2b75367a2b26fd8450ad25fa9f738612ea96809e312d33cb6f`，x86。REA 使用 Ghidra 12.1.4 的只读 headless 分析，未启动游戏、未加载商业 DLL 执行、未修改原始字节。完整 Evidence 及可复用快照保存在忽略的本地 build/font-research-evidence/main，分析会话已关闭。
反编译输出是恢复的伪代码，不是原始源码。以下地址为该文件的静态 VA，RVA 需减 ImageBase 0x52000000；不套用其他版本。

## 已验证的函数路径

| 功能 | 静态地址 | REA Evidence |
|---|---|---|
| 两套 Eng/Kor/Chi 字体加载 | 0x5201e9e0 | ev_486d7eefd7c583e872cf986b5af989601f0ef33aa57dc5b37c5a8e5f8375bb7e |
| Kor 文件读取 | 0x5201f1b0 | ev_742e16b69218502e7b8bc1de6582e4085bf269c385c4a1f57505a1b42c074bda |
| Eng 文件读取 | 0x5201f2c1 | ev_c1392059549b714889ee22de16e6584a97473d37e7c26e8b8a6a484297eb19d6 |
| Chi 文件读取 | 0x5201f3dd | ev_a5473fdf2c57e6696e4b6ce241c8264f5f0ba6364eb5d3c9d9e1b604a61dcdc8 |
| 字宽计算、字节消耗 | 0x5201f5ad | ev_e94c1869f443c1edce72b549bb13042750de78f61f92beb30f115dc1658fd3d1 |
| 字体选择及单字绘制 | 0x5201fb39 | ev_1eb17b365091313f26aceb6d58e5dc14ca48bf1f0d208db79322a1b37686742e |
| 逐像素 LSB-first 位图读取 | 0x5201fd21 | ev_4098707aeb9f542b54fb8d2205108923cb7b95110318456e34040c91d65f0bb6 |

构造路径加载 Font/Eng0/1.dat、Kor0/1.dat、Chi0/1.dat，不是按目标语言只选择一类文件。三个加载器先读取 100 字节头；头偏移 42 非零时，读取 offset92 指定长度的逐槽 advance 表；再读取 offset96 指定长度的位图区。逐像素读取以 slot×pitch×height + y×pitch + x/8 定位字节，使用 x%8 对应最低位至最高位掩码。

## 实际文件结构

- u16@88：两套分别为 14、22，绘制的行数与固定宽度均使用此值。
- u8@90：行跨度分别为 2、3 字节；1-bit 位图 LSB-first。
- u32@92：Eng 351、Kor 6239、Chi 13151 槽；u32@96 精确等于 count×height×pitch。
- Eng 的头 byte42 为 1，位图区起点 451；Kor/Chi 为 0，位图区起点 100。Eng advance 范围分别为 4..14、4..22。
- u16@86 等于 A3A0/B0A0/CAA0，但目前观察到的字符索引函数使用代码中的固定常量，不能只改头字段就改变编码。byte43 的完整语义及其他头部字段保持未知并原样保留。
- 六文件均解析/原样重建字节一致，字体文件没有回写到任何游戏副本。

## 运行时字节路由

| 首字节条件 | 字体 | 消耗字节与槽计算 |
|---|---|---|
| < A4 | Eng | 1 字节；首字节 - 20 |
| A4..AF | Eng | 2 字节；big-endian 双字节值 - A3A0 |
| B0..C9 | Kor | 2 字节；big-endian 双字节值 - B0A0 |
| >= CA | Chi | 2 字节；big-endian 双字节值 - CAA0 |

Kor 索引函数 Evidence ev_ca82a3944675dff84415817d7d2929c31f127b6e1b84b2a5292a0dd72e3e1117；Chi 索引 ev_a26c984df79d092e1ecf1349b74e95e415a0ab010ab58d95aaef0766fcb805f3；Eng 索引 ev_28cf5c688ed267f1c195903bc36766fcdad4fa00b1e133401a98f91c01b86b39。
文件槽数包含编码数值间隔，不能当作同样数量的有效字符。CP949 扩展区首字节 81 等会被该路径按单字节处理，不能因 Python 能编码就认定引擎支持。
字宽与绘制均使用该分类，但换行、控制码、文本来源到绘制的完整调用链仍未完成；本工具不解释或重写保护 token。

## 首次字符覆盖结果

两套原字库的“中”使用 CP949 F1E9、Chi 槽10057；“文”使用 D9FE、Chi 槽3934。槽在范围内，解码位图存在墨迹；静态检查通过，不作为已经显示中文的游戏证据。
“测”“试”“汉”“龙”等简体字不能按 CP949 原样编码。不能直接把全部译文写成 CP949、GBK 或 UTF-8，也不能按 Chi 文件名声称已有完整简体字库。
下一阶段先追踪确定的可见文本资源及控制码，在独立样本验证“中文”两字的运行路径；再设计可复现的目标字符映射、字库生成与编码适配，保持 locale 数据与通用工具分离。大规模翻译仍等待最小中文证明和跨作品术语核实。

## 可复现检查

```powershell
python tools/resource_font.py --source build/runtime/render1080-game/Font --report build/font-research-evidence/main/font-roundtrip.json --text "中文测试"
python -m unittest discover -s tests -p "test_*.py"
```

报告必须为新路径。解析器检查头部、总长、乘积关系、字宽/行跨度、槽和替换长度；未知头部原样保留。89 项单元测试通过，包括合成字形替换、其他槽保持、LSB-first、截断及槽路由。实际六文件原样往返通过，独立字体副本单槽修改和回滚作为构建基础测试，不部署到游戏。
