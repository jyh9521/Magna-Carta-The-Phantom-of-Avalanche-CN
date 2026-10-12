# 构建说明

已建立隔离复制、只读调查、输入比对和 FPB 原样往返工具；中文回写、字体生成及发布构建入口尚未完成，没有可安装汉化包。样本哈希见 docs/SAMPLE_AUDIT.md。

最小中文显示的字形层诊断构建、独立副本及恢复命令见 [显示探针](docs/GLYPH_DISPLAY_PROBE.md)。仅修改四个字形槽，不构成完整中文回写方案，游戏验收待执行。

下一阶段 [资源显示探针](docs/TEXT_DISPLAY_PROBE.md) 仅回写一个 SGI 武器名称为诊断字符串，原版六字库不变。已有受控回写入口，但完整中文导入、字体生成和发行构建仍未完成。

Status 已取得完整中文字符串的实际截图。SGI 名称 catalog、参考术语表版本锁定及跨作品一致性检查命令见 [术语对照](docs/SERIES_TERMS_AUDIT.md)，此阶段只读取原始资源和参考文件，不执行游戏。

全量目录清点、统一文本 catalog、图片文字覆盖及最终统一测试流程见 [全文管线](docs/FULL_TRANSLATION_PIPELINE.md)。当前结构提取 3,992 字段，不将未解析资源静默计为已完成。

预定流程：版本验证 → 提取 → 导入译文 → 控制符/编码校验 → 字体覆盖 → 重建 → 结构验证 → 游戏验收 → 增量发布。
原始文件保留只读基线，修改作用于副本；未知版本、预期字节不匹配或资源结构错误时停止。
生成产物使用 build/、dist/ 或 out/，不进入源码目录。

当前文档检查：安装 Python 3 后执行 `python tests/check_runtime_docs.py --expect modified`。此检查不证明游戏功能。
构建输入、来源、依赖和命令必须记录，不依赖私人目录或手工中间文件。发布前在干净检出重建，验证哈希、安装、卸载和回滚。
完整商业资源不进入仓库或发布包，第三方组件单独记录版本和许可。

## 样本调查命令

工具使用 Python 3.12 或更新版本；本轮验证版本为 3.12.14。安装研究依赖：

```powershell
python -m pip install -r tools/requirements-research.txt
python tools/prepare_workspace.py --source ORIGINAL_DIR --target build/runtime/game --manifest build/runtime/installation-manifest.json
python tools/inspect_game.py --workspace build/runtime/game --images game --report build/runtime/static-survey.json
python tools/compare_inputs.py --workspace build/runtime/game --iso "game/Magna Carta CD 4.iso" --patch game/MCV104a.exe --report build/runtime/input-comparison.json
python tools/resource_fpb.py --source build/runtime/game/Fpb --report build/runtime/fpb-roundtrip.json --catalog build/runtime/fpb-catalog.json
python -m unittest discover -s tests -p "test_*.py"
```

ORIGINAL_DIR 为只读来源路径；复制工具拒绝已有目标及嵌套源/目标，不覆盖已有实验。原文 catalog 与完整报告保持在忽略的 build/ 中。
上述命令不启动游戏、不应用补丁、不挂载镜像，也不写注册表。图形配置候选工具只生成独立文件，不能视为已生效设置。

## 原生启动隔离工具

Win32 构建、配置隔离测试与运行入口见 [副本启动隔离](docs/RUNTIME_ISOLATION.md)。该原生启动工具与前述只读调查命令分开：只读命令不启动进程，启动工具新建独立 HKCU 会话并启动副本，但不改写原安装登记或文件。

同一 CMake 工程新增 `graphics_probe.exe`，接受显式绝对路径的 DirectDraw DLL，使用非交互离屏目标测试深度遮挡，不启动游戏、不改变桌面模式。图形层安装、单层约束和恢复命令见 [图形候选](docs/GRAPHICS_CANDIDATE.md)。

完整异常采集和模拟回归见 [转储分析](docs/CRASH_ANALYSIS.md)。构建中的 `capture_core_fixture` 输出模拟 Core.dll，只用于自建故障样本，不复制到游戏副本；实际游戏 Core.dll 保持版本校验。非交互采集测试命令为 `python tests/check_exception_capture.py --bin build/runtime-native/Release --output build/capture-test`，输出目录须为新目录。
