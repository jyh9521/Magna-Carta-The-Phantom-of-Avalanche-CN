# 对话点击即时显现

## 已验证的原因与原生状态

调查样本为 `runtime/data/MCAlpha.dll`，1,089,536 字节，调查时 SHA-256
`5c701de93af6267b959c49e6927bee525bc0f3c68c8c6f51413515d13809d427`。
本次标点修正候选为 `7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e`。
两者唯一可执行节 `.text` 均为 RVA `0x1000`、770,048 字节，SHA-256
`1902718249d9783d5035c6640c101916030029cdd62930f03be5261fdaa07928`。
文本数据变化不改变下面的原生指令证据；启动器继续全文件摘要锁定。

Verified（REA/Ghidra 12.1.4 静态分析）：

- 对话事件函数 `0x5205c277`（实际代码至 `0x5205c305`）仅在 sender==this、event 为 `0x14`/`0x3b`、对象 `+0x190==3` 时执行结束状态 6。
  渐显状态 2 对相同输入没有即时显现处理。这不是中文解码速度造成。
- 原生更新 `0x5205b9af`，分析体至 `0x5205c13d`，执行控制码、自动换行及像素渐显。
  `+0x1bc==1` 时递增最近文本 label 的可见宽度；速度来自 `+0x1cc`。
- 状态 2 为渐显，3 为整段结束等待，4 为窗口装满后的原生滚动处理。
  直接循环至 3 会跳过长对白前部，因此不能把“全部显现”实现为无限快进。
- 原生事件/更新函数由两个对话虚表 RVA `0xbfcec`、`0xbfee4` 共享；更新槽为 `+4`，事件槽为 `+36`。
  全镜像精确查找事件函数指针只有 `0xbfd10`、`0xbff08` 两处。
- 原生输入离线执行确认：左键按下产生 event `0x3b`，Space 释放产生 event `0x14`；Space 持有 counter=2 不会重复产生确认事件。

证据 ID：
`ev_cfb931435cfb7fdd517390e4c57790e319437cd838ba58c3acad1ab25bdd34a2`（事件），
`ev_5ae540fd07c78f0818d298ed9e7dfe388c1491f180db3a17d16fbe2d3f85e3f8`（渐显/布局），
`ev_662e4fce197820f3401e314d5ba73c2606e51ddc0143975d9c80bd58f1339c72`（鼠标确认事件发送）。
反编译代码只用于分析，不是原始源码。

## 实现

`src/runtime/dialogue_reveal.cpp` / `.h` 在既有中文字符步长适配成功后默认安装，
原版磁盘 DLL 不因对话功能而写入。`MC_DIALOGUE_REVEAL=0` 可在启动前关闭，退出进程丢弃全部对话钩子。

只在本对象收到原生左键/Space 确认事件并处于状态 2 或 4 时：

1. 暂时把原生像素步长设为 32767，调用原生布局更新，最多 4096 次；不自行重新解析文本。
2. 状态 3 时停止；状态 4 时补全当前末行并暂停此对象更新，保留剩余源文本指针和原生滚动状态。
3. 恢复原步长并清除这次显现已消费的文字等待。该输入始终被消费，不在同一次输入里结束对白。
4. 第二次独立输入在状态 3 仍执行原生结束逻辑；满框状态 4 则只解除暂停，原生继续滚动/阅读剩余文字。

首次点击时已经在自然滚动状态 4 也可补全末行并暂停。
其他事件、其他 sender、其他状态走原函数；正常不点击时维持原来的渐显速度。
暂停按对象地址、源缓冲区和状态识别；对象重置会在下一次更新清掉暂停。

安装检查 PE32/I386/SizeOfImage、原生更新与渐显的指令上下文、事件函数全部 143 个代码字节 FNV-1a、四处虚表槽。
四槽要么全原始，要么全为当前模块钩子；混合状态拒绝，写入失败撤销已完成槽。
`removeDialogueReveal` 按同样守卫精确还原四槽。
完整来源身份由既有启动器 SHA-256 校验承担，FNV 只是上下文漂移守卫。

## 复现命令与结果

可选离线依赖沿用 `tools/requirements-native-replay.txt`；不加载 DLL，不启动游戏。

```powershell
python tools/replay_native_dialogue.py --sample runtime/data/MCAlpha.dll --report build/text-dialogue-repair/dialogue-native-replay.json
python tools/replay_native_dialogue.py --sample build/prompt-punctuation/candidate/MCAlpha.dll --report build/text-dialogue-repair/dialogue-localized-replay.json
python -m unittest discover -s tests -p test_native_dialogue_replay.py
build/native/Release/dialogue_reveal_fixture.exe
```

实际退出状态均为 0：

```text
NATIVE_DIALOGUE_REPLAY PASS cases=6 mouse_space=original_dispatch baseline_phase=2 modified_phase=3 prefix=5_to_639 second_input=phase6 source_unchanged=true game_started=false
DIALOGUE_REVEAL_FIXTURE PASS inputs=mouse_space reveal=complete advance=separate long_page=paused_resume bounds=4096 rollback=exact guards=2 game_started=false
```

Python 新增 3 项测试通过，包含未知摘要拒绝、同路径/硬链接报告覆盖拒绝及原生路径回归。
Win32 Release 的 `dialogue_reveal_fixture` 和 `workspace_profile` 构建成功。

### 原生 replay 证明范围

- 原生鼠标/键盘分发及原生事件执行：基线确认输入后状态仍为 2、可见像素前缀仍为 5。
- 自有边界 trampoline 调用真实原生渐显两次后为状态 3、前缀为 639；第二次独立原生输入为状态 6。
  此处 modified adapter 是 Python 离线边界适配，并非编译后的 DLL 钩子。
- 真实原生换行/控制码指令：受控 `ABCDEFGHIJKL` 在 56×22 框构造 `ABCD` 后停状态 4，源游标 4/12，后 8 字节未消费。
- 受控 `AB$nCD$d12EF` 经原生控制码处理得到 `AB`、`CD`、`EF` 三段，游标 12/12、状态 3。
  字体测宽、label 创建、堆/CRT 和变换服务是明确的自建边界；未观察游戏实际渲染。
- 编译 C++ 夹具独立覆盖即时补全、第二次确认、满框暂停/恢复、自然滚动时点击、对象重置、其他 sender/事件不变、4096 次上限、四槽逐字节回滚和两类拒绝守卫。

## 玩家验收

从原有 `runtime/Play.cmd` 或各显示配置入口进入同一存档，不需要新开档。

1. NPC 对话正在逐渐出现时单击左键：当前框立即补齐，但不切到下一段。
2. 同场景按下并放开一次 Space：同样补齐。按住 Space 不应连续结束对白。
3. 再次单独确认后才继续/结束该段。
4. 找到超过一框的对白：首次补满当前框并停住，再次确认继续后文，不能只看到尾句或丢掉后文。
5. 检查含 `$n`、等待码和中文私有码的混排对白、带人像对白；菜单点击/获得物品提示不受影响。

以上自动验证不等于游戏内验收。本次未启动游戏、未操作存档；实际人像布局、长对白阅读节奏和真实硬件输入仍待玩家确认。
