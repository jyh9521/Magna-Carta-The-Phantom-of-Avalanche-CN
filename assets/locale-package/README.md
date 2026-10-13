# 汉化离线候选增量包

需要已安装的受支持原版文件和Python 3。本包不包含完整游戏、专有字库或原始媒体；只含源摘要锁定的增量、自有启动隔离工具和文档。SOFTMAX开头Logo与开发人员名单整段保留，旧存档名字及24份指定低清装饰资源不处理。

```powershell
python apply_locale.py verify --package PACKAGE_DIR --source ORIGINAL_GAME
python apply_locale.py apply --package PACKAGE_DIR --source ORIGINAL_GAME --output NEW_GAME_COPY
```

输出必须是不存在的新目录；安装只生成独立副本，不覆盖原安装。源版本、补丁、目标摘要不一致会拒绝，不跳过未知版本。安装与校验不启动游戏。

回滚独立副本：

```powershell
python apply_locale.py rollback --package PACKAGE_DIR --source ORIGINAL_GAME --target NEW_GAME_COPY
```

回滚前验证全部目标摘要，存在额外修改则拒绝写入；恢复原始资源字节，保留自有工具及记录。用户存档不是补丁目标。完整QA要求见QA_CHECKLIST.md。`release_ready=false`和`in_game_verified=false`保持明确，不根据离线通过宣称已实机验收。

手动入口默认采用独立Direct3D设置并启用FocusGuard，先核对已验收render1080图形层/配置/驱动。缺少匹配兼容层会在游戏启动前停止。`Start.ps1 -PrepareOnly`仅准备配置，不启动游戏；退出后桌面分辨率及其他窗口大小是否保持需要实际复核。
