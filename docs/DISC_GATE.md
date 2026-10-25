# 无盘启动候选

## 已验证静态路径

适用于45,056字节的MagnaCarta.exe，原始SHA-256为`be2ae107373835defc6ec33643eaf435dcc5c882ea0b6e3c47032cd013690651`。启动函数VA`0x401000`扫描A至Z，要求GetDriveTypeA返回5，再查找根目录`\\MC_03`。不存在时显示重试/取消提示；不是MC_PLAY卷标比较。

匹配后FindClose关闭查找句柄，原逻辑加载MCAlpha.dll，取得`_GameMain@16`，使用原模块句柄、`/job:51 /file:0`及显示参数调用。返回非零时卸载并重载模块。MCBeta.dll与protect.dll不在这条启动器加载链中；相关文件的存在不证明当前EXE实际调用了保护模块。

补丁仅修改文件偏移`0x1025`的5字节：`BB 41 00 00 00`改为`E9 A7 00 00 00`，从VA`0x401025`跳往`0x4010D1`原LoadLibrary入口。跳过扫描和FindClose，避免对不存在的查找句柄执行关闭。导入表、大小、资源、其他代码均不改。目标SHA-256为`6046b29600b5e009903b3495bd11df0b4d89fc3545adde028193ea9fbff8d4de`。

MCAlpha的初始化函数`0x5200b8df`使用GetModuleFileNameA及ASRGetPathOnly推导文件路径，并传给ASRInitFile。这是硬盘目录初始化的静态依据，不等同于所有场景均无光盘访问。

静态证据：Ghidra12.1.4的`ev_8ccb07bc493bce8e07988ac176b63428cfb711228379e7248777b5c2adb91a08`、`ev_f8aacd90360e11f2ee6db6d79c19c157634e13ba1087d2b1bdd57ba6c00c0595`及`ev_ac721a95425918f6af2371471682897648bd5483ae4b702e7ce980028929b854`。反编译文本不是原始源码或运行观察。

## 受控验证

`tools/check_disc_gate.py`使用pefile2024.8.26、Unicorn2.1.4模拟原启动函数的机器指令，以记录桩替换所有Windows API和GameMain；不执行MCAlpha或游戏进程。

- 无盘原版：26次光驱类型检查、一次提示、取消返回1，不调用GameMain。
- 有盘原版：检查MC_03并关闭真实模型句柄，GameMain桩两次调用。
- 无盘修改版：零次光驱/文件标记检查、零次提示、两次GameMain桩调用，原参数和模块重载流程保留。
- DLL缺失：仍进入原错误提示/退出路径；格式化和退出CRT部分用记录桩表示。
- 反向恢复后与无盘原版结果完全相同。

模型验证不加载真实模块，不证明实际媒体播放、资源读取或新游戏/读档成功。`in_game_verified=false`，游戏未启动，未挂载镜像，未安装或修改保护驱动。

## 构建和副本应用

变更计划在`patches/disc-gate.json`，与翻译数据分离。通用等长补丁工具核对文件大小、完整摘要、预期字节、范围和最终摘要，不对未知版本尝试固定偏移修改。

```powershell
python tools/patch_binary_plan.py apply --plan patches/disc-gate.json --source ORIGINAL/MagnaCarta.exe --output NEW/MagnaCarta.exe
python tools/check_disc_gate.py --source ORIGINAL/MagnaCarta.exe --plan patches/disc-gate.json --output MODEL.json
cmake -S src/runtime -B NATIVE -A Win32 -DWORKSPACE_EXE_SHA256=6046b29600b5e009903b3495bd11df0b4d89fc3545adde028193ea9fbff8d4de -DLOCALE_ENGINE_SHA256=5c701de93af6267b959c49e6927bee525bc0f3c68c8c6f51413515d13809d427
cmake --build NATIVE --config Release --target workspace_launcher
python tools/build_disc_gate_bundle.py --launcher NATIVE/Release/workspace_launcher.exe --output NEW_BUNDLE
```

原生隔离入口新增显式编译绑定的EXE摘要；默认构建仍只接受原EXE，未知摘要继续拒绝。新的入口保留候选引擎摘要绑定与`--verify-only`，只核对文件且不启动游戏。

无盘候选增量包只包含计划、原创工具、原创入口和文档，不含完整商业EXE/DLL。解压后：

```powershell
python install_disc_gate.py apply --package PACKAGE --source ORIGINAL_OR_LOCALE_COPY --output NEW_GAME_COPY
NEW_GAME_COPY/.locale-runtime/workspace_launcher.exe --workspace NEW_GAME_COPY --verify-only
python install_disc_gate.py rollback --target NEW_GAME_COPY
```

来源为纯原版时，核对入口位于`.disc-gate/workspace_launcher.exe`。来源为汉化副本时，只更新该新副本的`.locale-runtime/workspace_launcher.exe`，系统消息/显示隔离模块不替换。回滚恢复EXE原字节及原入口，不改汉化资源、Logo、开发人员名单或存档。先撤销无盘候选，再按汉化包说明回滚汉化资源。

实际无盘验收尚未执行；后续需要明确启动要求，并记录未挂载介质情况下的菜单、新游戏、读档、场景切换、音乐、语音和视频结果。

候选启动入口继承OpenGL导致PixelFormat失败的实际日志及修正见[START_PROFILE_FIX.md](START_PROFILE_FIX.md)。当前入口在独立会话使用Direct3D、默认FocusGuard，并预检已验收无边框/1080兼容层摘要；`-PrepareOnly`不启动游戏，真实启动及退出后桌面布局仍待回归。
