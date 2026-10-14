# 队列世界矩阵与延后相机：移动抽动候选修正（2026-10-14）

## 当前状态

玩家最新反馈仍是待机稳定、走动抽动、停步后几次抽动再稳定；本轮不启动商业游戏。
此修正具有源绑定事实和真实自有钩子回归，仍需玩家画面验收，完整60FPS不标完成。

## Verified：闭合调用链

支持MCAlpha.dll SHA256 5c701de93af6267b959c49e6927bee525bc0f3c68c8c6f51413515d13809d427；
Asura.dll SHA256 f81e7c458d43b77210311499b39b9be2c4895e3a3b356d2e848b6e84210d2557。
REA/Ghidra只读反编译，没有执行这些商业函数：

1. MCAlpha RVA3a200构造骨骼观察对象并写入vtable bd9f4，+4槽bd9f8指向3b0c0。
   3df5a把该对象存入角色动作对象+5c：
   `ev_2844610b41ef561d32b911a1660f002d7a118573fdc0d137d86a3f7c432de45c`、
   `ev_d2cec64384ce051ea1a2ff8625ff6f0fe7e241eb3b8024ff738f17baee6ef8e1`。
2. 3f00d取当前GetMatrix作为父参数，角色+44为整数动作帧，调用+5c对象vtable+4，
   确实到达骨骼渲染入口：
   `ev_d792a7dd30a58b301dcdfbd41b4bc179253acbf3f30b1dc30764b60868aee8fc`。
3. 47416先执行节点变换；读取节点矩阵后，在push/pop保护区临时加载相机、乘节点矩阵，
   计算屏幕坐标；该保护区已退出才调用3f00d。不能把临时投影使用相机误作队列父矩阵含相机：
   `ev_63db265cb920775fce43f8dcab480f49d48f9ef0405bfff8f70d9c0c1c9db43e`。
4. 骨骼3b0c0将非空parent * object+4c写到object+c，ASRRegRender复制矩阵到队列，
   不仅保存指针。该乘法本身正确；空间解释此前错误。
5. 区域631a0先调度更新和63322场景登记，再1d604、1d9d9应用相机，随后ASRRender消费队列：
   `ev_bf8406c4b0c93ac6fe7e0990932e57a9a652417a4f036646f7bc49b30cfc91d3`、
   `ev_5afe63cc759964c3f18ba8aed409265c0fa91c03d9d9dd90eb0aa33baeb95bcd`。
6. Asura ASRRender RVA516fd转发四个消费函数4eec1、4f8d9、50047、50b89。
   四路都在消费时push模型视图、multiply队列+0x364（字节+d90）矩阵，再绘制/pop。
   相机与登记的世界变换在消费时才组合：
   `ev_50e96a78e8135f048c43ada981fe09cacbf1c579f56213572e7e54d1e3558fa6`、
   `ev_432fcea834005559e841cadb0455ef74f19f1d6b9fc700d5d1e5571d0be2139a`、
   `ev_c6a0ad80508bc5caf35cd49e81618653cf1b6bbbea1ad3281de37e9f82b655c9`、
   `ev_43abee2c7f1511b1121b62b79f6e7b002d4293baa4a56bef047cab89f596ee80`、
   `ev_5cf6c51306dea307686eab8bf6ec11fa9e985e111647be4e5b5af43a1ca44e8d`。

## 原缺陷与修正

旧非空父矩阵分支把登记世界矩阵误作view * actorWorld，逆相机后才插值。
临时相机在同tick加载/移动时，会改变其本应稳定的世界输入，导致TransformTrack重置；
恢复时还重新乘原相机，将native object+c写成另一空间。
旧夹具在传父参数前就预乘相机，因此掩盖了真实队列顺序。

现在修正夹具：原Render复制parent * local，记录队列矩阵，消费才乘相机。
旧生产代码+新夹具两次独立构建失败：
`FAIL queued parent world matrix restores exact native world not inverse-camera result`。
人物native world=10，相机=-20时，旧钩子错误恢复为-10。

新非空parent分支直接插值登记世界矩阵，按字节恢复原object+c，不逆相机、
不重新乘相机，不要求cameraState.valid。相机仍在独立受守卫driver钩子中插值。
空父矩阵分支、骨骼历史/层级保护、33ms逻辑、事件/碰撞/音频、原输入代码均保留。
不同源分支仍有各自TransformTrack，避免混合采样轨迹。

## 受控验证

893项实际自有钩子检查通过。新回放覆盖32个引擎余留值：登记先于相机加载，
人物世界平移/转向与骨骼同相位；同tick相机连续转向不改变登记世界矩阵，
相机只在队列消费乘一次；停步世界保持稳定；旋转父矩阵及SEH路径精确恢复。
停止后中间旋转允许既有插值的2e-5浮点误差，不把四元数重建舍入当作实机抽动。
受控输出：
`QUEUED_WORLD_REPLAY PASS samples=32 camera_motion=true camera_rotation=true queue_before_camera=true world_restore=exact game_started=false`。
独立源码回滚恢复264项旧基准；旧夹具描述旧假设，仅作为回滚对照，不作为队列空间证明。

## High-confidence deduction与待验收

相机跟随时错误逆变换可解释最新移动/停步反馈，但静态链路和受控回放不是玩家画面。
其他骨骼、附件、顶点缓冲、战斗和场景状态仍按实际反馈继续核对，不能声称全数解决。
上轮world/camera原因观察字段保留，新首次日志应为source_space=queued_world，
而不是旧view_composed；计数仍不等同于肉眼抽动数。

## 共享部署与手动验收

只更新runtime/modules的自有模块及摘要锁。数据仍唯一runtime/data；不新建整套游戏。
入口runtime/Play-motion.cmd（先不混手柄），同存档待机10秒→直走10秒→转身10秒→
停步10秒，重复两次，正常退出；特别看相机跟随和停步后身体是否还跳动。
再用Play-motion-gamepad.cmd确认组合结果，保持原速度/事件；存读档和换区继续回归。
用户负责启动；VerifyOnly仅静态预检。Alt+Tab搁置，汉化、标题美术、增强默认设置不动。
