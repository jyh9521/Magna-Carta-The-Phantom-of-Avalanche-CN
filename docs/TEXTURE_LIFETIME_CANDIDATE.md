# 纹理删除前解绑候选

## 完整现场证据

诊断会话 PID 11760 已取得约 380 MiB 完整转储，包含 22 个线程。恢复的首次异常为 d3dim700.dll RVA `0x71b8`，读取地址 `0xC`；指令通过内部引用读取引用计数，现场对应指针为 0。
调用来自 AsrD3DDrv.dll RVA `0x7bb0` 的 SetTexture，返回位置 `0x7bb6`。当前设备阶段为 0，新纹理 ID 为 301；新 surface 的 vtable 位于系统 ddraw.dll。设备旧绑定指针指向的数据以 `0xff000000/0xffffffff` 开头，内部偏移 `0x2c/0x30` 均为 0。
以上字段已按完整对象内存验证。仅凭快照不能确定是释放后重用、写越界还是其他损坏，不将释放历史或图形问题根因标记为已确认。
`tools/analyze_texture_state.py` 锁定 d3dim700.dll 时间戳、SizeOfImage、故障 RVA 和驱动调用位置；未知布局或索引拒绝读取，不对其他版本套用私有字段。

## 已实现的候选行为

静态检查的驱动 DeleteTextures 路径释放纹理表项并归零，但没有在该路径中先调用设备 SetTexture 解绑。候选跟踪驱动 BindTexture 调用的阶段/ID，删除这些 ID 前先对对应设备阶段设置空纹理，再执行原删除函数。
只解绑删除列表匹配的阶段，不清空其他绑定、不跳过绘制、不吞掉异常；原参数、原调用次数及原返回寄存器值保持。设备对象改变时清空跟踪记录。
这是针对绑定生命周期的候选，不是已验证的游戏修复。其他创建/上传路径、未跟踪的绑定及损坏发生时间仍需现场验证。

## 版本与开关

- AsrD3DDrv.dll SHA-256：`27db21dee7dde8ca3463e11fab57cc0b7cf6a7ed3338c950b6b1181eed7959ed`。
- 驱动 vtable RVA `0x1a5a8`；BindTexture 槽 `0x2c` 指向 RVA `0x7b2f`，DeleteTextures 槽 `0x104` 指向 RVA `0x5390`。
- 启动前核对哈希；加载后核对 PE32、SizeOfImage、原槽值和预期指令。只改变进程内两个 vtable 槽，恢复页保护，不改磁盘游戏 DLL、系统 DLL 或保护模块。
- 默认关闭，只在显式 `--texture-lifetime` / `-TextureLifetime` 模式启用。加载日志须出现 `TEXTURE_LIFETIME_READY`；拒绝或失败不报告候选生效。
- 实际解绑记录 `TEXTURE_LIFETIME_UNBOUND_BEFORE_DELETE`；失败记录 `TEXTURE_LIFETIME_UNBIND_FAILED`。

```powershell
& tools/launch_workspace.ps1 -Workspace build/runtime/diagnostic-game -CaptureException -TextureLifetime
```

候选仅供独立诊断副本测试，正常无层副本不更换配置。本轮没有启动游戏；专用入口为本地生成的 LaunchTextureFix.cmd。
禁用时去掉 TextureLifetime 参数即可回到同一诊断配置的原行为，退出进程即撤销内存槽修改；正常入口始终不启用该开关。

## 已完成验证与待验收

自建样本先证明不解绑会在仍绑定时执行删除，再验证候选在删除前解绑、保留无关绑定、处理两个阶段并保持原返回值。合成 PE 验证未知映像拒绝、双槽安装、重复安装、页保护恢复和隔离回滚。所有样本不运行游戏、不显示窗口、不加载商业驱动。
53 项单元测试、8 项注册表隔离回归通过；完整异常采集链路另行回归。该证据不替代实际读档、场景及显示验收。
下一次仅测试同一存档：是否能载入、是否出现 READY/解绑日志、是否仍有模型闪烁或地形缺失。失败时保留完整转储，不继续叠加图形层。
