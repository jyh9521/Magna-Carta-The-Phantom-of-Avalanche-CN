# 提示文本与对话显示修正

2026-10-19。提示文本按显示域全量检查，不以人物对白替代菜单和原生提示的覆盖。

## 提示标点

已验证：检查4,722个目标字段，其中474个属于物品栏、原生通知、设置对话框、
系统消息或菜单图片提示。25字段删除30个句末中文句号；复查符合规则的剩余字段为0。
含中英文逗号、多句、问句、感叹句、分号或省略号的行保持原样。
`$n`和实际换行划分独立提示行；格式参数、控制符、源摘要与资源ID保持原样。
普通人物对白、开场叙述、视频字幕和参考原文不套用提示标点规则。

变化范围：ITM两条物品说明、13条原生提示模板、4条设置提示、5条系统消息、
1条音量图片提示。获得道具、消耗道具、属性提升与卡尔塔亲和度提示均覆盖。
ABI、SGI、CHA固定表复查没有遗漏的同类句末候选。

## 可复现构建

策略为语言数据，通用工具不内置中文提示分类。先从旧版语言数据执行审计并保存变化清单，
再对当前语言数据应用策略，最后使用同一清单构建当前已汉化资源的增量候选。

```powershell
python tools/normalize_prompt_punctuation.py --locale OLD_LOCALE --policy locales/zh-CN/prompt-punctuation-policy.json --report OLD_AUDIT.json
python tools/normalize_prompt_punctuation.py --locale locales/zh-CN --policy locales/zh-CN/prompt-punctuation-policy.json --report CHANGES.json --apply
python tools/build_prompt_update.py --data-root runtime/data --locale locales/zh-CN --changes CHANGES.json --header runtime/build-inputs/system_message_rules.h --font LOCKED_FONT --font-lock assets/font-sources/noto-sans-sc.json --output NEW_TEXT_CANDIDATE
```

第一条审计发现待修字段时退出2，清单仍写入；无待修字段退出0。候选必须为新目录。
构建器保留当前1,898字槽映射，不因删除字符重新排序字库。
MCAlpha.dll仅修改原生数据槽与UTF-16设置资源；`.text`和`.rdata`逐字节不变。
音量图片先用旧文案复现当前图像并逐字节比较，再只重绘提示自身的布局框，保留邻近“注意”。
生成头文件以ASCII/LF确定性写出，记录摘要与落盘文件一致。

原生对话钩子的事件、阶段、分页与离线证据见[对话补全](DIALOGUE_REVEAL.md)。
新MCAlpha.dll源锁为`7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e`。
原有标题、光标、键盘离线回放及Field只读调查同步批准这份全文件摘要，报告实际输入摘要；
旧版仍受支持，未知文件继续拒绝，不以“代码看似相同”代替来源锁。
构建workspace_profile前采用候选的system_message_rules.h；构建workspace_launcher时将
`LOCALE_ENGINE_SHA256`设为同一摘要，其余字体和开场生成头保持不变。

```powershell
python tools/deploy_text_runtime.py apply --runtime runtime --candidate NEW_TEXT_CANDIDATE --native build/native/Release --record NEW_DEPLOYMENT_RECORD
python tools/build_text_runtime_update.py --runtime runtime --record NEW_DEPLOYMENT_RECORD --output dist/NEW_UPDATE.zip
```

部署只更新三份变化资源、八份自有profile、launcher及摘要清单；全量验证后写入，失败恢复旧字节。
生成头文件应与该次候选一起保留，用于后续重建。更早版本/未知摘要不自动转换；
本次小包要求与部署记录完全匹配的旧版运行文件，包的安装与回滚见[小更新包](TEXT_RUNTIME_UPDATE_PACKAGE.md)。

## 验收边界

自动检查包含全量文本规则、编码/结构、图片旧渲染复现、原生输入/渐显离线回放、
生产钩子Win32夹具、小包真实PowerShell安装及独立精确回滚。源商业文件只以增量分发。
存档、增强设置、字库、其它对白和开场图像保持原样。

本轮源基线540项、修改后565项Python回归通过；两个独立的小型变化文件副本分别
执行小包安装／回滚和开发回滚脚本，13份变化文件均恢复旧摘要，主运行目录保留新摘要。
本机13份存档在部署前后逐份校验不变。上述副本只包含变化文件，不复制整套游戏。

实际游戏画面和物理输入仍需人工验收。使用原有`runtime/Play.cmd`，
在文字尚未显示完时点击对话框或按放一次空格，当前屏应补全；再次操作才继续。
长对白应在补全当前屏后保留可读内容，下一次操作续读；同时检查物品说明和获得道具提示。
