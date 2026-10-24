# 多地图卡墙与连招后段缺声调查

2026-10-24。两个独立的玩家现场问题，均保持未解决状态。
初始排查未启动游戏或设置程序，未修改共享运行目录、游戏资源、存档或增强设置，未创建完整游戏副本。
后续新增可选探针及独立诊断更新包；本机共享运行目录仍保留原模块，未自动安装候选。

## 反馈与复现判据

| 标识 | 反馈 | 真正复现所需观察 |
| --- | --- | --- |
| MOVE-02 | 贴墙行走或接触场景物体时卡住，迷宫窄路最明显；“水之迷宫”靠近中央建筑会被吸入并卡死 | 正常进入可移动状态，经过触发步骤后角色位置向障碍物内偏移并停滞，反方向输入也不能脱离；保留前后位置、高度、场景和控制状态 |
| AUDIO-02 | 所有角色的F10普通辅助及F11暴走辅助，在后面几段同时缺角色语音与打击音效 | 同一角色、招式及连招段位中，动作实际继续，但角色语音和打击音效事件没有开始或提前结束；BGM状态仍单独记录 |

以上为玩家补充的触发条件，不作为本机已经重放出故障的证据。
“水之迷宫”尚未与本地Field编号绑定，不直接将其等同于“水之神殿”或“水之遗迹”。

没有现场录像、触发步骤或相关状态轨迹时，不将根因假设写为结论。
现有独立夹具尚未复现上述两项精确症状；本轮没有可证明修复的红绿回归。

## 已验证的本机状态

- 当前源码起点为 `40f040a`，任务开始时工作区干净。
- `runtime/runtime.json` 中 `data` 与 `files` 共554个摘要全部匹配，缺失/不匹配0个。
  这只验证本机共享目录，不代替玩家实际启动目录或已安装版本的检查。
- 当前 `runtime/config/enhancements.json` 为60帧、手柄关闭、自由视角关闭。
  不能据此推断玩家现场使用同一配置，也不能据此排除某个模块。
- 既有 `runtime/cache/profile.log` 更新时间为2026-10-23，包含动作插值及遇敌开关日志，
  没有可绑定到本次卡墙现场的角色位置/碰撞轨迹，也没有后段战斗语音事件记录。
  已在 `build/movement-combat-audio/` 保留原日志副本，避免下一次启动覆盖唯一现场候选。
- `motion60_fixture.exe` 通过996项检查，含队列世界矩阵精确恢复及逻辑tick保持。
  `world_gamepad_fixture.exe` 通过134项检查。二者使用自有场景/调用桩，
  不执行地图碰撞和真实战斗动作语音，因此不是本次故障的复现或反证。

## 既有修正和夹具的实际边界

1. `field_return_height.cpp` 明确限制在场景757、event2及对应脚本身份；
   不把该补丁扩展到所有地图，也不将全地图卡墙归结为同一高度参数。
2. `dialogue_reveal.cpp` 的等待守卫作用于剧情对白自动到期；
   战斗连招后段缺声独立追踪，不通过延长剧情文本停留时间代替修复。
3. `replay_combo_assist_chain.py` 和 `replay_rage_combo_assist.py` 验证输入、原生评分、
   动作选择。`selected_action_animation_boundary` 是明确的叶边界，
   选中正确动作不证明后续动画事件已触发声音或播放器播完声音。
4. 静态原生前进函数RVA `652b4` 写入actor+`16c/170/174`并提交类型4状态。
   该静态观察不证明地图碰撞通过，也不证明本次卡墙原因。
   MCAlpha.dll SHA256为 `7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e`；
   REA证据为 `ev_75b77bf13db0e3be8903d84b079fd981a7495217ea7ebad93d80391aaeb46bfa`。

## 下一步所需最小输入

- 实际启动的 `Play.cmd` 所在目录；走动接触墙面/物体的触发条件已经确认，无需重复询问。
- 一段从正常走动到卡住、再尝试反向脱离的短录像；任选一个容易触发的位置即可，
  不要求逐地图列举，也不要求特意提供故障点存档。最近一次普通存档可作为起点。
- 全角色、F10/F11以及打击音效一并缺失已经确认，无需重复询问。
  后续现场补充只需精确起始段位、BGM状态及可用于绑定地图编号的画面。
  对应的一段带声音录像可用于绑定动作与播放事件。

先用同一输入重放出精确症状，再选择最小运行时探针和单变量对照；
不预设60帧、碰撞资源或声道耗尽为已确认根因，不盲目改位置、穿墙开关或音量。
游戏现场操作保持手动；不要用本轮通过的离线夹具代替实际验收。

## 可选碰撞与声音探针

已实现 `contact_audio_trace.cpp`，只有进程环境变量 `MC_CONTACT_AUDIO_TRACE=1` 时安装。
普通 `Play.cmd` 与增强设置保持原样，不默认开启，不改变F10/F11调度或动作选择。
游戏仍由测试者手动运行，诊断更新包不是修复包。

### 源码绑定与观察内容

- 碰撞：字段场景vtable+48（RVA `c1304`）原目标 `6ed4e`；仅观察scene+1564对应的玩家。
  记录Field/Map编号、传入位置/速度、原生修正结果、调用后速度和角色位置。
  原函数仅调用一次，返回指针与参数副作用原样传回；不再额外调用点/线碰撞查询，
  避免改写碰撞树的最后命中平面状态。
- 采样音效：RVA `48e54` 原生启动方法；记录启动前后状态/声道、资源句柄、调用点和
  混音槽占用。只观察，不强占声道、不重播、不改音量、不增加声音对象。
  这不是每种动画事件或长对白stream的全覆盖；没有一条启动日志不单独证明某招式没有声音事件。
- 两处钩子分别验证原始代码、vtable槽、PE32/x86、映像大小及时间戳。
  保留调用前后LastError和原页面保护，支持幂等安装、精确移除和未知代码零写入拒绝。
- 每秒最多12条未改速度的碰撞、96条速度修正和128条声音启动；丢弃数量单独记录为
  `CONTACT_AUDIO_DROPPED`，下一窗口继续，不存在运行一段时间后永久停止观察的总量上限。
  碰撞每条是一次轴向求解，不将其误当成一整个逻辑tick或最终位置提交。

### 静态发现与未知项

**已验证（静态原生代码）**：`6ed4e` 在查询起点已处于实体内部时，将请求速度清零并返回零。
这说明进入实体后的移动求解会阻止正常脱离，但尚未证明中央建筑处首次吸入的来源。
证据 `ev_0b873f8e8220561f9b72a235d5816d845ce79c7d1486fed1a6c112156d894337`。

**已验证（静态原生代码）**：`05498` 扫描manager+64的12字节槽，容量来自+68；全占用时返回-1。
`48f81` 收到-1时不进入就绪状态，`48e54` 随后跳过播放。静态证据分别为
`ev_8d4269c14c93096e1051809ed133371475a7e43ad708540cd6276f9eed249118`、
`ev_2768601f4ce520b87777807e3771807a0af2c9a58f9de689b9cce68c593e960f`。
这是探针字段的依据，不是现场已经声道耗尽的结论。

**未验证**：水之迷宫对应的Field编号、第一次穿入的计算、后段是否未产生声音事件或播放申请失败。
没有根据上述静态机制直接修改物理参数或扩大声道池。

### 交付与手动取证

`dist/MagnaCarta-contact-audio-diagnostic-20261024.zip` 适配已交付的
`MagnaCarta-clean-game-all-in-one-overlay-v2-20261023.zip`，安装前逐项核对旧摘要。

1. 游戏退出后，将诊断包完整解压至原 `Play.cmd` 所在目录，双击 `Install-Contact-Audio.cmd`。
   `MODIFIED PASS files=15` 表示安装完成；结果窗口保留，输出写入 `Contact-Audio-Install.log`。
2. 手动启动新建的 `Play-contact-audio.cmd`，复现水之迷宫中央建筑吸入后尝试反方向脱离。
   退出游戏后立即将 `cache/profile.log` 另存为卡墙日志。
3. 再用诊断入口测试一次F10或F11后段缺声，退出后立即另存新的 `cache/profile.log`。
   两份日志分别保留，后续启动会覆盖cache中的上一份日志。
4. 普通入口仍是原 `Play.cmd`，默认关闭探针。不要把 `CONTACT_AUDIO_READY` 当作故障已经修复。

更新只涉及12份自有模块、两份摘要清单及一个新入口；不修改游戏资源、存档、设置、旧撤回目录。
独立备份目录为 `.contact-audio-trace-20261024`。精确撤回：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File Contact-Audio-Trace-20261024/Update.ps1 -Action Rollback -Runtime .
```

### 离线验证及边界

自有 `contact_audio_trace_fixture` 的未安装观察基线退出1，安装探针后退出0。
该红绿只表示观察能力从无到有，不是水之迷宫或连招缺声已经复现/修复。
835项检查验证11个栈DWORD的碰撞ABI、返回指针、向量副作用、声音状态、调用前后LastError、
失败分配观察、限频恢复、RX页保护、未知代码拒绝和整幅自有映像的字节精确撤回。
夹具中的声音分配失败是显式自有调用桩，不冒充现场混音器复现。

真实候选模块与交付ZIP另在最小自有文件夹具中执行Verify、安装、重复安装、CheckInstalled、
独立复制后的精确撤回和存档/设置哨兵保留；没有复制完整游戏，也没有启动游戏。

```powershell
cmake --build build/native --config Release --target workspace_profile contact_audio_trace_fixture
build/native/Release/contact_audio_trace_fixture.exe --baseline # 预期退出1
build/native/Release/contact_audio_trace_fixture.exe            # 预期退出0
python -m unittest discover -s tests -p test_contact_audio_trace.py -v
python tools/build_contact_audio_update.py --previous SOURCE_OVERLAY.zip --previous-sha256 SOURCE_SHA256 --module build/native/Release/workspace_profile.dll --work build/NEW-contact-audio --output dist/NEW-contact-audio.zip
```

## 本地证据与复查

`build/movement-combat-audio/baseline-state.json` 保存554个清单比较结果、
配置及58个模块/配置/Walk/系统语音表/技能表文件摘要；日志仅保留本地，不提交商业资源。

```powershell
build/native/Release/motion60_fixture.exe
build/native/Release/world_gamepad_fixture.exe
$env:PYTHONPATH="$PWD/runtime/dependencies"
python -m unittest discover -s tests
python tests/check_runtime_docs.py --expect modified
```

上述命令检查既有回归与文档一致性，不运行商业游戏；结果不作为MOVE-02/AUDIO-02已修复的证据。

初始排查结果：完整回归890项，1项按条件跳过，其余通过（343.014秒）；
文档检查48项通过。单独复查F11的5项及动作队列世界矩阵的1项同样通过。
这些结果没有扩大碰撞或战斗动画语音的覆盖边界。

加入可选探针后：完整回归897项，1项按条件跳过，其余通过（315.308秒）；
最终单独复查7项诊断/安装事务回归通过。交付ZIP含15项事务变更，大小1,416,549字节，
SHA256为 `1395558485150818f1b409a66b6e3a07497f4b3e3e57f0ed969b8db78736cc91`。
本机共享运行目录554个清单项及58个保护文件仍与初始快照一致。
