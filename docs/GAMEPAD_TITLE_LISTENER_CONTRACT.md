# Xbox标题确认的监听器契约回放（2026-10-14）

## 当前边界

镜头候选b536b28尚无更新的现场日志，本轮没有修改任何活动runtime模块或配置，
不覆盖玩家当前验收版本。Xbox实体菜单验收仍未通过；本轮补的是标题请求级证据。

## Verified：真实标题监听器不是A首按激活

支持MCAlpha.dll SHA256 5c701de93af6267b959c49e6927bee525bc0f3c68c8c6f51413515d13809d427。
REA/Ghidra只读反编译：
- 566cb从widget+17c取listener，02c01通过listener vtable+24转发sender,event,0,0。
  Evidence ev_fd5a3a44ffa43749002317aab916f1fa3dfb8fc1a8d67772ffd708adff4f2fc5、
  ev_b158e8b60729290ddb2f83837b0b685ebf9cffb3bb06685d312c2551b2ae5c62。
- 按钮bee80的+188为56aac，先发首按事件3b；+194为56ac7，先发松开事件3c。
  Evidence ev_83d2569c621e6fadb9447cfedf04e314c665e162085284d261164aa554bf7ae1、
  ev_a4c946e1fd91c550ca1d9584a65c339419e18f0823d0693c2a0a880626a7ce4f。
- 标题GUI c2340的vtable+24是b7ceb，GUI+1a8是标题场景。场景+70必须>3。
  该listener对四个ID只在event3c时接受：16c开始→请求6，16d读取→7，
  16e继续→9，16f退出→11。首按3b、持续39、空闲3a不会激活这些分支。
  Evidence ev_6afc626504fcaaf42f1d6e232f3a9d73a9ac08e2feb1b5d0818b8f35acea4a20。
- b874a先写场景+70，然后执行过渡/任务分支。请求9不是完成继续游戏；该函数还根据
  GUI+1ac走返回4或后续任务/11。此字段含义本轮未证实，不猜成存档可用性。
  Evidence ev_e05cb6b37b850754bb4e22bedc60db14c180478152ab14114996a8c64ec77104。

## 回放增强与验证

旧fixture只记录通用button首按/松开次数，没有任何标题listener。
加入请求级断言后失败：
`FAIL A release must reach source-shaped title listener commands not only a generic button callback`。
此RED证明旧测试覆盖不足，不是新发现了当前生产输入代码的故障。

现在fixture使用标题GUI/按钮原生类地址、四个原生ID和+17c→vtable+24转发，
经过实际生产XInput IAT/焦点钩子、原生形状键计数和鼠标命中；
自有listener只复现b7ceb的条件与过渡请求选择，不执行商业任务分配、绘制或加载。
验证：A首按/持续不产生请求；释放请求正确；随后空闲不重复；禁用项不接收；
真实鼠标接管继续项；第四项退出请求11；phase1拒绝标题请求。
菜单专用回放从51增至59项，完整世界/菜单回放从61增至69项。
输出明确transition_executor=not_run；不会把请求9当已加载存档。
独立两文件源码回滚重编译恢复51项菜单基准，活动游戏runtime未变。

## 剩余实机条件

仍没有执行真实标题listener、转场、存档列表或实体手柄。映射命中只证明合成链路，
不证明实体Xbox已解决A键问题，也不替代镜头/完整60FPS验收。
后续先完成镜头验收，再用runtime/Play-gamepad.cmd：方向选中后松开方向，
A按下再松开，检查四项各自结果；进入存档列表再检查A/B。不能只记录A按下瞬间。
开场A跳过另由原生Esc路径处理，不属于本标题请求回放。
本轮游戏启动0次，完整数据复制0份；汉化、Alt+Tab、标题美术和活动模块均未改。
