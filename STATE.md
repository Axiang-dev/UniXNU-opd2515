# OPD2515 当前状态

更新时间：2026-11-09

## 已确认

- 设备能在 BDS 中通过 `fastboot boot` 执行 102.4 KB 的 EFI 镜像。
- UniXNU 能恢复 boot.img 中的 208 MiB ramdisk，显示 payload 中的 XNU 条目。
- DarwinBoot 已通过 v2 trust cache 校验、退出 UEFI boot services 并打印 handoff。
- XNU 入口检查点已实际运行到品红色条，即 MMU 打开前的最后一个已记录位置。
- 全程没有执行 flash、erase 或 format；唯一持久写入是既有 userdata 尾部 4 MiB 日志窗口。

## 当前卡点

最后一个有直接证据的位置是 **XNU 品红色入口检查点**。当前无法区分：

1. 在 MMU 打开或其后极早期挂住；
2. 触发 panic，但 panic 屏幕未及时落到可观察状态；
3. 固件/平台发生复位，随后重新进入 UniXNU 菜单。

S8 照片同时显示旧菜单和新的倒计时，但缺少发生时刻，无法只靠照片判断复位原因。
payload 没有 stage 3 定时复位补丁，所以不能把菜单重现归因于本项目配置的定时复位。

## 下一轮诊断原则

- 先读取 S8 后 userdata 尾部的最后 `UNIXNU:`、`DARWINBOOT:` 行，并记录从三条出现到
  菜单重现的秒数。
- 若日志只到 handoff，增加一个单变量 stage 3 检查点：优先固定
  `entry_probe_reset_after`；只有在需要比较时间窗时才使用
  `entry_probe_reset_delay = 6`。
- 每次只改一个检查点。每次最多 `fastboot boot` 一个镜像。
- 不进入 UFS、根卷、显示驱动或 GPU 开发，直到 MMU 后路径有直接证据。

## 尚未验证

- XNU 完成 MMU 初始化。
- 进入内核 C 启动路径或出现可靠 panic 输出。
- XNU 侧中断、定时器、UFS、根卷、显示、触摸/按键、GPU、网络、音频和电源。
- 变基后最新 `de8962a` 构建的实机启动结果。

当前状态不构成“可日常使用”或“iOS 已启动”的结论。