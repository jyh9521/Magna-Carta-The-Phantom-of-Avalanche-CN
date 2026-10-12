# 技术说明

## 当前证据

已取得安装样本、四张完整镜像、最小镜像及提供的 1.04 补丁。安装文件复制至隔离副本，来源保持不变。
已验证 PE32 架构、DirectDraw/OpenGL 导入、FPB 结构与原样往返；运行解码、字体映射、原生分辨率和计时机制仍待验证。
详细版本、差异与 PixelFormat 错误定位见 [样本调查](docs/SAMPLE_AUDIT.md)。
结论区分已验证、高置信推断和未验证假设，记录来源与适用版本。

中文项目使用独立仓库，英文汉化项目 Nejuf/magnacarta 为技术参考。其文件树提供 Drv 驱动线索，不构成本项目运行验证；MC_PLAY 依赖与存档路径待原版样本确认。
候选工具源码、资源往返及字体方案仍需审计，不根据扩展名断言支持。

# 本作现代 Windows 与无盘运行路线

- [正式路线](docs/MODERNIZATION_ROADMAP.md)：Windows 10/11、P0–P3、模块分离及回滚。
- [静态调查](docs/RUNTIME_RESEARCH.md)：MC_PLAY、驱动、兼容层和来源版本。
- [运行验收](docs/RUNTIME_TESTING.md)：窗口、显示、无盘、输入、时序和媒体。

没有已验收的免 CD、无边框、原生高分辨率或现代手柄方案。禁止隐藏自动挂载；保护机制先记录授权与限制，不实施绕过修改。

## 研究记录

格式字段与未知字节记录于 docs/FILE_FORMATS.md；有意义的失败记录于 docs/PITFALLS.md；玩家可见限制记录于 docs/KNOWN_ISSUES.md。
可执行补丁须锁定版本、原始哈希和预期字节，保存修改与回滚验证。
