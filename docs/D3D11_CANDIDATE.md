# 独立 D3D11 图形候选

## 对照依据与当前状态

撤回 DDrawCompat 后，测试反馈确认可启动并读取存档，原有模型闪烁和地形缺失仍在。两项问题分开记录，不把恢复读档当作修复显示。
当前工作副本新增 dgVoodoo2 2.87.5 候选；未叠加 DDrawCompat、DxWnd 或其他图形层。未修改游戏 EXE、原有 Drv、保护模块、资源、注册表原安装设置及存档。本轮没有启动游戏。
图形候选仍待同一存档和场景实测，不作为发行支持声明。

## 来源、版本和许可

作者 Dege；[官方 2.87.5 发行页](https://github.com/dege-diosg/dgVoodoo2/releases/tag/v2.87.5) 与 [作者说明](https://dege.freeweb.hu/dgVoodoo2/ReadmeGeneral/)。
仅使用官方包的 x86 DirectX 1–7 部件，不提取 Glide、D3D8/9 或控制面板。

| 输入 | SHA-256 |
|---|---|
| dgVoodoo2_87_5.zip | `5ffde6927f7355ca3fdd5d785b581256a8e6539fa13e395a891ade6ba1040850` |
| MS/x86/DDraw.dll | `612a24408a090a3c6f3886557fa18034ee742e94ad0a40ebdf854d2816176c2e` |
| MS/x86/D3DImm.dll | `93c534f2d17419ea78f15551f7e0aac78b3c503733a840914fa063708a5afe8e` |

ZIP 哈希与官方 GitHub 发行资产 digest 一致。dgVoodoo2 为专有组件，不归入项目 MIT；作者条款允许游戏或模组附带个别文件，独立再分发要求完整包，并禁止通用多应用启动器或框架捆绑。本项目目前仅本地试验，不提交或再分发二进制。

## 配置与部署边界

- 显式选择 `d3d11_fl11_0`，避免 bestavailable 自动选择 D3D12；不修改系统 GPU 偏好。
- 虚拟显卡选择 `geforce_9800_gt`，依据作者对渲染错误的候选建议；不等于确定本作根因。
- 保持游戏内部渲染尺寸 `unforced`、原始比例及游戏控制的过滤和抗锯齿。
- 强制窗口候选为 borderless/fullscreensize，完整无边框、焦点和输入验收仍待测试；不强制真实宽屏、高分辨率或 60 FPS。
- 保留水印便于实际测试确认加载，不隐藏兼容层身份。

只新增 DDraw.dll、D3DImm.dll、dgVoodoo.conf 和受控 manifest。工具限定 build/ 副本，核对已支持原件与包哈希，拒绝路径链接、已有兼容层及运行中的游戏；失败不覆盖原件。

```powershell
python tools/graphics_candidate.py apply --workspace build/runtime/game --package build/dgvoodoo-research/dgVoodoo2_87_5.zip
python tools/graphics_candidate.py remove --workspace build/runtime/game
```

恢复先核对全部新增文件及 manifest，任一内容不匹配则停止，不依据 manifest 的任意路径删除文件。存档不属于应用或恢复对象。

## 非交互验证

37 项单元测试和 48 项文档检查通过。Win32 探针对新候选连续执行三次，各 120 帧 16 位深度遮挡检查均通过，最终退出码均为 0。探针报告 D3D11 模块已加载、D3D12 未加载；仅证明探针，不证明游戏已使用该路径。
探针不显示窗口、不启动游戏、不切换桌面模式。绘制完成和正常退出缺一不可。

## 下一次实际测试

收到测试确认后，从现有副本入口启动，首先载入此前存档，再检查截图对应场景至少 60 秒。分别报告读档是否成功、地形黑块是否消失、模型是否仍闪烁以及水印是否可见。
出现闪退时保存进程结果和系统事件；关闭游戏后移除候选即可返回已反馈可读档的无层基线。每项结果独立记录，不以启动或读档成功推断完整画面、媒体、无盘或中文支持。
