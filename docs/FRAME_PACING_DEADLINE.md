# 60Hz限帧截止时间误差修正（2026-10-14）

## Verified：实际呈现钩子的受控时钟回放

advanced_display.cpp的presentHook在原Present返回后等待deadline，但旧代码随后将
下一deadline写为实际醒来的now + frequency/60。每次等待的晚醒时间都会再次加到
下一个目标上；QPC频率不能被60整除时还有每帧向下取整的长期偏差。
这是自有模块的算法缺陷，不需要改商业逻辑或假定玩家电脑确实每次晚醒1ms。

夹具通过实际安装的x86 Present虚表钩子进入生产限帧算法，Present返回值仍为7。
仅ADVANCED_DISPLAY_TEST提供可控QPC和等待晚醒；生产模块不包含这些开关。
时钟频率60,000,000、晚醒60,000 ticks（1ms），3601次呈现跨3600个间隔：
旧目标算法输出：
`PACING_DRIFT observed_ticks=3816000000 expected_ticks=3600060000 frequency=60000000`。
即实际虚拟耗时63.600秒，固定60Hz目标加最后一次晚醒为60.001秒；回归失败：
`FAIL present hook accumulates waiter overshoot instead of retaining exact60Hz epoch`。
该回放展示可能的时间误差积累，不是玩家实机帧间隔捕获。

## 修正

deadline沿同一个60Hz纪元递增，不再每帧以醒来的时间重新定目标。
frequency除60的余数累积到deadlineFraction，每达到60补一个QPC tick；
60秒完整轨迹因此无周期取整漂移。已错过的槽位直接跳过，不通过连发帧追赶。
沿用原250ms长暂停重置、设备对象切换重置；不改变原33ms逻辑callback，
不修改动作相位、碰撞、事件、音频或存档。该实现控制呈现节奏，不是60Hz游戏逻辑。

日志每个窗口统计120个真实间隔，不把起点帧额外当作一个间隔；
受控第一窗口计入首个1ms晚醒显示59.970Hz，随后窗口显示60.000Hz。
该日志是呈现钩子返回节奏，不是GPU显示完成或骨骼姿态数。

## 验证

两个QPC频率（60,000,000和10,000,003），各3601帧、每次晚醒1ms：
精确目标纪元、分数tick、40ms短阻塞跳槽、1秒暂停重新定基准、设备切换、
原Present返回值和日志120间隔统计均通过。
原真实QPC/等待路径也运行61次自有Present，约1秒；这不是商业游戏执行。
夹具7335项通过，原33ms一分钟逻辑回放在30与60Hz呈现下均为1818次更新。
独立源码回滚恢复103项原基准；上轮队列世界修正893项仍通过。
本次未改queued_world、骨骼/相机插值或Xbox映射；没有新建游戏数据副本。

## 实机尚未证实

当前最新玩家反馈仍是待机稳定、走动抽动；上一轮队列世界修正尚待画面反馈。
本次修正限帧器的可复现漂移，不证明现场抽动全部解决，也不保证GPU负载下稳定60FPS。
实际较低帧率还可能来自原Present阻塞、场景负载等；不从合成1ms晚醒猜测现场原因。

## 验收入口

仍用runtime/Play-motion.cmd，沿上轮步骤待机→走动→转身→停步，观察镜头跟随
和停步后的抽动。正常退出后profile.log中的RENDER_PACING显示窗口返回频率。
Play-motion-gamepad.cmd保持相同修正和独立手柄候选；不自行启动游戏。
Alt+Tab继续搁置，汉化/标题美术/默认增强设置不动，完整60FPS仍需玩家画面验收。

## 重现命令

```powershell
cmake --build build/native --config Release --target workspace_profile advanced_display_fixture motion60_fixture
build/native/Release/advanced_display_fixture.exe
build/native/Release/motion60_fixture.exe
$env:PYTHONPATH=(Resolve-Path runtime/dependencies).Path
python -m unittest discover -s tests
```

构建失败时不运行旧fixture。源回滚仅对隔离的自有fixture执行，活动模块保持修正。
