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
