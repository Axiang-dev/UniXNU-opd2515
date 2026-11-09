# UniXNU-opd2515

OPPO Pad mini 5G（`opd2515` / OPD2515 / SM8845P “Alor”）的 UniXNU 独立设备仓库。

> ## 当前阶段
>
> 已通过 `fastboot boot` 进入 UniXNU、加载 payload 与 DarwinBoot，并在实机跑到
> XNU 入口的蓝色与品红色检查点。DarwinBoot 已打印
> `inputs validated; exiting boot services` 和 `hand-off to the kernel`。
>
> **尚未证明** XNU 已完成 MMU 初始化、进入内核 C 启动路径、进入存储/根卷阶段或启动 iOS。
> 绿色、蓝色、品红色三条都出现后再次出现菜单的具体时序仍在确认。
> S9 已在实机再次出现绿色、蓝色、品红色，并在用户观察到数秒后黑屏、硬复位进入 Android。
> 这给出了 MMU 后复位的初步证据；品红到复位的精确秒数仍需用秒表或视频复核，暂不把
> “约 6 秒”写成精确实测值。

> **注意：本项目主要由 AI 协助生成、实验和整理，代码与硬件结论都可能包含错误。**
>
> 地址、内存窗口、信任缓存和启动时序只对当前固件与镜像有效。未标为“已验证”的内容
> 都应视为待确认，不要直接移植到另一台设备或其他系统版本。

## ⚠️ 红线

- **只允许 `fastboot boot`。**
- **禁止 `fastboot flash`、`erase`、`format` 或修改任何分区。**
- 不要写入 `boot`、`abl`、`efisp`、`xbl`、`persist`、BDS 或 recovery。
- 保留 OrangeFox/REC；它是当前主要回退路径。
- 不要重新格式化 userdata。当前唯一获授权的持久写入，是既有 UniXNU 诊断代码覆盖
  userdata 尾部 **4 MiB** 日志窗口。该窗口会破坏 Android 文件系统尾部，回 Android 前
  必须另行重建 userdata。
- 进入 BDS 时手动重启，并在白色开机文字出现时按音量减；不要用
  `adb reboot bootloader`。

## 设备事实

| 项 | 值 | 证据 |
|---|---|---|
| 机型 | OPPO Pad mini 5G，OPD2515 | 实机与设备树 |
| 代号 | `opd2515` | 本仓库 |
| SoC | SM8845P / Alor / ALORP，`soc_id=727` | live DT / sysfs |
| CPU | 8 核，PSCI + GICv3 | live DT |
| 屏幕 | 1680×2520，`cont_splash_region` @ `0xFC800000` | live DT / framebuffer |
| 内存窗口 | 6 GiB @ `0x9_8000_0000`–`0xB_0000_0000` | 与 57 个 reserved-memory 节点做无重叠检查 |
| BDS fastboot | 序列号 `0000000000000000` | 实机 |
| OrangeFox/REC | adb 序列号 `42d72758` | 实机 |
| 目标 OS | iOS 16.5（20F66） | profile |
| XNU | 8796 | profile |

REC 自报 `fox_macan-eng`、`ro.product.device=macan`、`OnePlus_15R`，但系统指纹为
`oplus/ossi/ossi:16`。这些是 donor recovery 元数据，不能用来重写本机硬件身份。

## 当前进度

| 阶段 | 状态 | 证据 |
|---|---|---|
| BDS 执行 boot.img 中的 EFI | ✅ | 早期彩色检查点和 UniXNU 菜单 |
| payload / ramdisk 恢复 | ✅ | 菜单显示 `ramdisk: 208 MiB from boot.img buffer` |
| DarwinBoot 加载 | ✅ | `drivers 1 loaded / 0 failed` |
| trust cache 校验 | ✅ | v2 bundle 后不再出现 `Compromised Data` |
| DarwinBoot → XNU handoff | ✅ | `DARWINBOOT: hand-off to the kernel` |
| XNU 入口检查点 | ✅ | 蓝色条与品红色条实机出现 |
| S9 MMU 后计时探针 | 🟡 实机初验 | 三色后用户观察数秒硬复位；精确 6 秒时序待复核 |
| MMU 后启动 | ⛔ | 尚未验证 |
| 存储 / 根卷 / 用户态 | ⛔ | 尚未开始 |

更细的分阶段验收见 [`PROGRESS.md`](PROGRESS.md)，当前卡点和下一项单变量诊断见
[`STATE.md`](STATE.md)，完整过程见 [`HANDOFF.md`](HANDOFF.md)。

## 关键实机证据

| 产物 | 大小 | SHA-256 |
|---|---:|---|
| [`s8-darwinboot-xnu-handoff.jpg`](docs/evidence/s8-darwinboot-xnu-handoff.jpg) | 204,171 B | `46E73D13ECF40F43BC1F5C66BC07BA782A033CBDE95D881ADA08176B033384D4` |
| [`s8-post-handoff-unixnu-menu.jpg`](docs/evidence/s8-post-handoff-unixnu-menu.jpg) | 200,189 B | `5ECB83BC4C14871A30A10193C927F10A2E5D41498A98E448531D1113ED2146B4` |
| [`s9-entry-bands-reboot.jpg`](docs/evidence/s9-entry-bands-reboot.jpg) | 2,617,858 B | `057124BDAA26F855673A486E2E763221C093A8A4D69F956B2CA687ED7ACE1701` |

最新主机产物：

| 产物 | 大小 | SHA-256 | 状态 |
|---|---:|---|---|
| S9 kernel | 55,570,432 B | `41CDEB9ED00A10F9D79663AECD5C690DB2CAF99E021B27DE6528E66B75057573` | 含 6 秒 stage 3；主机回读通过 |
| S9 payload | 218,103,808 B | `FADA945E507E8EEB82C2917241B3E68B7760A12B9BC1718EB9C048EF0A558CC0` | 主机回读通过 |
| S9 boot image | 218,210,304 B | `FA3930AE0FDF286BD2A2082C1AF1EF9DEE3C6D4888758A4190FF30572DF3BC2A` | `fastboot boot` 实机初验通过；秒级时序待复核 |
| `UniXNU.efi` | 102,400 B | `BD781B444EFBB55254622E3C47A113E2C066EC72993D5E5DF842F88A6F7CD4CF` | `fastboot boot` 已通过；S9 镜像内字节一致 |
| `DarwinBoot.efi` | 27,136 B | `952B7636124D5454BABCBAFE6000D15E29A8588C1A2DA2D444E77BBEC73E5FDF` | 实机加载已通过；S9 镜像内字节一致 |

主机回读明细见
[`docs/evidence/s9-host-validation.txt`](docs/evidence/s9-host-validation.txt)。
实机观察、设备身份与重启原因见
[`docs/evidence/s9-device-result.txt`](docs/evidence/s9-device-result.txt)。

S8 实机证据对应的变基前 boot image SHA-256 为
`6112BC4C613F03CAA12EB4753E3358AB07240BB914260431CFA2C6C1AA992001`。
S9 的 kernel 相对 S8 payload kernel 只改变 64 字节：MMU 开启后的跳转与 6 秒 PSCI
复位 cave；蓝条、品红条、panic 屏和 payload 其余成员逐字节保持不变。

## 仓库内容

| 路径 | 用途 |
|---|---|
| `board.toml` | SoC、boot header、payload、内存窗口、OS profile |
| `dts/opd2515.dts` | 当前 6 GiB bring-up 内存窗口与 DT 身份 |
| `configs/opd2515_defconfig` | XNU 4K 入口阶段配置 |
| `package/unixnu.toml` | UniXNU 菜单、DarwinBoot 驱动和 XNU 条目 |
| `patches/xnu/` | iOS 16.5 / XNU 8796 板级补丁序列 |
| `patches/unixnu/` | OPD2515 所需固件层改动，可应用到固定上游提交 |
| `porting.toml` | 按子系统记录证据、边界与下一步 |
| `scripts/`、`tools/` | 打包辅助、payload 工具、日志读取工具 |
| `docs/evidence/` | 已公开的实机照片和主机校验摘要 |

## 构建

Apple IPSW、内核构建输入、平台 seed 和厂商固件都不会提交到此仓库。
`UNIXNU_UNIQUE_CHIP_ID` 必须通过本地环境或 GitHub Actions secret 提供，不能写入仓库。

推荐直接使用已经验证的固定提交：

```sh
git clone https://github.com/UniXNU/UniXNU.git UniXNU
git -C UniXNU checkout 8ec13bb1077502e53e8ba3b82c56842589b5c837

git clone https://github.com/Axiang-dev/UniXNU-opd2515.git UniXNU-opd2515
git -C UniXNU apply ../UniXNU-opd2515/patches/unixnu/0001-feat-opd2515-advance-firmware-boot-to-XNU-handoff.patch
cd UniXNU-opd2515
python3 ../UniXNU/scripts/porting-record.py check --device .
scripts/package.sh --check --os ios-16.5-20F66
scripts/package.sh --os ios-16.5-20F66
```

补丁固定应用在 UniXNU 上游
`8ec13bb1077502e53e8ba3b82c56842589b5c837`。打包和 macOS CI 的通用步骤以上游
UniXNU 文档为准；平台 seed 只通过本地环境或 CI secret 提供。
Windows 原生 EDK2 构建曾在当前工作树中验证；涉及本机 VS2022、LLVM、GnuWin32、
Mu_Basecore 和本机路径，不是独立 CI 承诺。

## 启动

仅在确认设备身份、备份和回退路径后执行：

```text
fastboot devices
fastboot boot <已校验的 boot.img>
```

不要在命令示例中替换成 `flash`。传输阶段出现 `no link` 时不代表镜像启动失败；
设备没有完整执行 boot.img 时也不能据此评价镜像。

## 已知问题与下一步

- 实机已到品红色检查点，但尚未看到 MMU 后内核输出或 panic 证据。
- S9 实机再次出现三色，随后在用户观察到的数秒后硬复位进入 Android；重启原因属性为
  `reboot,`。这是 MMU 后复位的初步证据。
- 目前没有精确秒表值。下一步应复跑同一镜像并录像或计时；约 6 秒复位后才能把 stage 3
  写成最终通过，提前复位或超过 6 秒不复位都不能据此宣称 MMU 初始化通过。
- XNU 侧显示、实体键/触摸、UFS、GPU、网络、音频和电源均未完成。
- S9 主机镜像不能替代实机计时结果，也不能据此宣称进入内核 C 路径。

## 许可

除另有 SPDX 标记的文件外，本仓库使用 BSD-2-Clause-Patent。第三方源码、Apple 组件和
设备厂商固件仍受各自许可证约束，本仓库不分发 Apple IPSW 或厂商固件。

## 致谢

感谢 UniXNU 上游、Mu-Silicium/EDK2 社区、DarwinBoot、XNU 8796/profile 维护者，以及
OrangeFox/REC 与设备树采集工具的作者。`UniXNU-caihong` 与 `UniXNU-rmx3551` 为本仓库的
公开格式和交接方式提供了参考。
