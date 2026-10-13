# 镜头相对XInput与界面导航候选

2026-10-14。替代首轮坦克式方向键适配的独立候选，实际Xbox手柄验收待执行。4K、宽屏、标题画面和汉化数据不改；完整动作60FPS使用既有候选，不把组合预检称为游戏验收。

## 已验证的静态边界

MCAlpha版本锁：`5c701de93af6267b959c49e6927bee525bc0f3c68c8c6f51413515d13809d427`。

- 探索逻辑`6b2d8`在原输入轮询后处理键盘和鼠标，再更新场景。角色指针`scene+1564`，主窗口`+10c8`。输入事件处理`6e6d8`使用事件1/5转向、9前进、12停止；这是坦克操作来源。证据：`ev_4a09b11f608153f6fa5e3ff8b19888348722143949586410ed789cd6e0bc94f1`、`ev_078c19477170d8be1e072f40c4ad26c458307637d2fc1dacf81e0e414a0cfacf`。
- 玩家类构造`64440`绑定虚表`c11e4`；探索更新槽`c12c0`指向`6b2d8`，玩家前进槽`c1258`指向`652b4`，方向槽`c12a0`指向`65504`。只处理当前探索场景的当前玩家，且调用返回点匹配`6e781`。未知字节、槽或角色身份拒绝。
- `65504`接收12字节向量，方向计算读取X/Y，Z不是水平轴；返回`ret 0xc`。`652b4`生成原移动向量到角色`+16c..174`，再进入原动作流程。使用原前进与方向接口，不直接改坐标，不另造碰撞或传送逻辑。证据：`ev_1c6f61386cef8b72d3faab339fae968f86e4631f27746b6b6ee15b9bb5b442e6`、`ev_d0b9065d1534a8ab34fec155778bf4b2a8c2fcd4ad3b43f605fb29025d660516`。
- GUI命中函数`4e686`读取`GUI+f8`矩形链表，将`GUI+24/28`加到矩形坐标。节点首DWORD为矩形指针、第二DWORD为next。证据：`ev_4258c8e1a3e5b351a18c10dc5a737aa3629e01804a313eef47c6500b8a0875c4`、`ev_45918c6e2eee83289420b6b190ad56e570c3539492a7f481bc54f09f38e3d9a9`、`ev_7bb49d8228959a5ffa6d32eeab200fb0a6939ed61e4a18103c6d6978daad7cbf`。
- GUI管理器`f220c`的`+34`为独占窗口栈，计数`+38`，头节点`+3c`。导航优先当前独占窗口，避免选到背景控件；独占窗口存在时禁用探索摇杆。证据：`ev_16a16f228705b7a06061586c3b8d31f6757618039749f14d835e5dc8b3c8916d`、`ev_24aa43181d3677e5252a317abcaeb58fdd5cda7af407b0d5237aa1bd203151ae`。
- 21类GUI的键盘分发槽原指向`55134`。导航只识别这些绑定类、原可见/启用字段及命中矩形；保留有原生方向键行为的控件，不调用虚构按钮回调。原鼠标点击分发继续执行。

矩形作为可导航控件的筛选属于候选策略，须逐菜单验证。静态结构不证明每个界面已经适配。

## 控制方案

| 控件 | 探索 | 菜单/对话框 |
|---|---|---|
| 左摇杆/十字键 | 镜头相对移动；摇杆方向连续、速度按幅度缩放 | 按实际控件矩形导航，支持重复与循环 |
| 右摇杆 | 游戏内虚拟指针 | 虚拟指针；不移动系统鼠标 |
| A | 原Space交互 | 原左键点击；标题开场阶段使用Space |
| B / Start | 原右键取消/菜单路径 | 原右键取消/菜单路径 |
| X | 原左键操作虚拟指针目标 | 原左键点击 |
| Y | 原Tab路径 | 原Tab路径 |
| LB / RB | 暂不新增探索动作 | 界面左/右导航 |
| LT / RT | 暂不新增探索动作 | 原滚轮字段，上/下滚动 |

Y及滚轮保留原界面语义，不宣称所有页面都有对应动作。战斗、特殊交互、滚动列表和禁用按钮均在实体验收清单中；未确认的专用战斗快捷键不伪装成已映射。

输入获取仍为原GetKeyboardState边界内的状态合并，不使用SendInput或全局键鼠事件。方向键/真实鼠标优先，连接、断开、失焦和换设备后要求回中；左右摇杆与扳机均参与中性检查。相机读取原逻辑视图，而非平滑渲染视图。实际前进保留原动作与碰撞，只缩放该次原移动向量。小幅摇杆下的步频与脚步观感仍需验收。

## 构建及独立入口

```powershell
cmake --build build/advanced-display-native --config Release --target workspace_profile workspace_launcher world_gamepad_fixture gamepad_ui_fixture camera_relative_input_fixture gamepad_cursor_fixture ui_focus_fixture modern_gamepad_fixture modern_input_probe
python tools/prepare_gamepad_trial.py --source build/disc-gate-game --native build/advanced-display-native/Release --locale locales/zh-CN --output build/xinput-modern-game
```

输出必须全新；原生构建依赖沿用BUILDING.md。`--native-gamepad`显式启用新路径并允许与高级显示组合；旧`--modern-input`仍与高级显示互斥。未选择新开关时清空`MC_GAMEPAD_NATIVE`。预检支持`-PrepareOnly`与`-VerifyOnly`，均不启动游戏。

入口目录`build/xinput-modern-game`：

- `Play-Xbox.cmd`：宽屏4K、完整动作插值候选、新XInput。
- `Play-Xbox-30fps.cmd`：同画质30FPS，隔离帧率影响。
- `Play-keyboard-mouse.cmd`：同显示/动作候选但关闭手柄模块。
- `Rollback-motion.cmd`：恢复候选基准配置；存档和原正常副本不回写。

## 手动验收

1. 先连接Xbox/XInput手柄，启动后双摇杆回中、松开所有按钮一次。
2. 标题十字键上下应切换按钮，A确认；右摇杆移动游戏指针，A/X点击。禁用的继续按钮不得被激活。
3. 同一存档探索：左摇杆四向及斜向应直接朝画面对应方向移动，不需要先坦克转身；轻推与满推比较速度，墙边碰撞保持正常。
4. Space对应交互、B/Start菜单、菜单取消、状态、物品、保存、读档、滚动列表逐项测试；检查右摇杆指针与按钮命中位置一致。
5. 战斗逐项确认角色选择、技能/目标选择、发动、取消和特殊操作；当前不把探索夹具通过当成战斗验收。
6. 键鼠交替、断开重连、长按连接再回中；不自行恢复旧按住动作。Alt+Tab鼠标故障仍搁置。

日志应含`MODERN_INPUT_READY route=native_world_and_ui`、`WORLD_GAMEPAD_READY`、`GAMEPAD_UI_READY`；探索及导航首次命中分别记录`WORLD_GAMEPAD_APPLIED`、`GAMEPAD_UI_FOCUS_APPLIED`。缺少命中日志不计为该路径工作。当前只读XInput快照未发现连接设备，实体手柄状态仍待玩家确认。
