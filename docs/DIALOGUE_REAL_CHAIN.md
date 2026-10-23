# 真实对白、原声与剧情收尾的离线证据

2026-10-23。游戏、设置程序和游戏DLL入口均未启动。自有Win32夹具使用现有
Miles/MP3组件，以音量0播放原声；没有完整游戏副本，没有更新共享模块、设置或存档。

## 结论与未完成项

**已验证**：原生自动结束可以在真实原声仍活动时释放对白action，继而越过剧情
等待并请求转场。现有`dialogue_reveal.cpp`守卫在真实Miles stream下正常等待，
并非只在`tick<400`的模拟状态下通过。所测文字没有尚未揭示就被原生滚动删除。

**未验证**：玩家反馈是否仍发生在当前模块上，以及每处“漏对白”是否同属这一机制。
本轮新增资源审计、真实音频夹具及剧情链回归；**没有新增运行时修复，也不将
玩家未指明场景中的剩余漏句标记已解决**。当前生产守卫未在新证据中失效。

## 资源审计与格式

`audit_dialogue_resources.py`按FLD中的FPB tag绑定文字，不把tag当ordinal。
565份可解析Field中的2,706条opcode700全部找到文字；2,354条找到语音文件，
352条明确为-1无声。其他Field变体逐项列为未支持，不解释为损坏或已覆盖。
最长12条已绑定对白的原声完整解码；缓存绑定源、解码器和参数摘要，不提交商业资源。

- 2,509份SVD为56字节compact头：storage=u32@8，filter=u32@12，40字节参数@16。
- +4为保留的未知metadata，不假定为0/1版本号。
- 两份旧SoftMax签名变体的物理payload从108开始，storage/filter位于60/64。
- filter18表示不安装filter，不是MP3编码编号，此时参数数组不读取。
- 原生Miles打开回调`4c30`改写扩展名并固定seek56。旧头物理位置与这一行为分别记录。
- 固定裁108后FFmpeg可能重新同步而仍返回成功，但会少解首帧，不能采用该时长证据。

## 三条完整实播

`dialogue_audio_fixture`校验输入摘要，实际打开声卡、原始MP3和Miles stream，
静音自然播完，每约20ms记录实际wall/position/total/status。游戏引擎仅用
`DONT_RESOLVE_DLL_REFERENCES`映射，不执行入口；绑定状态查询所需IAT并执行
原生6329。自有manager的声道槽指向真实HSTREAM，不以布尔模型替换播放器。

| 真实绑定 | Miles总时长ms | 自然结束wall_ms | 采样数 |
|---|---:|---:|---:|
| FPB0298 tag8 → SVD1961 | 37251 | 37297 | 1201 |
| FPB0258 tag5 → SVD1598 | 41744 | 41766 | 1344 |
| FPB0738 tag42 → SVD1500 | 54413 | 54453 | 1754 |

三条自然status4→2，每行native6329与直接Miles状态一致。Miles结束时position
可能小于total，不能以两者相等代替实际状态。完整CSV/log留在本地build目录。

## 同一实例的文字、等待和转场回放

`replay_native_dialogue_chain.py`绑定真实FLD/FPB/SVD及完整实播CSV/log摘要；
拒绝seek轨迹冒充全句实播。每帧观察label的+12c像素前缀，在实际删行/对白结束前
检查完整揭示，而不只拼接创建过的文本。

主例为0766.fld/event1/action50：FPB0738 tag42，310字节，SVD1500；原生视口
460×52，自动等待975tick。真实尾序列恰为700→1→4(target663)，没有跳过另一句。
同一Unicorn实例依次执行：

1. 状态/揭字/滚动`5b1ef / 5b9af / 5b735`。
2. 活动对白完成处理`78209`。
3. 真实事件扫描`4ba72`和opcode1的active计数等待。
4. phase6后真实`4b6ef`清理，active从1降为0。
5. dispatcher`71b9b`和opcode4 handler`729b9`。
6. 在真实任务入口`c9fd`捕获31:663请求后停止，**不执行场景加载器**。

| 分支 | 文字完成ms | 清理/转场请求ms | 实播结束ms | 提前量ms |
|---|---:|---:|---:|---:|
| 原生无守卫 | 16900 | 49433 | 54453 | 5020 |
| 现有守卫适配 | 16900 | 54466 | 54453 | 无 |

两分支所有label均完整揭示。1598实际文本例提前2233ms；1961例两分支均在37600ms
完成，原声已在37297ms结束。这一阴性对照保留，不称每条长对白必然提前。

这里是**离线布局边界下的指令回放时间，不是游戏现场测量**。字体测宽仍为明确的
14px自有服务，label/绘图/CRT隔离；首action预初始化，不覆盖完整构造、此前剧情
或完整父UI遍历。Python适配守卫决策；编译后守卫另由真实播放器夹具交叉验证。

## 编译后守卫与真实Miles集成

`dialogue_voice_chain_fixture`编入当前生产源，使用真实FPB、HSTREAM、原生49ecb
播放、6329查询、5c13e完成器。文字完成状态和native tick边界由夹具初始化，
不冒充完整UI更新；尾部seek只用于快速集成检查，不代替完整实播。

- `--unguarded`在真实status4时直接进入phase6，断言退出1。
- 生产钩子在1598、1500原声下保持phase3、自动等待字段0，真实status2后才phase6，退出0。
- 等待日志仅begin/end；撤回精确恢复四虚表槽、五字节播放调用、五Miles IAT槽及manager。
- 隔离夹具恢复无守卫后再次退出1，主验证配置保留守卫状态。

无守卫是显式测试分支，**不是声称当前部署缺少已有守卫**。本轮生产源和共享模块
没有行为变更，没有新的玩家更新包。

## 复现与证据

```powershell
cmake --build build/native --config Release --target dialogue_audio_fixture dialogue_voice_chain_fixture
python tools/audit_dialogue_resources.py --source runtime/data --decode selected --cache build/dialogue-chain-evidence/decode-cache --report build/dialogue-chain-evidence/NEW-resource-audit.json
python -m unittest discover -s tests -p 'test_dialogue*.py' -v
```

支持样本1500的完整实播复现如下，输出目录须为新目录；其他SVD应先使用parse_sound
判断物理payload偏移，不套用这里的compact偏移。音量固定0：

```powershell
$root=(Get-Location).Path
$out="$root/build/NEW-dialogue-audio"
New-Item -ItemType Directory -Path $out -ErrorAction Stop | Out-Null
$svd="$root/runtime/data/SVD/1500.SVD"
if ((Get-FileHash $svd).Hash.ToLower() -ne '372737488d2a96574cadd69faae58e1db9393b8da8f933a6ebf270adff415cff') { throw 'SVD source mismatch' }
$raw=[IO.File]::ReadAllBytes($svd)
[IO.File]::WriteAllBytes("$out/voice1500.mp3",[byte[]]$raw[56..($raw.Length-1)])
$sha=(Get-FileHash "$out/voice1500.mp3").Hash.ToLower()
& "$root/build/native/Release/dialogue_audio_fixture.exe" --dll "$root/runtime/data/Mss32.dll" --audio "$out/voice1500.mp3" --expected-audio-sha256 $sha --native-engine "$root/runtime/data/MCAlpha.dll" --trace "$out/audio1500.csv" | Tee-Object "$out/audio1500-traced.txt"
```

下列回放使用已保留的采样路径；从头复现时把trace和audio-log参数改为上述新目录：

```powershell
python tools/replay_native_dialogue_chain.py --source runtime/data --trace build/dialogue-chain-evidence/audio1500.csv --audio-log build/dialogue-chain-evidence/audio1500-traced.txt --report build/dialogue-chain-evidence/NEW-scene-chain.json
python tools/replay_native_dialogue_scene.py --sample runtime/data/MCAlpha.dll --field runtime/data/Field/0766.fld --report build/dialogue-chain-evidence/NEW-scene.json
```

本地`build/dialogue-chain-evidence/VERIFICATION.txt`保存验证配置
voice_guard=false→true的三态完整命令、输入、逐字输出、退出码和摘要。
`ROLLBACK.sh`只恢复指定隔离验证JSON，不改共享运行；`MODIFIED_FILE.json`仍为true。

## 仍需调查

不全局强塞阻塞或延迟：脚本存在刻意并行动作，少数对白在下一句之前没有opcode1，
这本身不足以认定损坏。后续仍需捕获实际漏句时的文本源、phase、声音对象/stream、
播放状态、action/event游标及销毁归属，区分显示、提前停音、并行覆盖与转场。
