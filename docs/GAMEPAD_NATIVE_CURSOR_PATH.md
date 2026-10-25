# 原生光标坐标准备与显示状态（2026-10-15）

## Verified：纠正测试的证明范围

此前将 vtable `be374+18 → 38c24` 称为“光标绘制”过于宽泛。原始指令显示该槽调用 `+14 → 38afb` 更新位置缓存，并递归处理子对象；`38afb` 再调用矩阵准备函数 `4846b/38f6a`。只检查该槽被调用，不证明屏幕上已经出现指针像素。

`606eb` 通过 `02e02` 读取点击全局坐标 `f20b0/f20a8`，调用 `4d480` 写当前 `f2388` 对象的浮点 `+24/+28/+2c`，再调用 `+18`。深度常量为 `bdcccccc`。自有合成对象无父节点时，`38afb` 将这些位置复制到 `+f4/+f8/+fc`，随后进入外部矩阵接口。坐标读取中 `357a0` 仅返回参数，并未重新轮询系统鼠标。

独立的原生显示状态也存在：`60735` 经虚表 `+44 → 38941` 将当前对象 `+118` 设为 -1，并将 `d9c3c` 设为 0；`60777` 将二者设为 0/1。`607b9` 切换类型时隐藏旧对象，只有原显示状态为 1 才显示新对象。`38a62` 检查 `+118/+11c`。所以“手柄模块不再跳过位置准备”与“原游戏显示状态允许绘制”是两个不同条件。

这些发现不证明玩家当前问题是原生隐藏状态导致，也不强行显示过场中本应隐藏的指针。

## 可重放证据

```powershell
python -m pip install -r tools/requirements-native-replay.txt
python -O tools/replay_native_cursor.py --sample runtime/data/MCAlpha.dll --report build/native-cursor-report.json
```

摘要锁定沿用 `replay_native_title.py` 的支持版本。十一项原始指令回放包含五个位置（含 4K 边界与负坐标）、隐藏、隐藏时切换类型、显示、显示时切换类型，以及隐藏/可见时的原始绘制分支。坐标准备在 `4846b` 首指令前停止，未执行外部矩阵或图形接口；显示/切换函数按原指令执行至返回并检查栈平衡及合成 SEH 哨兵。只在模拟内存中执行，未加载游戏 DLL、未运行入口、未启动游戏。

命令输出：`NATIVE_CURSOR_REPLAY PASS cases=11 click_coordinates=matched native_visibility=preserved graphics_APIs_executed=false game_started=false`。

REA 证据：位置入口 ev_9e2bb0d19a7dd80d5594e3cb864cad6598e54c3fd6242695305128e9ff8512c4；坐标读取 ev_2f4ea3062041677901960280e5ab3dce6b3453bdb9825c01469d734129532cc1；位置准备 ev_bbaedbbe62c0eff6877650c9928b57846f600f5aaeb85bcaca8fd4fb441ae7ae；显示状态 ev_f70ddf14c50b3ba21dfd17e5d864e362cc9408ec514de3c7e7edf0b6ee5137c8、ev_3bcb2383af70dd71044c5455c82c1f40548d7f09c1c094720b3e16b6ca4e63e4；类型切换 ev_28c08f666626c4c1463a673f2924b746412fd3945ab8f469a257d91eb940c099。

## Unverified / 下一步

实际绘制槽修正见 [光标绘制边界](GAMEPAD_CURSOR_RENDER_BOUNDARY.md)。等待玩家对 `runtime/Play-gamepad.cmd` 的指针可见性与 A 确认一致性的反馈。真实画面、实体 Xbox、当前对象原生隐藏状态均不由离线回放代替。若仍不可见，再以该显示状态和实际绘制路径定位，不继续用“调用了位置准备槽”作为可见性已修复的证据。
