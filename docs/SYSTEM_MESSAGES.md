# 系统提示Unicode候选

9处源字段对应6种消息：OBS槽/图片索引错误、存档损坏、存档版本不符、队伍对象缺失与跟随摄像机通知。语言数据在`locales/zh-CN/system-message-plans.json`；通用匹配、编码和导入表适配在`src/runtime/system_messages.*`，不把中文私有字槽交给MessageBoxA。

## 源绑定与行为

已验证静态调用：致命消息经MCAlpha的FUN_52001270格式化后调用USER32!MessageBoxA，再由原函数抛出异常。摄像机通知经FUN_52001395至MessageBoxA。致命正文由固定韩文前缀、额外换行和格式化载荷组成；标题由Critical、Magna Carta及`%s - %s`组成。基于反汇编和原始字节记录，不通过执行商业DLL确认。

构建器锁定原模块SHA-256、大小、9处原字节及终止符，验证格式参数的类型/顺序，重复来源的目标必须一致。生成的语言头只位于build目录，不提交商业模块或完整原始资源。

运行候选默认关闭。显式设置`MC_SYSTEM_MESSAGES=1`时，仅对MCAlpha导入槽启用；通过磁盘文件全SHA-256版本校验后替换MessageBoxA导入为受控分派。未知版本或导入槽缺失退出125，不绕过原启动器的版本锁。未包含语言头的普通构建没有可启用版本。

识别的消息使用显式CP949解码和MessageBoxW显示；窗口句柄、按钮/图标标志和返回值保留。未识别、过长、非法源编码或异常按原参数调用原ANSI接口。原调用者仍决定异常、关闭或继续行为，适配器不吞掉游戏异常。与Core.dll的异常采集分支分开，不改现有采集路线。

```powershell
python tools/build_system_messages.py --source ORIGINAL_GAME/MCAlpha.dll --plans locales/zh-CN/system-message-plans.json --output NEW_SYSTEM_PACKAGE
cmake -S src/runtime -B NEW_NATIVE_BUILD -A Win32 -DSYSTEM_MESSAGE_RULES_HEADER=ABSOLUTE_PACKAGE_PATH/system_message_rules.h
cmake --build NEW_NATIVE_BUILD --config Release --target workspace_profile system_messages_fixture
NEW_NATIVE_BUILD/Release/system_messages_fixture.exe
```

本命令不启动游戏，最后执行的是自建记录器样本，不弹出真实系统消息窗口。

## 实测

- 9处源字段的重复头构建逐字节一致；原MCAlpha始终未改动。
- 直接分派样本：9条普通消息、9条带致命前缀的消息和1条空标题消息，共19次Unicode记录；未知、附加前缀、过长、非法编码4次保持ANSI返回。句柄、标志和返回值一致。
- 实际IAT样本：自建DLL以MCAlpha.dll作为隔离样本名，生成与其磁盘SHA匹配的独立规则头，再实际加载自建profile。基线9条+未知消息共10次ANSI；修改后9次Unicode、未知1次ANSI，均退出0。所有UI接口使用自建记录回调，商业DLL和游戏未载入。
- 自建DLL追加尾部字节的同输入反例被全SHA门禁拒绝，退出125，没有显示窗口。
- 首次IAT样本复用编译器缓存的LoadLibraryW地址，未命中加载钩子而返回基线。样本改为读取实际导入槽后命中；不能把链接代码存在当作拦截已执行。

## 仍待结合全文候选

当前规则头锁定原MCAlpha摘要79e4c3d6af4afb2b75367a2b26fd8450ad25fa9f738612ea96809e312d33cb6f；上一批原生字段/对话框候选摘要不同，不混用。全文组装须重新验证全部宣告变化后绑定候选版本。动态`%s`若来自中文私有字槽，还须显示域转换；旧存档人名适配亦未完成。实际游戏错误/通知路径、原异常结束行为及完整发行包尚未验收。

本轮未复制候选到安装目录，不修改存档，不启动游戏。
