# 入口预检恢复显示配置（2026-10-15）

## Verified：原问题与重放

共享 `StartShared.ps1 -VerifyOnly` 原本在调用原生验证器前写入所选显示 INI，检查结束后没有恢复；验证器失败时也保留了候选 INI。新集成测试执行真实共享脚本，输入为完全自有的临时配置与只接受 `--verify-only` 的自建验证器 EXE，不含商业游戏。

旧源码两种结果均实际失败：`b'owned wide4k\r\n' != b'owned baseline\r\n' : VerifyOnly left the selected candidate INI in game data`。这不是从“未启动游戏”推断无副作用，而是检查了实际文件字节。

## 修正

语言无关设置模块新增 `Invoke-EnhancementDisplayTransaction`，在已有共享互斥锁作用域内：

1. 原 INI 保存到内存，候选 INI 通过同目录临时文件与原子替换生效。
2. 原生预检仍看到与所选模式匹配的候选配置，不跳过既有版本/摘要守卫。
3. `VerifyOnly` 无论成功或抛错均在 finally 中恢复原字节；正常启动保留所选配置。
4. 若检查期间外部程序将 INI 改成第三种内容，则保留外部修改并报错，不盲目覆盖。
5. 拒绝目录/重解析点类型，临时文件只在操作期间存在，不创建永久回滚副本。

PowerShell 5.1 调用 `File.Replace` 的空备份参数须使用 `[NullString]::Value`，直接 `$null` 在当前环境被绑定成空路径并报错；该失败已实际观察并修正。

原输入映射、游戏模块、汉化、存档与 Alt+Tab 不变。本修正只保证游戏显示 INI 的事务语义；预检仍写已有 cache 中的 profile.bin 与验证器输出，不声称整个目录零写入。

## 验证与验收

```powershell
python -m unittest discover -s tests -p test_configuration_verify_transaction.py
```

六项测试包含成功恢复、失败恢复、正常启动保留配置、外部编辑保护，以及真实共享脚本通过自建验证器的成功/失败两条路径。游戏启动为零。

玩家仍使用 `runtime/Configure.cmd`：选择另一种模式后点“检查入口”，预检应通过但当前游戏显示 INI 应恢复；只有随后正常启动才保留所选模式。实体手柄与实际菜单指针验收另行确认，未因这些测试而标记通过。
