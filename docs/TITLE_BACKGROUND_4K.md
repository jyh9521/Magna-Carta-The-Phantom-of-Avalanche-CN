# 4K标题背景扩展候选

玩家已确认上一轮标题坐标正确；本轮只扩展标题背景，保持已验收候选不变，独立输出到build/title-background4k-game。

## 离线重建

`python tools/build_title_background.py --source build/disc-gate-game --native build/advanced-display-native/Release --locale locales/zh-CN --output build/title-background4k-game`

输入背景来自本轮以玩家截图为参考的扩展绘制，深青/灰橄榄色旋涡布纹和暗色装饰延伸到16:9。生成原图1672×941，离线Lanczos重采样成3840×2160尺寸母图；4K尺寸不等于原生4K生成细节。现有透明字标作为独立层等比合成，不重新生成文字或修改按钮资产。原背景风格与装饰来源为SOFTMAX游戏标题；不把原游戏设计归为新创作。

可复现数据为locales/zh-CN/title-background-plan.json，锁定生成源、透明字标及12个用户提供原资源的SHA。完整原BGR不提交。构建无网络生成依赖，输出和原资源备份在build目录。

## 显示路径

本次独立候选入口经StartTitle.ps1验证12个资源SHA后设置MC_TITLE_BACKGROUND4K；底层StartAdvanced继续验证引擎、驱动与运行库。已验收advanced-display-game入口和运行库未更新。

两种标题布局仍各6个BGR节点，资源0357–0362/0363–0368。母图切为重叠2048×2048纹理，源x为0/1280/2560，源y为0/1080；重叠区来自同一母图，边缘透明填充。避免单张3840纹理要求。估算每组未压缩纹理96MiB，不等同实测显存。

仅布局209/210初始化时设置节点x/y与+40/+44等比缩放，保留z与其余节点；旧flag关闭时仍执行已验收107/134偏移。scale=物理宽度/2880，即原4:3高度/2160。16:9母图覆盖宽屏，非宽屏按母图中心裁切，按钮沿用原布局及点击代码。窗口分辨率由现有配置控制，不生成拉伸文字。

Verified（受控）：导出3840×2160、1920×1080、1280×720、640×480和800×600；裁切居中、纹理重叠逐像素相同、透明边缘、源漂移拒绝、旧flag路径、原生缩放与恢复分别验证。+24到BGR绘制变换及+40缩放字段基于此前同版本静态分析；最终商业运行像素、旧驱动2048纹理上传、透明混合及标题加载时间尚待玩家实测，不以PNG预览代替游戏验收。

## 验收与回滚

本次请使用新目录的Play-wide4k.cmd和Play-combined.cmd；另外Play-render4k.cmd/Play-baseline.cmd可验证4:3居中裁切。标题左右应有自然背景延伸、无黑色侧栏或拼接线；字标比例和按钮点击保持一致。进游戏后再返回标题，观察背景、按钮和稳定性。

关闭游戏后Rollback-title.cmd恢复此独立候选12个原标题资源，关闭HD标志；原已验收目录和存档不动。完整资源摘要及同一回滚在另一副本上的结果见build/title-background4k-final/VERIFICATION.txt。

离线准备时，Windows powershell.exe环境未加载Get-FileHash命令；入口已采用与既有StartAdvanced相同的.NET SHA256实现，而非依赖用户PowerShell模块自动加载。

## 英韩装饰名称重绘与原入口替换

检索交叉确认英文名称MagnaCarta: The Phantom of Avalanche（亦有Magna Carta分写）、韩文名称마그나카르타 ~눈사태의 망령~。资料：[英文条目](https://en.wikipedia.org/wiki/Magna_Carta%3A_The_Phantom_of_Avalanche)、[韩文GameMeca报道](https://www.gamemeca.com/view.php?gid=119517)、[概念设定集书目](https://www.aladin.co.kr/shop/wproduct.aspx?itemid=316586073)。本对象是2001年PC作品，不与后续진홍의 성흔或Tears of Blood混用。

新绘背景将原画笔触理解为韩文书写，将斜排英文理解为名称装饰，而非随机墨迹。暗色衬线MAGNACARTA、THE PHANTOM OF AVALANCHE与韩文마그나카르타、눈사태의 망령按检索拼写绘制，保留深青/灰橄榄旋涡布纹和低对比装饰；前景透明中文标题与按钮、native缩放/裁切代码不改。字形经过图像目视复核，不将书法字形识别宣称为自动OCR证明。生成源仍由离线构建器重采样为3840×2160母图。

`tools/refresh_title_background.py --workspace build/title-background4k-game --replacement build/title-names4k-game`验证旧/新12项资源、原资源来源一致、母图SHA和启动互斥锁后，仅更新标题资源及预览。上一版HD背景和清单逐项SHA备份；写入失败恢复已尝试文件。原已验收advanced-display-game以及商业引擎/字体/按钮/存档不改。

同一title-background4k-game入口继续使用本次替换版。Restore-previous-background.cmd恢复上一张HD背景；Rollback-title.cmd则恢复最初标题背景。独立副本的上一版恢复结果与基准/修改/恢复源码测试见build/title-names4k-evidence/VERIFICATION.txt。背景PNG预览不代替商业游戏实际验收。

## 按原图纠正英韩名称相对位置

玩家标注原图指出上一版韩文被错误放到左侧。此次仅修改背景源及布局意图数据：英文仍在右后方上层，韩文从MAGNACARTA的N附近下方起笔并顺同一斜向向右展开；移除左半幅韩文，恢复布纹。上方英文副标题与下方韩文副标题继续保留检索确认拼写，前景中文标题、按钮及全部native代码保持不变。

layout_intent是可复核的设计约束，不是测得的引擎字段。新增测试只验证约束数据保存正确，最终空间关系以生成图和合成4K图的目视复核、玩家复测为准；不把该测试描述成图像识别或像素定位证明。

仍通过build_title_background生成3840×2160母图及12个纹理，用refresh_title_background替换同一title-background4k-game。上一张错位背景摘要和18个文件备份保留，独立副本恢复上一版的结果见build/title-name-alignment-evidence/VERIFICATION.txt。

## 韩文小字与旋涡表面形变

本次背景韩文副标题明确采用玩家校正的눈사태의 유령，替换旧눈사태의 망령。先前网页名称仅保留为reference_korean_from_web历史资料，不再作为本背景小字的目标；前景中文标题与英文装饰拼写不改。

上一版文字呈平面斜贴感。新绘版沿布纹作明显非线性S形曲线，使英文及韩文笔画局部拉伸、收缩、倾斜，暗色墨迹随褶皱渐隐；保持英文上层、韩文从N附近下方起笔。typography_treatment是设计意图记录，测试仅验证该约束与目标字串，不声称自动验证艺术风格或OCR识别。

已有候选后续只需重新导出标题资产，不反复复制完整商业游戏：
`python tools/build_title_background.py --assets-only --source build/disc-gate-game --locale locales/zh-CN --output build/title-vortex-assets`
`python tools/refresh_title_background.py --workspace build/title-background4k-game --replacement build/title-vortex-assets`

assets-only输出不含游戏入口或商业执行文件，只含12个标题纹理、母图、预览及摘要清单。原版来源和标题源摘要仍先校验。完整新副本构建保留原--native参数路径。输出为3840×2160，native显示/裁切与按钮未改。上一版背景及18文件摘要恢复测试见build/title-vortex-evidence/VERIFICATION.txt；实机视觉仍由玩家复测。
