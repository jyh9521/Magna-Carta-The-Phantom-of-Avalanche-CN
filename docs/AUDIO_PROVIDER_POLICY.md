# 采样声音后端候选（2026-10-24）

## 已验证：现场与来源

原始输入只读复制到本地忽略目录，不提交日志、存档或商业DLL。

| 输入 | 字节数 | SHA256 |
| --- | ---: | --- |
| profile.log | 11197607 | `39a86b984c9051984ece8733c7f7ff22a9371c305d74ce0f63a7647429c7cc06` |
| MC01.sav | 23514 | `5770414ea21d7fb5686b440551e541206dda229d801666001cf198b61235ddf3` |

43149行日志含1881次采样启动、38951次碰撞观察。455次启动后仍为
`state_after=0 channel_after=-1`，全部快照有效且`slots_busy=slots_capacity=8`。
第一条在原日志1303行，调用点RVA4943a。这是现场原生分配失败，不是合成调用桩。
字段sample_handle实际取资源对象+4的数据指针，不是Miles 3D句柄；不能据重复缓冲区判定声道复用错误。
尚未把455条逐一绑定到角色、技能段位和声音文件。

`tools/analyze_contact_audio_log.py`重新统计、检查版本4存档CRC、导出场景切换摘要。
`--assert-no-audio-failures`对原日志仍退出1；历史失败不会因构建候选而改成成功。

来源MCAlpha SHA256 `7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e`，
Miles SHA256 `d0db426ebac97dc410b5130c9c74d19bc04151236df85b012823d6cb3d7fb87c`。

## 已验证：原生链与容量

- RVA6685打开数字驱动、枚举后端，原优先索引/类别为9/1、8/1、3/1、2/0、4/0。
  本地EAX2、EAX、DS3D硬件打开失败，随后Dolby Surround成功，报告最大16。
- 软件类别0按后端最大数扣除原有2D、流及保留预算，最终3D池为maximum-8；类别1算法不同。
- RVA52ae按manager+68分配12字节记录及真实Miles句柄；5498找空闲记录，满则-1；54f9释放。
  声音对象48f81失败后保持0/-1，48e54不播放。
- 随游戏提供的DirectSound3D 7+ Software - Pan and Volume本地打开成功，报告64；
  原生软件预算得到56。真实56个3D句柄、原生2D池与两个自有静音WAV流可共存。
  流只打开不播放；没有执行游戏入口、创建游戏窗口或复制完整游戏。

## 候选改动与后备

audio_provider_policy.cpp替换RVA6875的6字节IAT调用（IAT RVA bd518）。守卫检查x86 PE、
时间戳3ed73966、映像大小10b000、初始化/分配函数前缀和原调用字节。
桥保持stdcall栈、非易失寄存器及打开调用LastError，使用原EBP帧中的有界枚举表。

仅在第一轮且原20个优先表DWORD完全匹配时，按完整名称查找该软件后端并调用原打开函数。
成功时首行改成实际枚举索引、类别0，同时更新manager+400870已选句柄。后续容量查询、分配、
播放、释放仍执行原程序。失败/名称缺失时不改任何表项，再调用原首选，保留全部五个后备。
不强制容量、不超后端报告、不抢占、不改音量/速度/事件时间、不补发动画事件、不替换声音文件。
后端能力因机器而异，不保证每台机器都是56。

默认关闭。MC_AUDIO_PROVIDER_POLICY=1或新入口Play-audio-fix.cmd启用；新入口同时开启
既有探针，以setlocal限定环境，返回Play.cmd退出码。原Play.cmd不自动启用候选。

## 原生离线红绿

native_audio_pool_fixture以DONT_RESOLVE_DLL_REFERENCES映射源锁定映像，不运行DllMain；
绑定真实Miles和必要CRT，只有过滤器枚举被自有空枚举边界替代。执行原生6685、52ae、509a、
51de、5498及54f9，不重写算法。检查池边界/释放复用、两个不播放的流、空映像/未知调用点拒绝、
重复安装和6字节精确撤回。

| 模式 | 3D池 | 16个请求接受/失败 | 退出码 |
| --- | ---: | --- | ---: |
| baseline | 8 | 8/8 | 1 |
| modified | 56 | 16/0 | 0 |
| fallback，强制新首选失败 | 8 | 8/8 | 0 |
| rollback，初始化前撤回 | 8 | 8/8 | 0 |

```powershell
cmake --build build/native --config Release --target workspace_profile native_audio_pool_fixture
build/native/Release/native_audio_pool_fixture.exe ENGINE_DLL MILES_DLL --baseline
build/native/Release/native_audio_pool_fixture.exe ENGINE_DLL MILES_DLL --modified
build/native/Release/native_audio_pool_fixture.exe ENGINE_DLL MILES_DLL --fallback
build/native/Release/native_audio_pool_fixture.exe ENGINE_DLL MILES_DLL --rollback
python -m unittest discover -s tests -p test_audio_provider_policy.py -v
```

这证明本地受支持后端解除8声道瓶颈，不等于佩里西亚F11、全部角色段位/打击时序或超过56路
峰值已通过游戏实测。待人工候选入口复测，保留退出后的cache/profile.log和段位录像，核对
SELECTED/FALLBACK、实际slots_capacity、分配失败数和听感。

## 安装与撤回

MagnaCarta-audio-provider-candidate-20261024.zip仅适用已经安装上一份诊断包的平铺目录。
15项事务含12个自有模块、两份清单及新入口，原诊断入口、存档和设置不变。
来源诊断ZIP须匹配1395558485150818f1b409a66b6e3a07497f4b3e3e57f0ed969b8db78736cc91。
构建器核对载荷/双清单，安装器拒绝混装，独立备份.audio-provider-fix-20261024不覆盖旧备份。

```powershell
python tools/build_audio_provider_update.py --previous DIAGNOSTIC_ZIP --previous-sha256 DIAGNOSTIC_SHA --module build/native/Release/workspace_profile.dll --work build/NEW-audio-policy --output dist/NEW-audio-policy.zip
powershell -NoProfile -ExecutionPolicy Bypass -File Audio-Provider-Fix-20261024/Update.ps1 -Action Rollback -Runtime .
```

## 黑屏和卡墙仍开放

所交存档版本4、场景715、标签与0715一致；CRC32计算值与尾值均为9981b2f7，不等于完整结构验证。
FLD715/event3条件含304(10000,1)、101(27,0,2)，动作末尾为4(254,0,0)。现场两次记录715→254，
最后一次254/map109继续约7.4秒。脚本目标与现场相符，不证明画面绘制。
DDraw日志以初始化/能力与正常卸载为主，缺少设备丢失报错不能排除显示问题。
探针未记录淡入淡出、相机/提交/最终帧，黑屏根因未确认，不能宣称坏档或套用旧读档Exception修复。
碰撞尾部的纯Z重力/落地也不是水之迷宫吸入卡死的证据。
