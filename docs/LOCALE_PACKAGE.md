# 全文候选结合与增量包

## 明确不处理项

直接用户决定记录在`locales/zh-CN/scope-decisions.json`：旧存档名字不适配、不改写存档；SOFTMAX开头Logo和开发人员名单不汉化。为避免有损重编码改变名单画面，MOV/MOV.pak整份原样保留，职位、姓名、配音表、公司署名、版权和结尾字卡均不回写。24份指定低清英文/装饰书页/符号继续原样保留，未算作译文。

## 本轮结合

- 结构目录4,137字段供给完整：4,091译文、46明确保留；427份结构资源与2份原生字库继续使用同一1,898字形映射。
- 170份单图和10组32tile共202份图像候选。第一套誓言的可读tile为299/300/301及303/304/305，302/306为空白，307只有模糊背景。按数字连续排列的旧调查拼图不是游戏布局定义；当前六个可读tile按实际文字/边缘关系拼合、裁回，六行均已回写。运行时位置仍需观察。
- 2段BMC文字候选共5,267帧，原压缩音频保留；SOFTMAX开头Logo整段原样保留，不附加中文。名单所在PAK没有进入补丁清单。
- 13条原生提示、Unicode设置对话框和系统消息适配器结合。系统规则生成器从原模块重新计算已声明文本/资源修改，要求与候选模块逐字节相同，再绑定候选SHA-256；不接受任意改版。6种系统消息的9个来源保持原字节。
- 系统消息解码同时接受合法CP949和字体映射中的私有字对。私有字对本来就在CP949无效区，两者不冲突。1,898字形逐一通过受控Unicode分派及实际自建IAT拦截，句柄、标志和返回值保留；没有加入旧人物名别名或存档转换。
- 原生入口可编译绑定确定的候选引擎SHA-256，仍拒绝未知版本。新增`--verify-only`只核对文件摘要，直接返回，不创建游戏进程、注册表会话或窗口。

## 构建

```powershell
python tools/build_system_messages.py --source SOURCE/MCAlpha.dll --plans locales/zh-CN/system-message-plans.json --module-candidate MODULE_PACKAGE/MCAlpha.dll --domain-plans locales/zh-CN/text-domain-plans.json --font-package FONT_PACKAGE --output NEW_SYSTEM_PACKAGE
cmake -S src/runtime -B NEW_NATIVE -A Win32 -DSYSTEM_MESSAGE_RULES_HEADER=ABSOLUTE_HEADER -DLOCALE_ENGINE_SHA256=VERIFIED_CANDIDATE_SHA
cmake --build NEW_NATIVE --config Release --target workspace_profile workspace_launcher system_messages_fixture
python tools/locale_package.py build --source SOURCE --candidates STRUCTURED_IMAGES_AND_MODULE_PACKAGES --runtime NEW_NATIVE/Release --scope locales/zh-CN/scope-decisions.json --output NEW_PACKAGE
```

候选列表分别提供结构资源/字库、单图、组图、模块、开场/Game over视频构建目录。每份build.json和实际候选摘要必须一致，不静默重新打包损坏候选。source、目标和运行工具摘要均记录；原名单和指定保留图另外受摘要保护。

## 应用、校验、回滚

增量包只应用到不存在的新副本，全部来源及补丁预检后复制原文件并生成修改资源。原安装不覆盖，复制和校验不启动游戏。

```powershell
python PACKAGE/apply_locale.py verify --package PACKAGE --source SOURCE
python PACKAGE/apply_locale.py apply --package PACKAGE --source SOURCE --output NEW_GAME_COPY
NEW_NATIVE/Release/workspace_launcher.exe --workspace NEW_GAME_COPY --verify-only
python PACKAGE/apply_locale.py rollback --package PACKAGE --source SOURCE --target NEW_GAME_COPY
```

回滚前验证全部目标摘要与安装标记；额外修改会拒绝全部写入。原字节恢复后保留自有工具/记录，不删除用户存档或原安装。原型LPD1为源引用与变更literal组成的zlib压缩增量；格式、大小、路径、压缩边界和重建摘要均验证。生成包和完整副本留在忽略的dist/build，不提交商业资源。

`.locale-runtime/Start.ps1`是明确手动入口，不由安装或校验自动执行。它只读取原有设置，在副本内生成会话配置，然后使用版本锁定隔离工具；不替换图形驱动。脚本已做语法检查，但没有执行。手工验收清单随包提供。

`all_game_text_complete=false`、`release_ready=false`及`in_game_verified=false`保持明确；离线文件与模型证明不能替代实际游玩、所有场景及渲染验收。

开头SOFTMAX Logo按直接用户决定整段原样保留，MOV/0023.BMC不进入补丁清单；曾含Logo译文的未发布候选已撤回。

## 离线验证记录

634资源清单全部重建、安装读回和独立副本回滚通过。基线293项测试和修改后303项测试均通过；自建系统消息模型覆盖1,898字形，实际自建IAT测试通过，未知模块退出125。`--verify-only`分别识别候选与回滚后原版摘要，均报告`game_started=false registry_changed=false`。

增量包同时保护Logo、名单与24份指定保留资源的原始摘要；旧含Logo译文包已撤回。结果只证明文件与受控模型，不代替实际游戏内验收。

候选启动入口继承OpenGL导致PixelFormat失败的实际日志及修正见[START_PROFILE_FIX.md](START_PROFILE_FIX.md)。当前入口在独立会话使用Direct3D、默认FocusGuard，并预检已验收无边框/1080兼容层摘要；`-PrepareOnly`不启动游戏，真实启动及退出后桌面布局仍待回归。

实际截图中的旧字描边残痕已按完整清理轮廓修正；202份图像复核、985→0像素对照、源保护和独立回滚见[IMAGE_RESIDUE_FIX.md](IMAGE_RESIDUE_FIX.md)。不将静态清理通过称作完整游戏内验收。

主界面改为两行银白艺术字及横线，菜单提高对比度；前景英文撤换、尾字跨tile修复、源保护及可复现素材见[TITLE_ARTWORK.md](TITLE_ARTWORK.md)。当前图像203份、完整增量635资源，实际新标题显示待观察。
