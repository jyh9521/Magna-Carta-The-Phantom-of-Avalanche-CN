# 几何显示设备路径对照

## 已验证与未确认

2026-10-12 会话 `session-20261012-120122-401` 正常退出，退出码为 0。日志包含 TEXTURE_LIFETIME_READY 和四次 TEXTURE_LIFETIME_UNBOUND_BEFORE_DELETE。实测反馈未报错，但模型消失与场景缺失仍然存在。单次读档结果不作为长期稳定性证明，纹理绑定生命周期与几何显示问题分别验收。

对应 DDrawCompat 日志记录实际设备 IID_IDirect3DTnLHalDevice、D16、sysmem 顶点缓冲，且没有目录、全局、用户或 overlay 配置覆盖。驱动中的 HAL GUID 位于 RVA 0x1c450，RVA 0x2b5d 将其传入 IDirect3D7 EnumZBufferFormats；这只证明驱动存在 HAL 深度格式枚举，不证明实际创建设备为 HAL。

模型异常是否来自设备变换路径仍为未验证假设。截图与正常退出不能区分变换、裁剪、深度、顶点数据或引擎可见性逻辑，不直接禁用深度或背面剔除。

## 单变量候选

固定 DDrawCompat v0.7.1、纹理删除前解绑候选、原始资源、存档、窗口配置和渲染分辨率。HAL 组仅增加 `SupportedDevices = hal`；standard 组恢复原配置。该项限制可枚举和可使用的设备类型，依据为 [上游配置说明](https://github.com/narzoul/DDrawCompat/wiki/Configuration#supporteddevices)。并非关闭全部硬件加速，也不修改游戏可执行文件。

包及驱动版本锁定沿用 [图形候选](GRAPHICS_CANDIDATE.md) 与 [纹理候选](TEXTURE_LIFETIME_CANDIDATE.md)。不引入第二个兼容层，不更改正常无层副本。历史 HAL 离屏退出异常保持失败记录；本次未用历史离屏结果宣称实际游戏通过。

## 可复现操作

先关闭游戏、设置程序及启动器。已部署受控 DDrawCompat 的 build/runtime/diagnostic-game 才接受切换：

```powershell
python tools/graphics_compat.py select-profile --workspace build/runtime/diagnostic-game --profile hal
python tools/graphics_compat.py select-profile --workspace build/runtime/diagnostic-game --profile standard
```

工具先检查隔离路径、原件哈希、DLL、配置及 manifest，一致才更新配置和 manifest。未知版本、修改过的受控文件或其他兼容层拒绝覆盖。临时写入使用原子替换；第二次写入失败时恢复两项原始内容。进程突然终止可能留下不匹配文件，下一次校验将停止操作而非静默重写。

显式运行 `tools/launch_graphics_trial.ps1 -Python <Python路径> -DevicePath hal` 才启动诊断副本，保留异常采集与纹理解绑。`-DevicePath standard` 恢复原诊断配置再启动。本地生成 LaunchHalTextureFix.cmd 和 LaunchTextureFix.cmd 分别对应两组；生成或检查入口不会启动游戏。

## 游戏验收

1. HAL 组读取相同存档，使用相同镜头、移动路径观察至少 60 秒，记录角色消失、地形缺失、音画及退出情况。
2. 日志必须出现实际 IID_IDirect3DHALDevice，而不是仅出现配置项 hal；同时必须出现 TEXTURE_LIFETIME_READY。设备选择失败或仍用 T&L 时，该组无效。
3. 必要时 standard 组按相同步骤复测，核对配置哈希与实际设备。日志先归档再进行下一次运行，避免同名日志覆盖。
4. 正常退出码与显示反馈分别记录。HAL 若没有改善，保持 DISPLAY-01 未修复，恢复 standard，继续调查绘制状态和几何数据，不继续添加设备配置变量。

## 自动验证范围

已验证 standard→hal→standard 字节往返、重复选择、受控配置被改动拒绝、其他层拒绝、外来 manifest 拒绝及写入失败恢复。58 项单元测试通过；PowerShell 入口仅作语法解析，没有执行启动。隔离回滚副本重新通过原 53 项测试。该证据仅覆盖配置工具，不代替游戏显示验收。
