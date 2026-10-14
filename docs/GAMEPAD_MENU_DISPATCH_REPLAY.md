# A键原生菜单事件整链受控回放（2026-10-14）

## Verified

MCAlpha.dll SHA256 5c701de93af6267b959c49e6927bee525bc0f3c68c8c6f51413515d13809d427。
02f95先读取真实鼠标，随后GetKeyboardState并将256个键转为计数。
557ee子优先：键1首按=1调用+188，持续>0调用+18c，空闲=0调用+190，松开=-1调用+194。
03099检查0，030cf检查-1；空闲与松开不可混用。
5641e/56437/56450/56469分别转发事件3b/39/3a/3c。
REA证据：ev_662e4fce197820f3401e314d5ba73c2606e51ddc0143975d9c80bd58f1339c72、
ev_b0bc73849e1e036505b80928e80bcd073ad5b195dbc1ddbae8a91bf318287a08、
ev_87b63eac5074096683f4f93f5b98809bebfc6cae43d9b8582a9091df0d7b9c6a、
ev_25c927a34b67fd888afa6b82835f9645ccdef7b3d10613aebb9d978760e6ae04、
ev_84e7976a0d201f0b3e59627384f2d85a59b3c699949d43cf0e0c0294e29fd5bd、
ev_c4af5009c08f239874f99d17dfeed10822863658993b6900ffa716d905ce7759。

world_gamepad_fixture增加真实鼠标恢复→生产XInput IAT桥→生产方向焦点钩子→
原生形状键计数→子优先鼠标命中→自有vtable回调的整链回放。
覆盖第一项A首按、持续、松开、后续空闲；第二项确认、禁用按钮、真实鼠标接管第三项。
记录器获得首按3次、松开3次、持续4次，目标符合选中矩形；完整夹具由53增至61项。
以menu-physical-poll-repair保存的历史旧modern_gamepad.cpp和头文件独立重编译，
菜单专用回放失败 `FAIL A must reach selected native button first-press callback after physical poll`。
当前生产源码同回放通过，不是人为改坏当前代码制造失败。
独立回滚测试源恢复53项基准通过。Python整链回归已加入，完整452项通过。

## 未证明事项

回调为自有记录器，不是实际标题listener；没有加载或执行商业游戏DLL。
受控整链证明当前轮询修正可以把A送到选中回调，不证明实体Xbox、实际标题listener、
全部菜单、独占/捕获状态与宽屏实机坐标映射通过。模态焦点另由UI夹具覆盖。
本轮未修改生产模块；完整60FPS、实体菜单验收继续保持未完成，原日志未更新。
游戏启动0次，游戏数据复制0份，Alt+Tab搁置，汉化冻结。

## 复现与验收

构建world_gamepad_fixture，运行`build/native/Release/world_gamepad_fixture.exe --menu-dispatch-only`；
`python -m unittest discover -s tests -p test_gamepad_menu_dispatch.py`检查回调标量。
未构建原生fixture时Python显式skip，不把skip当作通过。
不带参数保留完整运动、镜头、键盘与回滚检查。
玩家仍用runtime/Play-gamepad.cmd：方向选中后松开，A首按进入，B返回；
Start打开游戏内菜单重复方向/A/B，再用真实鼠标接管。没有为测试新增游戏入口。

## 后续：标题listener请求级契约

现在回放已增加原生ID、listener+24转发与release-only请求选择，见GAMEPAD_TITLE_LISTENER_CONTRACT.md。
自有callback计数不等于实际标题转场；本请求级验证仍未执行商业transition executor。
