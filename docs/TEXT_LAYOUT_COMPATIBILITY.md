# 原生文本框字符步长适配

## 已验证的静态差异

适用 MCAlpha.dll 大小1,089,536，SHA-256 `79e4c3d6af4afb2b75367a2b26fd8450ad25fa9f738612ea96809e312d33cb6f`。完整函数位于 RVA `0x1efcd`，72字节；本样本原始文件偏移恰为同值，不能推广到其他PE。

原生 Font 的 Chi 路由按双字节绘制，但文本框步长仅 A4..C9 返回2，CA..FF返回1。自动换行构造前缀时由此拆开私有码。两条函数和调用证据见 [字形映射](NATIVE_GLYPH_MAPPING.md)。

最小修改为 RVA `0x1f000`，即时数值 CA→00，指令 `83 FA CA`→`83 FA 00`。MOVSX 后进行有符号比较，不按无符号范围解释：

| lead | 原步长 | 候选步长 |
|---|---:|---:|
| 00..A3 | 1 | 1 |
| A4..C9 | 2 | 2 |
| CA..FF | 1 | 2 |

CA..FD 中只有编码器明确分配且槽有效的代码可写入译文。FE/FF 虽在分支上返回2，仍不构成字库支持；不生成这两个lead。81..A3行为未放宽，不能据此声称UHC支持。

## 实现与恢复

`src/runtime/native_text_step.cpp` 为显式启用的进程内模块。启动器原有完整EXE/DLL摘要校验不放宽；模块另校验PE32、I386、SizeOfImage与整函数72字节，只允许原即时CA或已安装00。其他上下文不匹配时拒绝，不静默继续。写入后刷新指令缓存并恢复页权限；写入或恢复失败撤回原值。

`--native-text-step` / PowerShell `-NativeTextStep` 默认关闭，只影响启动器新建的隔离进程；不扫描或挂接既有游戏。步长选项与注册表夹具模式互斥。运行时预期上下文拒绝会记录 `NATIVE_TEXT_STEP_REJECTED` 并使隔离进程失败，不继续加载有半字符风险的译文。

安装文件和所有运行副本的MCAlpha.dll保持原摘要；退出进程即丢弃变化。受控模块也提供关闭恢复接口并验证CA恢复，仅供测试与受控生命周期使用，不作为热切换承诺。全文资源和字库最终部署时必须同步启用，不单独发布此选项。

## 验证结果

Win32 Release构建成功。自建隐藏内存镜像夹具核验全部256 lead、单字节变化、重复安装、精确恢复、截断镜像、未知即时数值、变更上下文及错误架构拒绝：

```text
NATIVE_TEXT_STEP_FIXTURE PASS leads=256 changed_bytes=1 rollback=exact mismatch_rejected=true commercial_code_executed=false game_started=false
```

只读检查实际DLL的摘要、大小、72字节上下文；4,795个候选私有码的原步长1、修改模型步长2，ASCII及原有A4..C9行为不变，混合ASCII/控制字串前缀不拆对：

```text
TEXT_LAYOUT_STATIC PASS leads=256 private_pairs=4795 baseline_step=1 modified_step=2 source_unchanged=true commercial_code_executed=false game_started=false
```

```powershell
python tools/verify_text_layout.py --module ORIGINAL_WORKSPACE/MCAlpha.dll
python -m unittest discover -s tests -p "test_*.py"
```

上述只读命令不启动游戏。4项新增回归与原161项合计165项通过。既有焦点、注册表隔离和纹理夹具分别回归，图形探针不作为本轮测试对象。

## 保留边界

未执行商业指令、加载商业DLL或启动游戏。控制码静态调查确认 `$n/$N` 两字节、`$dNN/$DNN` 四字节且延迟1..99；其他控制码保持原值和顺序，不虚构颜色/等待功能。自动换行不依赖空格，仍无中文标点禁则；极窄文本框可能产生空前缀，最终布局校验须覆盖。

文本缓存的strlen/strcpy与Font绘制静态链没有观察到代码页转换；渐显更新像素宽度，不再次按CP949解码。实际对话分页、跳过、延迟、混排、超长串与存档兼容仍留待完整流程后的统一验收，不把受控夹具作为游戏通过记录。
