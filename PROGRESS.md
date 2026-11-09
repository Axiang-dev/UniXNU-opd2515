# OPD2515 进度

最后更新：2026-11-09

状态按证据分级：`主机验证` 表示构建、解析或结构检查通过；`实机验证` 表示有设备照片、
屏幕输出或用户确认；`计划` 表示尚未实现。任何未直接观察到的阶段都不升级状态。

## 阶段总表

| 阶段 | 状态 | 结论 |
|---|---|---|
| 身份与红线 | ✅ 实机 | SM8845P / Alor、1680×2520；测试只用 `fastboot boot` |
| S1 屏幕打点 | ✅ | 品红、黄、绿检查点可区分 EFI 执行位置 |
| S2 早期落盘 | ✅ | userdata 尾部出现 `UNIXNULG` 日志并可读回 |
| S4 无 payload 对照 | ✅ | 当前 EFI、菜单、按键与状态行正常 |
| S5 带 payload 对照 | ✅ | 确认失败发生在 ramdisk/payload 发现路径 |
| S6 ramdisk 恢复 | ✅ | 菜单显示从 boot.img 缓冲找回 208 MiB ramdisk，XNU 条目出现 |
| S7 DarwinBoot 加载 | ✅ | Security2 拒绝后改为私有内存缓冲重试，`drivers 1 loaded / 0 failed` |
| S7 trust cache | ✅ | 原始 IM4P 被 DarwinBoot 判为 `Compromised Data`；转 v2 bundle 后通过 |
| S8 DarwinBoot handoff | ✅ 实机 | `inputs validated; exiting boot services`、`hand-off to the kernel` |
| S8 XNU 入口探针 | ✅ 实机 | 绿色、蓝色、品红色三条依次出现；品红表示已到 MMU 打开前 |
| S9 MMU 后定时复位探针 | 🟡 主机已准备 | 只新增 stage 3，实机需确认三色后约 6 秒复位 |
| MMU 后内核 | ⛔ 未证明 | 没有 CSV/串口/panic 屏幕或后续日志证据 |
| 存储 / 根卷 / 用户态 | ⛔ 未开始 | 当前 defconfig 明确关闭 UFS、显示和 GPU |

## S1–S8 验收记录

### S1：屏幕打点

- 品红 = EFI 入口。
- 黄 = 调用 ramdisk 发现前。
- 绿 = 调用返回。
- 从已确认的 BDS 再次内存启动后，实机观察到品红、黄，随后黑屏，说明 EFI 已执行但
  ramdisk 发现路径没有正常返回。

### S2：提前持久日志

- 将 4 MiB 诊断窗口放在 userdata 尾部，使用 `UNIXNULG` 头、递增 sequence 和多个 flush 点。
- S2 仍黑屏；进入 REC 读回日志后确认 S2 落盘子项通过，但菜单和 XNU 条目未出现。
- 该日志窗口是全部持久写入的唯一例外。

### S4：无 payload 对照

- 修正状态行后，菜单可同时显示 ramdisk 和 log 两行。
- 状态为 `ramdisk: not found in FDT or memory`、
  `log: userdata @0x726590F000`、`no boot entry found`。
- 按键、倒计时和返回固件动作均通过。

### S5：带 payload 对照

- `fastboot boot` 成功，实机仍为品红 → 黄 → 黑屏。
- REC 日志证明问题位于发现 payload 的 UEFI 路径，而非 boot.img 传输失败。

### S6：找回 boot.img ramdisk

- 通过扫描 BDS 保留的 fastboot boot.img 内存缓冲，找到 208 MiB ramdisk 并注册块设备。
- 菜单显示 `ramdisk: 208 MiB from boot.img buffer, first 58EB` 和
  `OPPO Pad mini - Darwin XNU (xnu)` 条目。
- 首次 XNU 选择返回 `Unsupported`；进一步接入 DarwinBoot 后继续。

### S7：DarwinBoot

- 路径式 `LoadImage` 被固件 Security2 返回 `EFI_ACCESS_DENIED`。
- 改为从私有内存缓冲 `LoadImage`，仍让固件执行 Security2；DarwinBoot 随后加载成功。
- 首次内核启动返回 `Compromised Data`。根因是 `kernel.macho.trustcache` 仍为 Apple
  IM4P；本项目改用官方 `bundle-ipsw-trust.py` 生成单模块、2,759 条目的 v2 bundle。

### S8：XNU handoff 与入口检查点

- trust cache v2 通过后，DarwinBoot 打印：
  `inputs validated; exiting boot services`、`DARWINBOOT: hand-off to the kernel`。
- 实机随后出现绿色、蓝色、品红色三条：
  - 绿色：DarwinBoot 已退出 boot services 并进入交接。
  - 蓝色：XNU 入口在 MMU 关闭状态下已执行。
  - 品红：CPU 已到达打开 MMU 之前的位置。
- 主机检查确认 kernel 包含 stage 1、stage 2 与 panic-screen 补丁，但没有 stage 3 的
  定时复位补丁。
- 三条之后再次出现 UniXNU 菜单。当前尚未确认这是自动复位、返回固件还是新的启动循环，
  因此不把“复位后再次进入 XNU”算作已通过。

## 最新构建

变基到 UniXNU 上游 `8ec13bb1077502e53e8ba3b82c56842589b5c837` 后得到提交
`de8962a9bcf838bfc16b8571f43449663d094194`。主机重新构建与回读通过：

| 产物 | 大小 | SHA-256 |
|---|---:|---|
| `UniXNU.efi` | 102,400 B | `BD781B444EFBB55254622E3C47A113E2C066EC72993D5E5DF842F88A6F7CD4CF` |
| `DarwinBoot.efi` | 27,136 B | `952B7636124D5454BABCBAFE6000D15E29A8588C1A2DA2D444E77BBEC73E5FDF` |
| payload | 218,103,808 B | `567330FF26814DDFFF14DB4812E11C9D3C7AE686C22A1FE3CD5A6E34744FE588` |
| boot image | 218,210,304 B | `902C6D3FC978E6468A8C0A136A7C09FF24C22799E4E5C7E54347C0AA17AC3C2D` |

上述最新产物尚未再次实机启动。S8 实机照片来自变基前
`6112BC4C613F03CAA12EB4753E3358AB07240BB914260431CFA2C6C1AA992001`。

## S9：MMU 后定时复位检查（主机已准备，实机待验收）

- 依据 UniXNU 官方 `docs/guide/debugging.md`，品红条只证明 CPU 到达打开 MMU 之前。
  S9 只增加 `entry_probe_reset_delay = 6`：MMU 开启后等待 6 秒，再以 PSCI
  `SYSTEM_RESET` 复位。
- 修正 `scripts/patch-xnu-entry-probe.py` 中 panic screen 与 reset cave 的空间冲突。同时启用
  两者时，reset cave 放在入口后的空填充 `0xFFFFFFF0073FA4A0`；蓝条、品红条和 panic
  screen 的地址与内容保持不变。修正提交为
  `840fbdb4f7260dedcde53a10dc5c437ef28e30b8`。
- 无 reset 回归构建与原 payload kernel 逐字节一致，SHA-256 均为
  `E810A2E36F4113CABAF02028B9DD816E7D337CD538F40FC6D11DDA92C5FDBA38`，证明工具修正
  没有改变 S8 路径。
- S9 kernel 与 S8 payload kernel 只有 64 字节不同。反汇编确认原
  `mov x0, #0x300000` 后读取 `CNTPCT_EL0` 等待 6 秒，再执行 PSCI reset。
- S9 kernel 为 55,570,432 B，SHA-256
  `41CDEB9ED00A10F9D79663AECD5C690DB2CAF99E021B27DE6528E66B75057573`；payload 为
  218,103,808 B，SHA-256
  `FADA945E507E8EEB82C2917241B3E68B7760A12B9BC1718EB9C048EF0A558CC0`；boot image
  为 218,210,304 B，SHA-256
  `FA3930AE0FDF286BD2A2082C1AF1EF9DEE3C6D4888758A4190FF30572DF3BC2A`。
- payload 内 `unixnu.toml`、ADT、v2 trust cache 与 DarwinBoot 相对 S8 payload 逐字节不变；
  boot image 头、EFI 段和 payload 段均通过主机回读。
- 详细主机证据见 [`docs/evidence/s9-host-validation.txt`](docs/evidence/s9-host-validation.txt)。
- 实机验收标准：三色后约 6 秒复位才证明到达 stage 3；提前复位不能证明到达；超过 6 秒
  不复位则说明 CPU 没有到达 stage 3。当前尚未执行 S9 实机启动，不能把主机结果写成
  MMU 或内核 C 路径已通过。
