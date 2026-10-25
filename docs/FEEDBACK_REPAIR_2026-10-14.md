# 实机反馈修正：动作历史与菜单导航

## 玩家验收状态

- 完整动作60FPS：玩家报告模型抽搐，未通过；60Hz呈现不等于60Hz逻辑。
- Xbox：探索移动通过，菜单和A/X语义未通过。
- 增强配置：玩家确认通过。
- 纹理生命周期：引擎资源管理候选，不是清晰度或纹理增强；尚无玩家确认的崩溃修复。
- 环绕视角：绘制视角通过，视角改变后的移动方向未通过。
- 区域地图：玩家认为近乎空白、无实用价值，未通过。
- 标题：背景和宽屏通过；按钮默认亮度过高、悬停区别弱仍待修正。

Alt+Tab继续搁置，汉化冻结。上述反馈取代首轮的“待验收”，不把候选发布当作功能完成。

## 本轮已验证

### 动作过渡历史

Verified（静态）：支持的MCAlpha SHA256为
`5c701de93af6267b959c49e6927bee525bc0f3c68c8c6f51413515d13809d427`。
REA/Ghidra `3b0c0`在过渡分支使用对象`+f0`的局部骨骼历史，且每次渲染在调用
`MakeAbsoluteMatrix`之前回写该缓冲。Evidence：
`ev_80a717cc5415cd7ba940a922e9878f4a96e0b02d1018d83405679a767e51c35e`。
完整返回保存在忽略的`build/feedback-repair-evidence/rea-render.json`。

Verified（受控复现）：原夹具未模拟这个原生副作用。新夹具在同一逻辑tick连续绘制，
重现历史在额外呈现中推进；旧实现报
`FAIL same logic tick cannot advance original transition history`。
新实现保留tick开始时的输入历史，同tick重绘重新使用该输入，而下一个原逻辑tick仍正常推进。
按对象、action、历史缓冲、骨骼数和计时器generation/tick隔离；未知资源、超512骨骼、无有效相位均旁路。
原33ms调度、碰撞、动作事件、音频、存档不加速。历史缓存最多128对象。

High-confidence deduction：该逐绘制历史反馈可能解释部分动作抽搐。
尚未用玩家录屏或现场姿态日志证明该修正解释所有抽搐，不宣称完整60FPS已修好。
每秒约30次逻辑更新与每秒60次呈现是两个指标；本候选以呈现插值补中间状态，不把逻辑改为60Hz。

### GUI原生结构

纠正：`GUI+f8`是矩形链表容器，不是首节点。`02014`读取容器`+8`，所以首节点在`GUI+100`；子控件首指针是`+18`，兄弟next是`+10`。
依据原命中函数`4e686`（Evidence `ev_4258c8e1a3e5b351a18c10dc5a737aa3629e01804a313eef47c6500b8a0875c4`）
和分发函数`55134`，原分析留在`build/xinput-camera-move-evidence`。
上一轮将容器地址误判为节点指针，改为`+f8`的代码与夹具一起犯错，16项通过不证明真实菜单有效。
这一轮夹具加入真实容器非零计数，并把节点放到容器`+8`；旧实现再次报`FAIL first downward focus and original dispatcher return`，读取`+100`的实现通过16项检查。
`01ced`返回节点首DWORD的数据并以节点`+4`推进，不能跳过这两个访问器仅靠容器参数猜布局。

当前修正只覆盖矩形容器读取。实机仍由玩家验收；开头动画跳过、A/X语义和标题样式还未通过。
新增每秒一次`INPUT_FRAME`日志，记录连接/焦点/回中/场景模式和手柄动作，辅助区分输入未到达与控件导航失败，不采集系统键盘输入。
A在探索打开菜单、X触发鼠标定向移动的问题仍未修正，
下一步须重新绑定探索/菜单/对话/战斗语义，不以方向导航通过替代完整手柄验收。

## 构建和小型共享入口

```powershell
cmake --build build/advanced-display-native --config Release --target workspace_profile motion60_fixture gamepad_ui_fixture
python tools/prepare_feedback_trial.py --workspace build/configurable-modern-game --native build/advanced-display-native/Release --output build/feedback-repair-runtime
```

输出需为全新目录。复用已通过的配置副本数据，只复制运行时模块，不再复制整套游戏。
三个入口隔离变量，纹理修复、环绕视角和地图不启用：

- `build/feedback-repair-runtime/Play-motion-repair.cmd`：完整动作修正，手柄关闭。
- `build/feedback-repair-runtime/Play-menu-repair.cmd`：菜单导航修正，动作插值关闭。
- `build/feedback-repair-runtime/Play-baseline.cmd`：关闭本轮动作和手柄候选的对照。

关闭游戏、改用baseline即关闭这两项；原验收入口及原模块不替换。
运行`Start.ps1 -VerifyOnly -WithoutTextureGuard -SettingsFile <对应json>`只预检，不启动游戏。

## 玩家复验

1. 对照baseline与motion-repair：同存档待机、起步/停步、走跑转换和连续转身，各观察至少10秒；
   换动作、镜头切换、换场景也要检查。抽搐应消失，路线耗时、攻击和事件不得加速。
2. menu-repair：主菜单和游戏内菜单用十字键/左摇杆逐项移动；检查循环、禁用项、模态弹窗。
   先只验方向导航，A/X及取消绑定仍在修正清单，不要求把旧错误操作验为正常。
3. 失败时记录入口、场景及触发动作；本轮不是对全部现代化功能的最终验收。

## 项目体积

历史完整测试副本是占用主因；当前修正采用共享数据模块。上次清理删除命令被执行环境拒绝，
没有执行删除；`build/project-cleanup-evidence/Cleanup.cmd`为已准备的人工入口，先校验备份与原文件再删除。
当前入口、存档和独有差异必须保留。不得把磁盘空闲的外部变化记作本轮清理成果。
