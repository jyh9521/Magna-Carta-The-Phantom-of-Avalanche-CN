> 2026-10-19复核：真实Windows D3D7使绑定surface增加引用。当前原生Bind/Delete连续200轮，
> 原路径与解绑候选都未访问违规。此前hazard模型只证明删除时仍绑定，不证明UAF或崩溃；
> 候选仍不默认开启。见[场景切换调查与真实COM反证](SCENE_TRANSITION_INVESTIGATION.md)。

# 正常驱动纹理生命周期候选

## Verified

REA复核当前正常驱动SHA-256 `00d443327abf56c94f9f088515ab29be63bab9650771a5cacdcef20ab85eff29`：DeleteTextures RVA52c8，vtable槽1a6ac，BindTexture RVA7a67，资源表object+100ea0，分配标记object+104ea0。原删除直接释放标记为1的surface并清零，没有先核对设备绑定。旧27db版本现场崩溃不能作为本版本的现场证明。

受控样本证明旧Bind跟踪候选漏掉未经过该Hook的实际绑定，回归退出1；新候选直接GetTexture核对8阶段，匹配待删除surface后解绑，查询临时COM引用分别Release。无固定对象缓存，也不根据失败Bind推测状态。无关纹理保留，重复stage和ID保留原删除顺序。

查询或解绑失败时整个批次暂缓删除，资源表保持分配状态，记录TEXTURE_CURRENT_DELETE_DEFERRED_*。此前成功解绑不回写绑定，可能短暂丢失纹理；被暂缓的资源只有之后再次删除或退出设备时才释放，可能增加显存占用。该选择避免明知解绑失败后继续释放。非法批次拒绝，不静默按未知索引访问。

只改内存DeleteTextures槽，原Bind槽不动；安装核对PE32/I386/SizeOfImage/原槽与15字节指令，启动器核对整文件SHA。CompareExchange和页保护恢复分别验证；未知槽拒绝回滚。纹理候选先安装，再组合显示和60FPSHook，失败终止启动而不是报告READY。

## High-confidence deduction

GetTexture获取的临时引用需要Release；COM约定及[Wine Direct3D7实现](https://github.com/wine-mirror/wine/blob/master/dlls/ddraw/device.c)支持该处理。Wine明确注明该行为未在Windows核实，故其实现不是本机系统DLL的现场证明。不得以Direct3D9文档代替Direct3D7验收。

## Unverified / 玩家验收

未自动启动商业游戏。正常驱动实际加载、重复读档、切场景与退出仍待验收，未确认历史崩溃由本生命周期路径造成。Alt+Tab鼠标、译文、字体和已接受画面保持不变。

生成：`python tools/prepare_engine_bug_trial.py --source build/disc-gate-game --native build/advanced-display-native/Release --locale locales/zh-CN --output build/engine-bug-game`。入口Play-texture-guard.cmd显式开启，Play-without-texture-guard.cmd关闭；两者读取同一增强设置。

验收同一存档：关闭候选读档一次；开启候选反复读档/切场景/返回标题，确认模型、纹理与速度不退化；日志出现TEXTURE_LIFETIME_READY，仅真实发生解绑才出现TEXTURE_CURRENT_UNBOUND_BEFORE_DELETE。失败保留session/profile.log和转储，不将无解绑日志算作路径覆盖。

低磁盘容量时使用tools/prepare_texture_overlay.py，仅复制独立运行模块到build/texture-guard-runtime，不替换已有配置副本的游戏数据或运行模块。Play-texture-guard.cmd与Play-without-texture-guard.cmd读取配置工具同一设置并使用同一互斥锁。关闭入口撤销候选开关，旧Play-configured.cmd仍使用旧模块。开启/关闭及五种模式均以VerifyOnly预检，不代表游戏内安装或删纹理路径已发生。
