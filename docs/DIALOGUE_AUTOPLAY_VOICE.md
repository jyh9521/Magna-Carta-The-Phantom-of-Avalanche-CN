# 自动对白尾部与原声完成状态

2026-10-23。全部调查、编译、回放与回滚均未启动游戏或设置程序，未改存档。

## 已验证的机制

源绑定 `MCAlpha.dll` SHA-256 为 `7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e`。

- 对话构造器 RVA `5ab40` 创建声音对象（类虚表 `be620`，控件标识 `15c`），
  读取原声时长、计算文字像素步长，然后在 `5afee` 调用 `49ecb` **开始播放**。
  `49ecb` 不是析构；它调用音频管理器并将声音对象 `+124` 置为播放状态 2。
- 原声时长方法 `4a16e` 将毫秒除以 1000 再乘 30，得到原生逻辑帧数。
  构造器最后 `5b06f` 又将文字步长 `+1cc` 固定为 5；此前按原声时长算出的步长不再决定实际揭字速度。
- 完成处理 `5c13e` 只检查对话等待计数 `+1d0`。计数为零时直接转阶段 6，
  没有查询原声是否仍在播放。外层脚本 `785be`、`78e40` 将阶段 6 视为对白完成并清理后继续。
  因此「译文已经揭完、原声尚未结束」确实存在自动提前推进的机制。
- 原生查询 `6329` 经 `5e27` 定位声道，再以 `AIL_stream_status` 的状态 4 判断播放中。
  修正采用这项真实播放状态，不给每条台词附加固定秒数。

REA 静态证据：构造器 `ev_26bc264f7111ff47cb7fbd395f03a570ee1712b24b84f8c0cc6881e600b27f44`；
播放 `ev_e27044e458b621b125613353f30e0ad7158d42e139bd2c530cb1acfe408ec41d`；
时长 `ev_7bac0e5590eacf02d6c414d663ade77b80358a0c9d5e3d05772f2f53ea884beb`；
播放状态 `ev_f566d16c9eda318e07d9435bd5cf91bb9e41ccc78e78b08f6d1ca888f08956d3`。

这些证据验证机制；尚未采集玩家现场音频，不将该机制冒称为每处反馈的唯一原因。

## 修正

`dialogue_reveal.cpp` 复用现有对话模块，额外锁定构造器播放调用上下文及音频查询指令。
调用桥只在原生构造器现场读取 `EBP-64` 的对话指针与 `EBP-2c` 的原声帧数，
随后保留普通函数调用约定，原生播放依旧执行。

对话进入阶段 3、自动等待已到零、对应原声仍在播放时，暂时将自动等待设为 -1，
执行原来的完整 UI 更新，再恢复零。输入分发仍运行，真正的鼠标/空格确认立即推进。
自动等待尚未到零、手动等待模式、无声对白与其他阶段不改。

关联验证同时包括对话地址、源缓冲区、声音类、声音资源、声道与 Miles stream 句柄。
新语音登记、对象/源/声道复用、播放结束或关联失效会清除旧关联。
关联上限 64 条；额外寿命上限为构造器原声帧数 × 34ms + 3000ms，异常/失效音频不永久卡住对白。
`DIALOGUE_VOICE_WAIT` 只记录每次等待的 begin/end，不逐帧刷日志。
撤回同时精确恢复原有四个虚表槽和五字节播放调用。

## 离线回归

沿用 Win32 工程：

```powershell
cmake --build build/native --config Release --target dialogue_reveal_fixture dialogue_image_fixture workspace_profile
build/native/Release/dialogue_reveal_fixture.exe
build/native/Release/dialogue_image_fixture.exe runtime/data/MCAlpha.dll
python -m unittest discover -s tests -p test_dialogue_autoplay.py
python tools/replay_native_dialogue_autoplay.py --sample runtime/data/MCAlpha.dll --resources runtime/data/Fpb --report build/dialogue-autoplay.json
```

新 C++ 回归配旧生产源实际失败：
`FAIL autoplay must wait for still-playing original voice`，退出 1。
修正后 `DIALOGUE_AUTOPLAY_VOICE PASS`，退出 0；独立还原副本恢复旧摘要后，
同一新回归再次产生同样失败、退出 1。主生产源码保持修正状态。

回归覆盖实际调用桥构造器栈、原声仍播/停止、手动推进、更新中的输入、源地址复用、
声音结束、stream 复用、异常时长、有限超时及仅状态转变日志。
真实 Windows PE 映射覆盖生产指令守卫和五槽精确撤回，不执行 DLL 入口。

原生指令回放补充：

- 四项无输入揭字/控制码/自动倒计时检查与六项多屏滚动检查。
- 最长五条已汉化 FPB 台词为 434、346、338、326、324 字节；实际原生链表插入、
  行滚动、删除与结束处理全部执行，各 label 拼接后逐字节等于去除换行控制码的源文本。
  字体测宽、label 和音频状态仍为明确的自建边界，未声称观察实际画面。
- 自建 400-tick 声音边界下，真实原生完成指令的旧行为在 tick 0 结束，
  修正适配在 tick 400 结束；tick 10 手动确认仍在 tick 10 结束。
  音频边界不是现场录制音轨，不能据此声称测得具体剧情原声时长。

## 人工验收边界

真实长对白的音频尾部、场景切换和最终画面仍待测试者通过原入口复验。
自动测试没有启动游戏，未改变播放器音频、原文资源、翻译内容、设置或存档。
