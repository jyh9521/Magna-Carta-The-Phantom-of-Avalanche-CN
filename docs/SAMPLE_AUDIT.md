# 首轮样本与启动错误调查

日期：2026-10-12。阶段：隔离工作区、版本识别、资源往返与启动错误定位。
已验证表示静态文件、配置或测试证据成立；运行行为另列，不以静态检查代替游戏验收。

## 隔离与输入完整性

安装目录只作为读取来源。工作副本位于 `build/runtime/game/`，包含 11,784 个文件、2,669,674,586 字节。
复制前、复制后以及首轮分析后的来源与副本清单/哈希一致。`game/` 和 `build/` 均不进入版本控制。
完整文件清单、原文 catalog、镜像、补丁和配置备份保持本地；公开记录仅包含工具、结构与必要指纹。
本轮未修改安装目录、镜像、游戏程序或注册表，未应用补丁或附带修改文件。

## 版本锁定与差异

| 文件 | 字节数 | SHA-256 |
|---|---:|---|
| MagnaCarta.exe | 45056 | `be2ae107373835defc6ec33643eaf435dcc5c882ea0b6e3c47032cd013690651` |
| MCAlpha.dll | 1089536 | `79e4c3d6af4afb2b75367a2b26fd8450ad25fa9f738612ea96809e312d33cb6f` |
| Drv/AsrD3DDrv.dll | 155648 | `27db21dee7dde8ca3463e11fab57cc0b7cf6a7ed3338c950b6b1181eed7959ed` |
| Drv/AsrGlDrv.dll | 45056 | `ad6b5cafdcebcecf41754dbd0b225fe898a08282b917c2205a00da4317ca4e46` |
| MCV104a.exe | 5500831 | `527ec4ae3fce5b9dc03e5af338a397c413e74af3a24397fe0dff9e2452ffd4e0` |

提供的 MCV104a.exe 可作为 ZIP 自解压容器只读解析，共 882 个文件条目：878 个与安装目录哈希一致，3 个不同，1 个未安装。
不同项是 Net.dll、Protocol.dll、Replacer.dll；未安装项是 MCAutoCopy.exe。
MCAlpha.dll、MCBeta.dll、MCSetup.exe 等与提供补丁一致，但不能据此将整个安装标为纯净官方 1.04；来源及差异原因仍待核实。
补丁未执行，容器中的任何程序均未启动。

## 架构、图形及媒体

- 已验证：18 个 EXE/DLL 样本均为 x86 PE32；64 位 Windows 目标不意味着使用 64 位代理 DLL。
- AsrD3DDrv.dll 导入 DDRAW.dll 的 DirectDrawCreateEx / DirectDrawEnumerateExA；AsrGlDrv.dll、Asr3dfxGl.dll 导入 OPENGL32.dll / GLU32.dll。
- 实际运行的 API 版本和兼容层加载仍须日志验证，不能仅由导入确定全部图形行为。
- MCAlpha.dll 导入 Bink 和 Miles；样本元数据分别为 Bink 1.2a、Miles 6.1a。MOV 存在 BMC、PAK 和 IDX，读取与播放链路待验证。
- 设置、输入与窗口导入包含 Win32 ANSI API；非韩文区域、DPI、焦点和鼠标坐标仍须运行对照。

## PixelFormat 启动错误

### 运行报告

挂载提供的最小镜像，双击原版后出现：`Unknown Error - Cannot Match PixelFormat`。
这是提供截图所证明的失败结果，不是隔离副本运行通过。本轮未由测试工具启动游戏。

### 静态与配置证据

- `Cannot Match PixelFormat` 出现在 AsrGlDrv.dll 和 Asr3dfxGl.dll；本轮未在 AsrD3DDrv.dll 找到该文本。
- 当前用户注册表虚拟化位置保存 52 字节的 `MCSetting`。原始 byte offset 1 为 `1`，配置中的宽、高与色深数值为 640、480、16。
- 对锁定的 MCAlpha.dll，RVA `0x961A` 起读取结构 byte offset 1：值 `1` 选择 AsrGlDrv.dll，值 `0` 选择 AsrD3DDrv.dll。此为配置选择分支，不是可执行补丁位置。
- MCSetup.exe 的读取逻辑同样使用 52 字节 MCSetting；默认设置包含 OpenGL 选择。

高置信判断：错误与当前旧 OpenGL 像素格式选择相关，优先测试 Direct3D 分支。该错误不单独证明光盘保护是否通过，也不证明最小镜像可满足全过程运行。

### 当前处理结果

`tools/runtime_settings.py` 已从原始设置副本生成 Direct3D 候选，只改变 byte offset 1 的 `01 → 00`，其余 51 字节保持。
候选仅保存在本地独立文件，尚未写入注册表或应用到运行进程，因此尚未认定错误修复。
注册表安装路径仍指向来源目录；后续启动器必须隔离安装路径与设置读写，不能仅改变工作目录后假定全部访问均在副本。
下一步建立可恢复的运行配置隔离，再核实实际加载模块位于副本，验证 Direct3D 启动与窗口行为。

## 光盘与保护

| 镜像 | 字节数 | SHA-256 |
|---|---:|---|
| CD1 | 568008704 | `4b7a5c26687b9214c61f5d2da8830d82407c30c7ee33201e4e09ab9b21aada95` |
| CD2 | 689387520 | `6b1838e45dcce643be973ad95508354b930f26009325716b505a4cd390adba94` |
| CD3 | 681816064 | `f289cf84d88b212adfa82e1e2277959c855dd9c2ba2c3c149a2552129ec07088` |
| CD4 | 674539520 | `af768a772fbf20326e8077aa751e56cb2b8aff33be0f17c90dd39a56ca0e03fa` |
| CD4 最小镜像 | 925696 | `e5973103419e58eee72a06daa7ee2721b7cdfad88de1a96d656a80bb24b20c0b` |

完整 CD4 的 ISO9660 卷标为 MAGNA_CARTA_CD_4，存在 MC_03 标记，包含 2,722 个文件条目，不是仅供存在性检查的空盘。
与安装目录对比：2,710 个相同、5 个同大小不同内容、2 个大小不同、5 个未安装。不同项包括图标与六个 TXRS 资源。
已比对的 MOV、SMD 等数据在硬盘副本存在，但尚未验证运行时是否仍读取光盘。
镜像包含额外修改目录，未用于工作副本；镜像原始来源与修改范围仍需核实。

最小镜像 PVD 卷标为 MC_PLDSK，pycdlib 1.14.0 因双字节序字段不一致拒绝解析；该结果不等同于 Windows 挂载失败，不自动修复原件。
完整镜像枚举时出现 UDF 终止记录警告，ISO9660 命名空间仍可读取，不能将该结果扩展为全部文件系统实现兼容。

MCBeta.dll 与 protect.dll 的版本元数据标记为 Star Force / CD-ROM Copy Protection Module。
保护的实际调用、驱动及授权条件尚未验证；本阶段不修改保护模块，不使用附带保护规避文件。
无盘运行尚未实现，后续分别调查硬盘资源路径与保护依赖。

## 文本与字体

- FPB：606 文件、3,524 记录，183 空表；606 个原样重建全部字节一致，所有记录可 CP949 严格解码。并非中文回写或显示验收。
- ITM / ABI / SGI：各 1 文件，记录计数分别为 88 / 205 / 87，记录尺寸关系见 FILE_FORMATS.md。
- BGR：422 文件；格式识别、转换与重建仍待完整验证。
- Font：Chi0/1、Eng0/1、Kor0/1 共 6 文件；MCAlpha.dll 存在相应字体路径字符串。Chi 命名是研究线索，不证明简体中文字符覆盖或选择机制。
- CharData/0000.cha、UiData 的 UIS 等还包含可读文本线索，不能把可见文本范围限定为五类资源。

## 上游工具审计

参考 Nejuf/magnacarta commit `9ce77cace0d717f5ad75bb2910517802e55932c8`，读取 12 份 README、许可与脚本，仅存本地研究目录。
FPB 字段线索按实际样本独立验证；Python 工具独立实现，未把上游脚本或原始资源纳入提交。
Ruby 脚本使用 ISO-8859-1 作为字节容器并固定 ko/en 目录，不能视作已经支持 UTF-8 中文。SGI 提取脚本还依赖 pry。
FPB 脚本的 strip、换行替换与偏移累计可能影响原样往返；当前实现保留原始字节，中文回写另行设计。

## 已完成检查与下一阶段

17 项工具单元测试、48 项文档检查；FPB 实样往返 606/606；安装来源与副本哈希完整性检查通过。
本阶段没有游戏实测通过项。PixelFormat、保护依赖、设置隔离、中文显示、无边框及媒体播放均保持待验证。
下一阶段优先处理副本启动设置隔离和 Direct3D 同输入对照，然后开展字体映射、资源覆盖与最小中文证明。
