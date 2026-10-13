# 现代输入：首轮 XInput 候选

2026-10-13：汉化内容冻结，继续兼容性、现代输入和引擎缺陷调查。本阶段不改译文、字库、图片、视频或保存文件。

## 已验证的原输入边界

REA/Ghidra 12.1.4读取原MCAlpha.dll，SHA-256 `79e4c3d6af4afb2b75367a2b26fd8450ad25fa9f738612ea96809e312d33cb6f`，未执行商业模块。

- `0x52002f95`：读取鼠标位置，调用GetKeyboardState到256字节表`0x520f1b94`，按高位生成每键连续按下计数与释放状态。调用IAT为`0x520bd3dc`，调用后地址`0x52002fd5`。
- `0x52002d10`：独立GetAsyncKeyState高位查询；首轮手柄候选不改这条路径，不宣称全部游戏动作覆盖。
- `0x52002dad`：GetCursorPos后根据fullscreen字段决定是否ScreenToClient；鼠标坐标来自独立路径。
- `0x520019ea`：返回游戏窗口字段`0x520f1b44`。
- `0x5200bea8`：WM_KILLFOCUS的SW_MINIMIZE分支、WM_MOUSEMOVE的SetCursor(NULL)、WM_MOUSEWHEEL计数及下游消息回调。

这些是静态事实。仍需记录菜单、行走、战斗的实际键位消费者；方向键、Space与Esc只是首轮输入候选，不冒充已验收的完整动作映射。

## 首轮实现

`modern_input`为与语言、Windows后端分离的状态机。输出held/pressed/released动作；数字方向、左摇杆方向、确认、取消和菜单在模型层可重映射。左右/上下冲突归零，摇杆采用进入16000、退出10000的滞回阈值。启用、重新聚焦、连接或更换设备后，先等待一次中性采样；持续按住时不跨窗口/设备继续动作。

`modern_gamepad`为可选进程内GetKeyboardState导入适配：十字键/左摇杆映射方向键，南侧面键映射Space，东侧面键映射Esc。菜单键尚未确认，桥接不输出菜单键。保持实际键盘状态与toggle位；Windows读取失败时不把失败转换成手柄成功。只处理版本锁定的调用地址，只在游戏原HWND前台且非最小化时合并。检查映像、重定位操作数和原IAT，未知槽拒绝安装。无SendInput、全局按键、抢焦点或后台控制。

XInput从系统目录延迟加载到输入轮询阶段，不在DllMain加载；只选择一个当前设备，保持该设备直至断开，随后切换也要先回中。新增launcher开关`--modern-input`，默认关闭；未传开关时显式清空环境启用状态。当前是XInput键盘状态适配，不是原生模拟摇杆移动，也不是PS/Nintendo原生支持。SDL3后端、可编辑配置/标签、完整映射和实体设备验收另行实现。

XInput API依据[Microsoft文档](https://learn.microsoft.com/en-us/windows/win32/xinput/getting-started-with-xinput)；后续跨品牌后端依据[SDL3 Gamepad文档](https://wiki.libsdl.org/SDL3/CategoryGamepad)，不借系统XInput探测结果宣布其他品牌支持。

## 构建与验证

使用既有Win32 CMake工程及当前锁定字体/消息头：新目标`modern_input_probe`、`modern_gamepad_fixture`。构建profile和launcher时沿用当前`NATIVE_FONT_DATA_HEADER`、`SYSTEM_MESSAGE_RULES_HEADER`、`LOCALE_ENGINE_SHA256`，不重建汉化资源。

```powershell
cmake --build NATIVE_BUILD --config Release --target modern_input_probe modern_gamepad_fixture workspace_profile workspace_launcher
NATIVE_BUILD/Release/modern_input_probe.exe --fixture
NATIVE_BUILD/Release/modern_gamepad_fixture.exe
NATIVE_BUILD/Release/modern_input_probe.exe --snapshot
python -m unittest discover -s tests
```

纯状态机枚举全部65,536有符号轴值和65,536按钮掩码；自建可执行调用桩验证真实IAT安装/调用、原键保留、失焦/回中、断线、读取失败、未知映像拒绝、幂等、页保护及槽恢复。不加载商业游戏DLL。`--snapshot`只读取系统XInput四个槽，不发送输入或启动游戏。本机首轮四槽均1167、连接数0；没有实体手柄验收。

现用游戏副本的profile/launcher不替换；新原生工具保留在独立构建目录，手动试验时使用匹配版本的独立启动工具及`--modern-input`。关闭开关或重新使用原工具恢复原输入，进程退出清除内存IAT改动。源代码和构建产物的独立回滚证据位于忽略的build目录。

## 下一步验收

先确认原游戏方向/确认/取消/菜单的消费位置，再测试菜单、剧情、探索、战斗和存读档。对比开关OFF/ON，检查实体手柄、键鼠共存、失焦至少20次、断开重连和热切换。窗口切回不代表鼠标恢复；INPUT-01继续单独追踪。当前不称为完整P2或鼠标故障修复。
