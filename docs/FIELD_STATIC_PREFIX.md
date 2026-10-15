# Field静态前缀与地图关联（2026-10-15）

## Verified：原生读取链

MCAlpha SHA256 `5c701de93af6267b959c49e6927bee525bc0f3c68c8c6f51413515d13809d427`。

`65f90` 将 Field 文件首个DWORD读入 FieldInfo+4；`68996` 将 FieldInfo放在scene+10cc，随后用scene+10d0调用`8a3f0`加载区域。因此文件首字段是WRD资源ID，不是Field文件名本身。文件+8读入FieldInfo+c，并用于`FPB/%04d.fpb`，是PlayBook引用。其他前缀字段不凭取值猜测用途。

REA：Field路径 ev_b39f5df301c5146e03539db39d4bfd9ce36be23e3156e91d3abdf3bf0ed0803c；完整读取顺序 ev_dc0796cb41c75e46bd7c97a182b4e97389bd3c3aa1d91b67097caccc039d690b；场景关联与对象实例化 ev_6fae70035077092bc33e7e86d7712fd93214acedef345430260204e6444c8cdd。

固定前缀1060字节后是light计数。序列化记录长度与运行时结构步长并不总相同：

| 记录 | 文件长度 | 内存步长 | 处理 |
|---|---:|---:|---|
| light | 76 | 76 | 只跳过 |
| actor | 52 | 60 | 资源ID与XYZ |
| object | 56 | 72 | 资源ID、kind与XYZ |
| CCTV | 124 | 124 | 只跳过 |
| region | 112 | 232 | 中心、ID与8个角点；6个平面在运行时计算 |
| event camera | 20+(samples+1)*76 | 头24+分配数组 | 有界跳过 |
| wave | 204+points*samples*36 | 动态结构 | 有界跳过 |

wave数量来自文件+244；显示标签仍是+252容量18字节，读取器不解码、不改标签。kind=3的对象在已核原生场景加载分支创建FNPC，kind=6/7创建箱体对象；静态存在不证明当前剧情启用或箱体未领取。

读取至静态区结束后，原游戏还通过场景虚函数读取动态脚本尾部。新工具明确返回`full_file_parsed=false`与`remaining_opaque_bytes`，不把跳过未知尾部称作完整FLD解码。

## 只读样本核对

597份本地Field中，572份静态前缀通过，25份被长度/计数/坐标/样本数守卫拒绝。通过者包含1886条actor、3319条object、446个region体积；543份首字段指向现存WRD文件。这里的“文件存在”不是几何可解析或区域已实机加载的证明。

全部572份仍有未解释尾部；25份拒绝也不直接称为原游戏损坏，可能有旧布局或未使用资源。未推断区域连接、任务、出口、碰撞或可行走路线。

```powershell
python tools/resource_field.py --source runtime/data/Field --maps runtime/data/MAP --engine runtime/data/MCAlpha.dll --report build/field-prefix-report.json
python -m unittest discover -s tests -p test_resource_field.py
```

批量工具先验证用户原引擎完整SHA，始终只读；报告必须新建在两个数据目录之外。报告只含摘要、ID和计数，不导出对象位置数组或原标签。八项测试覆盖自有序列化样本、未知尾部、截断、计数上限、非有限坐标、-1地图哨兵、错误引擎和报告路径保护。

## 当前边界

本轮是地图后续数据层准备，不改现用入口或运行模块，不新增地图显示或导航声明。手柄菜单实机验收仍待确认；汉化冻结、Alt+Tab搁置。没有启动商业游戏，也没有复制游戏数据。
