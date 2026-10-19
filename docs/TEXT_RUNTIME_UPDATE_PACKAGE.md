# 文本与对话运行模块小更新包

构建器读取部署后的共享运行目录及同次部署记录 `changes.json`，记录格式与
`tools/update_configuration_runtime.py` 一致：相对路径映射到 `before`、`after`
SHA-256，旧文件位于记录目录的 `original/`。构建器验证两侧摘要，只打包实际变化。

```powershell
python tools/build_text_runtime_update.py --runtime runtime --record build/text-dialogue-repair/deployment --output dist/text-runtime-update.zip
```

输出必须为新的独立 ZIP 路径。包内 `Update.cmd` 调用 Windows PowerShell，玩家无需 Python。
自有 modules DLL、workspace_launcher.exe 及 runtime.json 可以完整交付；商业资源仅交付
MCD1 稀疏替换增量（u64 目标长度，随后重复 u64 偏移、u32 长度、替换字节，全部小端）。
增量截断/扩展输出，只在不同字节区间保存最长 4096 字节的替换段；未变化区间依赖玩家现有文件。
拒绝包含整个目标资源字节的退化增量。数据路径白名单限 FPB、固定 ITM/ABI/SGI/CHA 表、
MCAlpha.dll 文本修改及 BGR 图片提示修改；不涉及字库、影视、存档或设置。

解压后对共享运行目录执行：

```powershell
./Update.cmd -Action Verify -Runtime "D:\Games\MagnaCarta-Runtime"
./Update.cmd -Action Install -Runtime "D:\Games\MagnaCarta-Runtime"
./Update.cmd -Action CheckInstalled -Runtime "D:\Games\MagnaCarta-Runtime"
./Update.cmd -Action Rollback -Runtime "D:\Games\MagnaCarta-Runtime"
```

Verify 仅验证原状态、全部载荷及重建结果，不写入。Install 全量预检后备份待修改文件到
运行目录 `.text-runtime-update/original/`，再原子替换各文件并记录安装标记。
CheckInstalled 验证安装标记与所有目标摘要。Rollback 在所有目标和备份通过摘要预检后恢复
原字节并删除原本不存在的自有模块。回滚保留备份与已回滚标记作为证据；同一个包仅在精确
回滚且所有旧备份再次通过摘要验证后可以重新安装，不会静默覆盖其他包的既有更新记录。
任何后续同名文件改动、未知版本、链接路径、重复路径或损坏载荷均拒绝覆盖。
玩家在安装后更改的存档和配置不进入更新文件白名单，回滚仍予保留。

自动验证：`python -m unittest discover -s tests -p test_text_runtime_update.py -v`。
使用合成资源实际调用 Windows PowerShell，覆盖只读预检、安装、安装校验、精确回滚、
新增模块删除、存档/设置保留、损坏载荷、损坏备份、原文件/安装后漂移、非法路径和损坏增量。
自动测试不启动游戏，不替代对话和提示文本的实机验收。
