# 全屏黑屏与碰撞阻断调查（2026-10-24）

优先级为剧情全屏黑屏及多地图卡死，声音候选暂缓。现场确认黑屏时只有声音，字幕和头像也不显示。
当前没有宣称这两项症状已修复。本轮仅离线执行原生有限函数和安装只读记录，没有启动游戏。

## 黑屏：已验证与缺失输入

所交版本4存档CRC通过；场景715前进后进入254。254/event1的502命令参数为8、30、0、0、0，
原生处理器RVA79a21启动scene+1098淡入帘，目标0、时长参数31，tick为5786c。
`replay_native_fade.py`执行原生淡入tick及原生移动/完成计算：正常最终percentage=0、complete=1；
显式暂停负例保持100/0。输入/owner通知和移动器的通用父回调为边界，不执行GPU或资源构造。
该负例证明暂停可维持遮罩状态，不证明现场黑屏就是暂停造成，也不把percentage=0当作最终画面通过。

已有profile.log没有四个全屏层和场景门状态，初版采样记录不足以区分遮罩未退与绘制未提交。
新增MC_BLOCKER_TRACE=1门控，在既有玩家碰撞调用后读取状态；原函数仍只调用一次，不额外查询碰撞。

- BLOCKER_STATE：Field/Map、mode、scene+28/30/2c门值、event lock、loading gate、角色位置/状态。
- BLOCKER_FADE：scene+1098/109c/10a4/10a8，分别为curtain_in/out及scene_in/out。
  记录对象可读性、d0/d4/d8原生控制字段、190完成标记、19c阶段、194指向的box的1b8效果和1bc百分比、
  198移动器的f0活动标记。字段名描述原生位置，不单靠单个字段推断最终可见性。
- 场景或mode变化立即记录，其余最多每500ms一组；保留返回指针、碰撞副作用和LastError。
- 自有Win32观察夹具838项通过；默认旧探针835项仍通过。两者只验证观察透明性，不是症状修复红绿。

## 碰撞：真实几何离线链

`resource_gid.py`按照fb56/11586/14143/13710读取：1024字节保留头，计数sublevel，各项12字节元数据
及32字节顶点，随后native节点数及前序BSP。叶为flag、solid两个DWORD；内部节点含22字节polygon、
四个float平面、计数22字节共面项及前后子树。计数、深度、有限数、节点数和EOF均验证。
polygon字段保持不透明，不导出原始顶点。内存节点96字节，父指针+10也须重建，供线段命中的平面读取。

WRD末尾16字节中的最后DWORD由原生2a723读入资源+44，8a3f0再用它选择GID；不能按WRD同名猜GID。
已核对MAP106→GID59、MAP109→GID62、MAP111→GID64。
`replay_native_collision.py`执行原生8a6a4、8a6eb、6ed4e及其BSP/向量方法，不运行游戏或渲染。
记录中的38951条中心位置使用真实资源重新查询，共6945个不同点，6414条原生中心判入实体，
与现场求解器清零速度的关系矛盾数为0。中心查询没有重建实际角色八个offset，不能称完整玩家回放。

自有半空间夹具中，初始已在实体内时，原生6ed4e对四个水平尝试方向均清零，包括向外方向。
这验证原生起始穿入分支可形成锁住状态，不证明水之迷宫的穿入入口或所在GID已经定位。
现场许多Z方向清零是地面响应，不能统统计作卡墙。963个可配对水平步长均接近0.03，
不支持凭逻辑定时器33ms就推断运动积分步长被改成0.033的假设。

## 共享测试版安装与人工步骤

外部平铺诊断包和本机共享data/布局分开构建，禁止混用。共享构建器为build_shared_blocker_update.py，
先核对完整files清单及受支持MCAlpha摘要，再生成14项事务：12个自有模块、runtime.json及新增
Play-contact-audio.cmd。普通Play.cmd和增强设置不变；不启用声音后端候选。
Install-Blocker-Trace.cmd及Shared-Blocker-Trace-20261024目录为安装载荷，重复安装转为检查。
独立备份为.shared-blocker-trace-20261024，与平铺版和旧回滚互不覆盖。载荷没有游戏资源或玩家存档。

实际共享目录安装、重复安装、CheckInstalled均通过；独立自有文件副本精确撤回14项。
现有三份存档及设置在安装前后摘要相同。为本次人工测试另复制所交存档至空闲MC03，不覆盖MC00/01/02，
该私人存档只保留本地，不加入ZIP或源码。游戏随后正常自动存档产生的变化应与安装变化区分。

测试者手动运行Play-contact-audio.cmd，读新增MC03，前进触发黑屏后停留约3秒并退出，预计约一分钟。
新记录为cache/profile.log，须含BLOCKER_TRACE_READY。水之迷宫若另测，吸入后尝试反向移动，再退出保留
另一份日志，避免覆盖黑屏记录。分析以新遮罩/场景状态与实际画面绑定，不再索取旧日志。

```powershell
python -m unittest discover -s tests -p test_blocker_replay.py -v
python tools/replay_native_fade.py --engine ENGINE_DLL --field FIELD254
python tools/replay_native_fade.py --engine ENGINE_DLL --field FIELD254 --paused-negative
python tools/replay_native_collision.py --engine ENGINE_DLL --gid GID_RESOURCE --point X Y Z
python tools/build_shared_blocker_update.py --runtime runtime --module build/native/Release/workspace_profile.dll --work build/NEW-shared-blocker --output dist/NEW-shared-blocker.zip
powershell -NoProfile -ExecutionPolicy Bypass -File runtime/Shared-Blocker-Trace-20261024/Update.ps1 -Action Rollback -Runtime runtime
```

完整回归913项，3项按条件跳过，其余通过；之后更新的BSP父指针和计数检查由9项专项再次通过。
原生回放、观察ABI、安装/撤回证据与实际游戏画面验收分别记录，不互相替代。
