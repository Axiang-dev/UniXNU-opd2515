# OPD2515 当前状态

更新时间：2026-11-09

## 已确认

- 设备能在 BDS 中通过 `fastboot boot` 执行 102.4 KB 的 EFI 镜像。
- UniXNU 能恢复 boot.img 中的 208 MiB ramdisk，显示 payload 中的 XNU 条目。
- DarwinBoot 已通过 v2 trust cache 校验、退出 UEFI boot services 并打印 handoff。
- XNU 入口检查点已实际运行到品红色条，即 MMU 打开前的最后一个已记录位置。
- S9 主机镜像新增官方 stage 3：MMU 开启后等待 6 秒，以 PSCI `SYSTEM_RESET` 复位。
- 全程没有执行 flash、erase 或 format；唯一持久写入是既有 userdata 尾部 4 MiB 日志窗口。

## 当前卡点

最后一个实机确认位置仍是 **XNU 品红色入口检查点**。S8 的三色之后再次出现菜单，
但当时没有 stage 3，也没有秒级时序，无法区分 MMU 前故障、MMU 后故障、panic 或固件复位。

S9 已完成主机侧准备和回读校验。相对 S8 payload kernel 只改变 64 字节：MMU 开启后的
跳转与 6 秒复位 cave；蓝条、品红条、panic 屏和 payload 其余成员逐字节不变。

## 下一轮实机验收

1. 手动进入 BDS，确认 `fastboot devices` 显示 `0000000000000000`。
2. 只执行 `fastboot boot <S9-boot-image>`；禁止任何 flash、erase 或 format。
3. 记录绿、蓝、品红出现到复位/菜单重现的秒数。
4. 三色后约 6 秒复位，才证明 MMU 开启指令执行并到达 stage 3。
5. 提前复位或超过 6 秒不复位都不能证明 MMU 完成；根据结果只增加下一个检查点。
6. 测试后进入 OrangeFox/REC，保持 userdata 原样，读取尾部日志。

## 尚未验证

- XNU 完成 MMU 初始化。
- 进入内核 C 启动路径或出现可靠 panic 输出。
- XNU 侧中断、定时器、UFS、根卷、显示、触摸/按键、GPU、网络、音频和电源。
- S9 镜像的实机启动结果。

当前状态不构成“可日常使用”或“iOS 已启动”的结论。

## 最新主机产物

| 产物 | 大小 | SHA-256 | 状态 |
|---|---:|---|---|
| S9 kernel | 55,570,432 B | `41CDEB9ED00A10F9D79663AECD5C690DB2CAF99E021B27DE6528E66B75057573` | 主机回读通过 |
| S9 payload | 218,103,808 B | `FADA945E507E8EEB82C2917241B3E68B7760A12B9BC1718EB9C048EF0A558CC0` | 主机回读通过 |
| S9 boot image | 218,210,304 B | `FA3930AE0FDF286BD2A2082C1AF1EF9DEE3C6D4888758A4190FF30572DF3BC2A` | 待实机 |
| `UniXNU.efi` | 102,400 B | `BD781B444EFBB55254622E3C47A113E2C066EC72993D5E5DF842F88A6F7CD4CF` | S9 镜像内字节一致 |
| `DarwinBoot.efi` | 27,136 B | `952B7636124D5454BABCBAFE6000D15E29A8588C1A2DA2D444E77BBEC73E5FDF` | S9 镜像内字节一致 |

详细回读记录见
[`docs/evidence/s9-host-validation.txt`](docs/evidence/s9-host-validation.txt)。

S8 实机照片来自变基前 boot image
`6112BC4C613F03CAA12EB4753E3358AB07240BB914260431CFA2C6C1AA992001`。
