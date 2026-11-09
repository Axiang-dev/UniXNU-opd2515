# OPD2515 当前状态

更新时间：2026-11-09

## 已确认

- 设备能在 BDS 中通过 `fastboot boot` 执行 102.4 KB 的 EFI 镜像。
- UniXNU 能恢复 boot.img 中的 208 MiB ramdisk，显示 payload 中的 XNU 条目。
- DarwinBoot 已通过 v2 trust cache 校验、退出 UEFI boot services 并打印 handoff。
- XNU 入口检查点已实际运行到品红色条，即 MMU 打开前的最后一个已记录位置。
- S9 主机镜像新增官方 stage 3：MMU 开启后等待 6 秒，以 PSCI `SYSTEM_RESET` 复位。
- S9 实机再次出现三色，并在用户观察到的数秒后硬复位进入 Android；重启原因为 `reboot,`。
- 全程没有执行 flash、erase 或 format；唯一持久写入是既有 userdata 尾部 4 MiB 日志窗口。

## 当前卡点

最后一个实机确认位置仍是 **XNU 品红色入口检查点**。S8 的三色之后再次出现菜单，
但当时没有 stage 3，也没有秒级时序，无法区分 MMU 前故障、MMU 后故障、panic 或固件复位。

S9 已完成主机侧准备和回读校验，并完成一次实机初验。相对 S8 payload kernel 只改变
64 字节：MMU 开启后的跳转与 6 秒复位 cave；蓝条、品红条、panic 屏和 payload 其余成员
逐字节不变。实机已经观察到三色后的硬复位，但用户只能描述为“数秒”，还没有秒表级数值。

## 下一轮实机验收

1. 复跑同一个 S9 镜像，保持镜像、配置和其他诊断变量不变。
2. 用手机录像或秒表记录品红出现到黑屏/复位的秒数。
3. 约 6 秒复位后才把 stage 3 标为最终通过；提前复位或超过 6 秒不复位都不能证明 MMU 完成。
4. stage 3 最终通过后，下一条单变量测试改为官方 stage 4：在 `_arm_init` 中
   `_arm_vm_init` 调用之后复位。
5. 全程只允许 `fastboot boot`；禁止 flash、erase 或 format。

## 尚未验证

- XNU 完成 MMU 初始化。
- 进入内核 C 启动路径或出现可靠 panic 输出。
- XNU 侧中断、定时器、UFS、根卷、显示、触摸/按键、GPU、网络、音频和电源。
- S9 品红到复位的精确时序。

当前状态不构成“可日常使用”或“iOS 已启动”的结论。

## 最新主机产物

| 产物 | 大小 | SHA-256 | 状态 |
|---|---:|---|---|
| S9 kernel | 55,570,432 B | `41CDEB9ED00A10F9D79663AECD5C690DB2CAF99E021B27DE6528E66B75057573` | 主机回读通过 |
| S9 payload | 218,103,808 B | `FADA945E507E8EEB82C2917241B3E68B7760A12B9BC1718EB9C048EF0A558CC0` | 主机回读通过 |
| S9 boot image | 218,210,304 B | `FA3930AE0FDF286BD2A2082C1AF1EF9DEE3C6D4888758A4190FF30572DF3BC2A` | 实机初验通过，秒级时序待复核 |
| `UniXNU.efi` | 102,400 B | `BD781B444EFBB55254622E3C47A113E2C066EC72993D5E5DF842F88A6F7CD4CF` | S9 镜像内字节一致 |
| `DarwinBoot.efi` | 27,136 B | `952B7636124D5454BABCBAFE6000D15E29A8588C1A2DA2D444E77BBEC73E5FDF` | S9 镜像内字节一致 |

详细回读记录见
[`docs/evidence/s9-host-validation.txt`](docs/evidence/s9-host-validation.txt)。
实机证据和重启原因见
[`docs/evidence/s9-device-result.txt`](docs/evidence/s9-device-result.txt)。

S8 实机照片来自变基前 boot image
`6112BC4C613F03CAA12EB4753E3358AB07240BB914260431CFA2C6C1AA992001`。
