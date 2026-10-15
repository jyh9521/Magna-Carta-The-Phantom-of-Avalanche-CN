# 剖切资产接入原生地图绘制回放（2026-10-15）

## Verified

上一阶段只验证地形PNG与MCM1一致。本轮使用实际 `map_overlay.cpp::renderCanvas` 的GDI+绘制路径，将未剖切/剖切资产分别绘制为大图和小图，确认原有玩家箭头、NPC圆点、箱体方块和轨迹可以继续叠加。

`map_overlay_fixture` 采用自有场景/对象/坐标样本与隐藏测试窗口，不加载或启动商业游戏。它读取本地生成的地形资产，输出536×584离屏PNG。窗口消息仍检查鼠标穿透和不激活，但这不证明真实游戏全屏合成通过。

新增三项黑盒回归使用自有两层几何、同一MCM1和实际原生测试EXE：地形像素随裁切变化，但同一视图中玩家/NPC/箱体的纯色像素掩码完全一致。大图确认世界坐标投影；小图确认玩家锚点在绘图区中心。输入资产摘要也保持不变。

实际0009候选另做四张原生输出对照，得到相同的标记掩码结论。测试玩家最终XYZ为(-80,260,33)，NPC为(-100,250,33)，箱体为(-180,320,33)；这是自有样本，不是当前存档或实际楼层。Z33与剖切高度30不同，测试只证明XY叠加，不证明楼层筛选；当前地图标记仍不按该剖切高度过滤。

## 避免错误的模式证据

旧夹具对未知第四参数静默按大图处理，也不输出实际渲染模式。文件名带mini不代表真的使用了小图。本轮明确要求只有无参数自检、`ASSETS OUTPUT.png` 或 `ASSETS OUTPUT.png --mini` 三种形式；其他参数在创建窗口/读资产前退出2。

成功绘制会输出 `MAP_OVERLAY_RENDER PASS mode=large|mini size=536x584 source=owned_fixture pixels=rendered game_started=false`。这描述自有离屏输出像素，不描述游戏画面。

```powershell
cmake --build build/native --config Release --target map_overlay_fixture
build/native/Release/map_overlay_fixture.exe runtime/maintenance/map-height-cutaway/cutaway-final-atlas build/cutaway-large.png
build/native/Release/map_overlay_fixture.exe runtime/maintenance/map-height-cutaway/cutaway-final-atlas build/cutaway-mini.png --mini
python -m unittest discover -s tests -p test_map_cutaway_native.py
```

独立源码回滚后重新编译，原生小图输出像素保持相同，只有新模式证据/参数守卫恢复成旧行为。没有修改生产地图绘制代码、运行模块、入口或当前资产。下一步实际游戏对齐、楼层逻辑和输入验收仍分开处理，未据此标记完整地图或手柄完成。
