# OPD2515 UniXNU 交接记录

> 本文件收录 OPD2515 bring-up 的追加式历史。`STATE.md` 是最短当前状态，`PROGRESS.md`
> 是按验收点整理的进度，`porting.toml` 是与 UniXNU 工具兼容的结构化记录。
>
> 历史章节中若出现“完全不写 userdata”等较早的概括，以第 15 节及当前红线为准：
> 当前唯一获授权的持久写入是既有 userdata 尾部 4 MiB UEFI 诊断窗口。不得格式化
> userdata，也不得写入任何 boot、ABL、EFISP、XBL、persist、BDS 或 recovery 分区。
>
> 全部设备阶段只执行 `fastboot boot`。本文档不提供 flash、erase 或 format 步骤。

---
# OPD2515（OPPO Pad mini）UniXNU 移植 — 交接文档

- 更新时间：2026-11-09 03:41（CST）
- 工作目录：`C:\Users\27699\Documents\Codex\2026-11-09\unixnu-oppo-pad-mini-opd2515-12`
- 设备：OPPO Pad mini 5G（OPD2515），SM8845P / Alor，8 核，1680x2520
- 目标系统：iOS 16.5（20F66），XNU 8796
- 当前阶段：**BootRamDisk 已接线并通过编译；确认设备 BDS 会丢弃 boot.img 的 ramdisk 字段，已加入“从内存里的 boot.img 定位 ramdisk”的备选路径。等设备重新连上 USB 做实机验证。**

---

## 0. 五分钟速览

已经能证明的事：

1. WSL 交叉工具链可用，XNU + 原生内核可以完整编译、链接、prelink。
2. GBL/BDS 能 `fastboot boot` 我们的 Android boot 镜像，并执行其中的 `UniXNU.efi`。
3. 实机屏幕、缩放（1680x2520）、菜单、按键都正常（见 `outputs/opd2515-unixnu-ui/menu-verified.jpg`）。
4. payload FAT 卷内容正确，里面确实有 `EFI/UniXNU/unixnu.toml` 和 55.5 MB 的 `kernel.macho`。

还没做到的事：

1. 现有 GBL/BDS 固件**没有把 boot 镜像的 ramdisk 发布成文件系统**，UniXNU 找不到 payload，菜单显示 `no boot entry found`。
2. 内核 `kernel.json` 的 prelink 资格标记仍为 `false`（`loadable / abi_qualified / instruction_relocation_complete / register_dataflow_qualified`），未做 ABI 级验证。

下一位接手先看 **第 14 节（最新进展）**，再决定是否需要走 8.A 的后续备选。

---

## 1. 红线与约束（必须遵守）

- **只允许 `fastboot boot`（内存启动）**。不要 `fastboot flash`、不要写 `boot / abl / userdata / efisp / persist` 等任何分区。
- 不要覆盖平板上现有的 TWRP recovery 与 GBL/BDS 引导环境，这是目前唯一的回退路径。
- 不要为了“验证”去格式化或重建 userdata。
- 设备当前可能停在 fastboot 或 TWRP；操作前先确认模式，再决定命令。
- 任何持久化写入都必须先得到用户明确同意。

---

## 2. 设备与硬件事实（已从实机采集）

| 项 | 值 | 来源 |
|---|---|---|
| 型号 | OPPO Pad mini 5G / OPD2515 | 设备树 |
| SoC | SM8845P（Alor / ALORP），soc_id 727 | `soc_id`、`qcom,alor-mtp` |
| CPU | 8 核，MPIDR affinity 0-7，PSCI + GICv3 | `dts/opd2515.dts`、`work/device-capture/live.dts` |
| 内存窗口 | 6 GiB @ `0x9_8000_0000` – `0xB_0000_0000` | 与实机 57 个 reserved-memory 节点逐一比对，无重叠 |
| 屏幕 | 1680x2520，`cont_splash_region` = `0xFC80_0000` + `0x2B00_000` | 实机 FDT / sysfs |
| 定时器 | 19.2 MHz system / generic timer | 实机 DTS |
| 当前 recovery | donor TWRP（OnePlus 15R / ovaltine / PGP110），已修触摸 | adb 识别为 `twrp_ovaltine`，属 donor 元数据 |
| GBL/BDS | 平板上已安装；工作副本 `work/gbl_root_canoe/`、`D:\IDM Download\oppo_pad_mini_gbl_root_canoe\`（`BDS.efi` 290,816 B） | 实机 |

实机采集物都在 `work/device-capture/`：`live.dts`（2.28 MB）、`live.dtb`、`dmesg.txt`（2 MB）、`iomem.txt`、`partitions.txt`、`boot_a-header.bin`、`vendor_boot_b.img`、`dtbo_b.img`、`abl_a/b-current.img`、`efisp-current.img` 等。这些是只读证据，不要回刷。

`work/device-capture/persist-efisp/` 里还有从设备抓下来的 ABL/EFI 工具文件，仅作分析留档，**不要执行、不要写回**。

---

## 3. 引导链与断点（最关键的一节）

### 3.1 现在的链

```
fastboot boot <boot.img>
   └─ GBL/BDS（平板自带）
        └─ 取 boot.img 的 kernel 区（= UniXNU.efi，102,400 B）执行
             └─ UniXNU 菜单（EFI 应用）
                  └─ 期待从某个 FAT 卷读 EFI/UniXNU/unixnu.toml
                       └─ 读不到 → "no boot entry found"
```

### 3.2 boot 镜像实测结构

`work/opd2515-xnu-payload-fastboot.img`（218,210,304 B，SHA-256 `C743818654E31FE7E423416C9B5BF18ABA3DC335C86B6D39A65EC0C7634B38CD`）：

- header v0，page 4096
- `kernel` = 102,400 B → 就是 `UniXNU.efi`（PE32+，machine 0xAA64）
- `ramdisk` = 218,103,808 B（正好 208 MiB）→ FAT32 卷，OEM `MTOO4043`（mtools 生成）
- `second` = 0

FAT 卷内容（已解析确认）：

```
/EFI/UNIXNU/UNIXNU~1.TOM      422 B      -> unixnu.toml
/EFI/UNIXNU/PAYLOADS/KERNEL~1.MAC  55,570,432 B -> kernel.macho
/EFI/UNIXNU/PAYLOADS/KERNEL~1.ADT      14,288 B -> kernel.adt
/EFI/UNIXNU/PAYLOADS/KERNEL~1.TRU      66,265 B -> trustcache
```

`unixnu.toml` 内容（正常）：

```toml
version = 1
[boot]
timeout = 3
default = "xnu"
[kits]
autoload = false
[[entry]]
id = "xnu"
title = "OPPO Pad mini - Darwin XNU"
type = "xnu"
path = "Payloads/kernel.macho"
args = "-v serial=3"
# 另有 reset / shutdown / tools 三个 action 条目
```

**结论：payload 本身没问题，问题在“谁把这个 FAT 卷挂出来”。**

### 3.3 对照实验

`outputs/opd2515-unixnu-ui/uniXNU-OPD2515-ui-scale4-superfastboot.img`（106,496 B）：

- `kernel` = 102,400 B（同一个 UniXNU.efi）
- `ramdisk` = 0
- 实机点亮菜单，同样显示 `no boot entry found`

说明菜单、显示、缩放、输入都正常；失败点就是“没有可见文件系统”。

### 3.4 已有但未生效的方案

- `work/UniXNU/package/UniXNUPkg/Driver/UniXNURamDiskDxe/`（已编译出 24 KB 的 `UniXNURamDiskDxe.efi`）
  - 走 Mu-Silicium 的 entry-arg HOB（`DAEE82E6-8090-4E72-BFB9-78C13CD4E359`）拿 FDT，再读 `/chosen` 的 initrd。
  - 在 GBL/BDS 单独启动 EFI 应用的场景下**没有这个 HOB**，所以它不会工作；而且 BDS 不会替我们加载这个 DXE。
- `work/UniXNU/package/UniXNUPkg/Library/UniXNULib/BootRamDisk.c`（194 行，**2026-11-09 02:50 新写，未接线、未编译**）
  - 同一思路的“应用内版本”：用 `EfiGetSystemConfigurationTable(&gFdtTableGuid)` 拿固件 FDT，读 `/chosen` 的 `linux,initrd-start/end`（或 `initrd-start/end`），注册一个只读 BlockIo，让后面的 FAT 驱动认出卷。
  - **这是当前最省事的突破口**：如果 BDS 把 ramdisk 地址写进了固件 FDT，就能避免整套 Mu-Silicium 固件卷移植。

---

## 4. 目录地图

```
unixnu-oppo-pad-mini-opd2515-12\
├─ build-opd2515.cmd              # 一键入口（转调 tools\build-opd2515.ps1）
├─ tools\
│  ├─ build-opd2515.ps1           # Windows 侧：开 transcript、映射路径、调 WSL
│  └─ build-opd2515.sh            # WSL 侧：fetch / defconfig / tree / build kernel
├─ work\
│  ├─ UniXNU\                     # 上游主仓（含本地改动，见第 5 节）
│  ├─ UniXNU-opd2515\             # 设备仓（board.toml / configs / dts / patches / package）
│  ├─ UniXNU-sm8845-common\       # SM8845 共用 SoC 仓（local.toml 指向它）
│  ├─ uni-mu-basecore\            # EDK2 / Mu_Basecore（约 86 MB）
│  ├─ uni-build\                  # EDK2 构建工作区；产物 Build\Out\AARCH64-DEBUG\*.efi
│  ├─ ref-UniXNU-*\               # 7 个参考移植（nx769j-ios165、sm8550-common、star/ace6/fuxi/sheng…）
│  ├─ ref-xnu-8796.121.2\         # 上游 XNU 参考树
│  ├─ gbl_root_canoe\             # GBL/BDS 副本
│  ├─ device-capture\             # 实机采集（只读证据）
│  ├─ recovery-capture\           # TWRP 采集
│  ├─ opd2515-xnu-payload-fastboot.img   # 208 MiB payload boot 镜像（最新候选）
│  ├─ unixnu-menu-superfastboot.img      # 早期菜单镜像
│  └─ unixnu-menu-1680x2520-superfastboot.img
├─ outputs\
│  ├─ opd2515-build\
│  │  ├─ kernel\kernel.macho      # 55,570,432 B
│  │  ├─ kernel\kernel.json       # prelink / 资格报告（15 MB）
│  │  └─ logs\                    # 构建日志（见 6.3）
│  ├─ opd2515-unixnu-ui\          # 菜单镜像 + 实机照片
│  └─ opd2515-boot-attempt.log    # 最后一次 fastboot boot 记录
└─ docs\HANDOFF.md                # 本文档
```

---

## 5. 源码版本与未提交改动

### 5.1 主仓 `work/UniXNU`

- HEAD：`3c8f96f ui: bound portrait scale by panel height`
- `git status`：4 个修改、2 个新增

| 文件 | 改动 | 原因 |
|---|---|---|
| `scripts/linux/prepare-xnu.py` | 增加 `-MJ` 编译记录输出 | 归档构建和 boot-progress 层要读 `.o.json/.cpo.json` |
| `scripts/build-xnu-4k-baseline.sh` | 去掉 `-MJ` 参数末尾空格 | 否则 `lastkernelconstructor.o` 报 `no input files` |
| `scripts/unixnu/kernel.py` | bootstrap 判定同时要求 `startup.o.json` 与 `IOPlatformExpert.cpo.json` | 首次构建记录不全，避免误判已就绪 |
| `scripts/unixnu/devicetree.py` | 生成 `/cpus` 时只收 `device_type="cpu"` 的节点 | 实机 DTS 的 `/cpus` 下有 `cpu-map` 拓扑节点，会被误当 CPU |
| `profiles/os/ios-16.5-20F66/`（新增） | `profile.toml`、`configs/ios.config`、`patches/xnu/series`、`README.md` | iOS 16.5 / XNU 8796 的 OS profile |
| `package/UniXNUPkg/Library/UniXNULib/BootRamDisk.c`（新增） | 194 行，见 3.4 | **未接线** |

### 5.2 设备仓 `work/UniXNU-opd2515`

- **一个 commit 都没有**（`master` 是 unborn branch），所有文件都是 untracked。接手后建议先本地 commit 一次，避免误删无法回溯。
- 关键文件：
  - `board.toml`：board/组件/kernel/bootimg/payload/adt 全部板级参数
  - `configs/opd2515_defconfig`：只开 `ArmDTPlatform / ArmCpu / SoftwareAES / XnuPrelink / DarwinBoot`，**UFS / 显示 / Adreno / 虚拟块设备全部关闭**
  - `dts/opd2515.dts`：6 GiB 内存窗口 + splash 保留区
  - `patches/xnu/series`：64 个补丁（含 native-4k、pmap、work-interval、offline-owner 系列）
  - `patches/libpthread/*`：2 个
  - `scripts/emit-prelink-ios165.py`、`scripts/package.sh`
  - `package/unixnu.toml`
  - `porting.toml`：**仍是模板（name = "example"），未填**
- `local.toml` 把 `sm8845` 指到 `../UniXNU-sm8845-common`；`feeds.toml` pin 的是 `8d9573f6`。

### 5.3 依赖 pin（`unixnu.lock`）

```
xnu              c54f35ca767986246321eb901baf8f5ff7923f6a
libpthread       c0e60fb5ecfc54cf379c261d3f9572cc22ded891
libplatform      a00a4cc36da2110578bcf3b8eeeeb93dcc7f4e11
libdispatch      30fe6a7d945340ce69cef121132f049e810089a5
corecrypto-2023  11fba65b12d8830630e248dfa8344caf8b065f26
AvailabilityVersions 933f9360f1b70dfbda5548386a3d65e0358b4f7d
IOStorageFamily  e45fbe30a7879e0b16e26dddb78538f1b00e0bff
edk2             cfb93724a06ff86ff5ba971413368a7809ee42a5
```

---

## 6. 构建环境

### 6.1 环境事实

- WSL2（Ubuntu，root），`.wslconfig`：`memory=12GB`、`processors=20`、`swap=4GB`（Linux 实际看到约 11 GiB）
- 工具链：`/opt/unixnu-linux`（clang、ld、xnu-host-cc、migcom、iig、lzfse、xcrun 包装）
- 构建输出：`/opt/unixnu-opd2515-out`（WSL 内，约数十 GB）
- 锁：`/var/lock/unixnu-opd2515-build.lock`（flock，重复执行会直接退出 73）
- 默认 `-Jobs 12`；增量内核构建实测 **1 分 44 秒**（02:32:07 → 02:33:51），峰值内存约 1.4 GiB

### 6.2 命令

```powershell
cd C:\Users\27699\Documents\Codex\2026-11-09\unixnu-oppo-pad-mini-opd2515-12

.\build-opd2515.cmd -Stage status      # 只检查，不构建
.\build-opd2515.cmd -Stage prepare     # fetch + defconfig + tree
.\build-opd2515.cmd -Stage kernel      # 编 XNU + 原生内核（最常用）
.\build-opd2515.cmd -Stage all         # 全流程
.\build-opd2515.cmd -Stage kernel -Jobs 12
```

等价 WSL 直调：

```bash
wsl.exe -u root -- bash /mnt/c/Users/27699/Documents/Codex/2026-11-09/unixnu-oppo-pad-mini-opd2515-12/tools/build-opd2515.sh \
  /mnt/c/Users/27699/Documents/Codex/2026-11-09/unixnu-oppo-pad-mini-opd2515-12 \
  /mnt/c/Users/27699/Documents/Codex/2026-11-09/unixnu-oppo-pad-mini-opd2515-12/work/UniXNU-opd2515 \
  kernel 12 \
  /mnt/c/Users/27699/Documents/Codex/2026-11-09/unixnu-oppo-pad-mini-opd2515-12/outputs/opd2515-build
```

EFI（`UniXNU.efi`）单独构建：

```bash
cd /mnt/c/.../work/UniXNU/package
UNIXNU_EDK2=/mnt/c/.../work/uni-mu-basecore \
UNIXNU_BUILD_DIR=/mnt/c/.../work/uni-build \
./build.sh -b DEBUG -t GCC
# 产物：work/uni-build/Build/Out/AARCH64-DEBUG/UniXNU.efi （102,400 B）
```

> 注意：`work/uni-build/Build/Out/AARCH64-DEBUG/` 下还有 `UniXNURamDiskDxe.efi`、`XnuTest.efi` 等，都是同一次 EDK2 构建的副产物。

### 6.3 日志

| 文件 | 说明 |
|---|---|
| `outputs/opd2515-build/logs/kernel.log` | 最终内核构建主日志（114 KB） |
| `outputs/opd2515-build/logs/kernel-bootstrap.log` | 首次 bootstrap 全量日志（**417 MB**，别用编辑器直接打开） |
| `outputs/opd2515-build/logs/opd2515-20261109-023207.log` | 最后一次成功构建的 PowerShell transcript |
| `outputs/opd2515-build/logs/component-*.log` | ArmCpu / ArmDTPlatform / SoftwareAES 的 `-Werror` 审计，全部通过 |
| `outputs/opd2515-boot-attempt.log` | 最后一次 `fastboot boot`：`Sending 'boot.img' (213096 KB) OKAY` + `Booting OKAY` |

---

## 7. 产物与校验

| 产物 | 大小 | SHA-256 |
|---|---|---|
| `outputs/opd2515-build/kernel/kernel.macho` | 55,570,432 B | `8691B0DE99A1291D3A42BE0950FC05A508626E3E3C10360B173F723789EAAAA8` |
| `work/opd2515-xnu-payload-fastboot.img` | 218,210,304 B | `C743818654E31FE7E423416C9B5BF18ABA3DC335C86B6D39A65EC0C7634B38CD` |
| `outputs/opd2515-unixnu-ui/uniXNU-OPD2515-ui-scale4-superfastboot.img` | 106,496 B | `407777C7A72A95CEF6E7E8FDC1CDA9D520D40A0FFB96A07FFAA1D70983761CA2` |

`kernel.macho`：Mach-O `0xfeedfacf`，ARM64，`MH_EXECUTE`。
`kernel.json` 关键字段：

```
candidate_bytes                    = 55,570,432
slide                              = -16,777,216
instruction_relocation_complete    = false
abi_qualified                      = false
loadable                           = false
runtime_qualified                  = false
register_dataflow_qualified        = false
early_security_initializers        = {}
pc_relative_encodings_preserved    = 235,530
```

编译记录 948 份。构建目录名沿用上游通用目标 `DEVELOPMENT_ARM64_BCM2837`，产物是 `mach.development.bcm2837`，**不是** 树莓派板级配置，属正常命名。

---

## 8. 当前两个阻塞点

### A. 引导层：payload FAT 不可见（首要）

**现象**：菜单能起，但显示 `no boot entry found`，`drivers 0 loaded / 0 failed kits 0 acpi 0`。

**已排除**：kernel 字段、payload 内容、FAT 结构、菜单 UI、缩放、输入。

**待验证方案**：`BootRamDisk.c` 从固件 FDT 的 `/chosen` 取 initrd 范围，注册只读 BlockIo。

**如果失败**（FDT 里没有 initrd，或配置表不存在），备选：

1. 走 Mu-Silicium 固件卷路线：`unixnu bootimg --fd <fv> --ramdisk payload.img --dtb ...`，由自带 `UniXNURamDiskDxe` 接管（工作量大，但和上游参考端口一致）。
2. 让 BDS 支持从 boot.img ramdisk 启动（改 GBL/BDS 配置或换 BDS）。
3. 把 payload 直接嵌进 `UniXNU.efi` 的资源段（自包含镜像，绕开卷发现问题）。

### B. 内核层：prelink 资格未通过（次要，但会挡住真正进系统）

四个 `false` + `early_security_initializers = {}`。上个会话的判断是“参考端口（NX769J）同样为 false，不影响先把 payload 链路打通”，但没有实证。真正加载 `kernel.macho` 之前，至少要确认：

- `DarwinBoot` 是否校验 `loadable`；
- `early_security_init` 地址缺失会不会在 `machine_startup` 阶段 panic；
- 是否需要在 `patches/xnu/` 里补 AMFI / early-security 的初始化记录。

---

## 9. 下一步任务清单（按顺序）

### 第 1 步：把 BootRamDisk 接进去（30–60 分钟）

1. 读 `work/UniXNU/package/UniXNUPkg/Library/UniXNULib/BootRamDisk.c`（194 行，结尾完整，已确认无截断）。
2. 在 `Include/Internal.h` 增加原型，例如：
   ```c
   EFI_STATUS
   EFIAPI
   UniXNUInstallBootRamDisk (
     VOID
     );
   ```
3. 在 `Application/UniXNU/Main.c`（或等价入口）里，**在文件系统枚举 / CachedFileSystem 连接之前**调用它。
4. 在 `UniXNUPkg.dsc` 的 `[Sources]` 或应用 INF 里加入该文件（当前全仓 grep 无引用，说明还没接）。
5. 重编 `UniXNU.efi`（命令见 6.2），确认大小仍在 100 KB 左右。
6. 重打 boot 镜像（kernel=UniXNU.efi，ramdisk=payload.img，header v0，page 4096，base 0x10000000，kernel_offset 0x8000，tags_offset 0x100）。
7. `fastboot boot`，观察菜单是否出现 `OPPO Pad mini - Darwin XNU` 条目。

**判定标准**：菜单出现 1 个 xnu 条目 + 3 个 action 条目，`kits 0` 但不再是 `no boot entry found`。

### 第 2 步：首次尝试引导 XNU

- 选中条目后，用串口/屏幕 panic 信息定位。
- `board.toml` 已设 `panic_screen = true`、`kernel_args = ["-v", "serial=3"]`。
- 如果是 green bar / 黑屏，按 UniXNU 文档的 green-bar 诊断走。

### 第 3 步：补 `porting.toml`

当前还是模板。至少填 `[device]`（name/soc/os_profile/summary）和 configuration/firmware/cpu/memory 四个 area 的实际输入与证据。

### 第 4 步：提交

- 设备仓先 `git add -A && git commit`（现在零 commit）。
- 主仓的 4 改 2 增也要提交，信息写清楚原因。

---

## 10. 常用命令 / 状态检查

```powershell
# 设备在哪种模式
adb devices -l
fastboot devices

# 回 TWRP（如果需要）
adb reboot recovery

# 进 bootloader
adb reboot bootloader

# 内存启动候选镜像（不写分区）
fastboot boot .\work\opd2515-xnu-payload-fastboot.img

# 取内核产物哈希
Get-FileHash .\outputs\opd2515-build\kernel\kernel.macho -Algorithm SHA256

# 看设备采集
Get-Content .\work\device-capture\partitions.txt
```

当前实测：`fastboot devices` 能看到一台设备，序列号显示 `????????????`（驱动未上报序列号，属正常）；`adb devices` 为空。

---

## 11. 已知坑

1. **git dubious ownership**：在沙箱身份下 `git -C ...` 会报 owner 不匹配。用
   `git -c safe.directory=<abs path> -C <abs path> ...`，不要写全局配置。
2. **WSL 在受限 shell 里 E_ACCESSDENIED**：`wsl.exe` 需要真实用户会话；沙箱内调用会失败。构建要在正常 PowerShell 里跑。
3. **417 MB 日志**：`kernel-bootstrap.log` 不要用编辑器打开，用 `Select-String` / `Get-Content -Tail`。
4. **CRLF**：`devicetree.py` 工作区是 CRLF，git 会提示将被换成 LF；提交前留意。
5. **模型 400 错误**：之前两个 OPPO 会话不是工程问题，是 `gpt-5.6-sol` 与 Key 出口不匹配。换模型或改 Key 出口即可。
6. **boot 镜像的 kernel 字段不是 Linux kernel**：GBL/BDS 把它当 EFI 应用执行；不要用常规 Android 思维去解包。
7. **payload 卷必须整卷可见**：只给 `unixnu.toml` 不够，FAT 驱动要能枚举根目录和 `PAYLOADS/`。

---

## 12. 参考端口与资料

- `work/ref-UniXNU-nx769j-ios165/` — 最接近的 iOS 16.5 端口（同代 XNU 8796）
- `work/ref-UniXNU-sm8550-common/` — 共用 SoC 层写法
- `work/ref-UniXNU-star-ios16/`、`ref-UniXNU-ace6/`、`ref-UniXNU-fuxi-ios16/`、`ref-UniXNU-sheng/`
- `work/ref-xnu-8796.121.2/` — 上游 XNU 参考
- 文档：`https://unixnu.com/porting/`、`/porting/uefi-firmware`、`/guide/debugging#green-bar`
- 设备仓 `README.md` 里有本地构建与启动诊断的入口说明

---

## 13. 一句话交接

> 编译链、payload、EFI 菜单都已就绪；只差“让 UniXNU 看见那个 208 MiB 的 FAT 卷”。
> 先接 `BootRamDisk.c`（读固件 FDT 的 `/chosen`），不行再上 Mu-Silicium 固件卷。
> 全程只 `fastboot boot`，不写任何分区。

---

## 14. 2026-11-09 04:25 最新进展（BootRamDisk 已接线 + BDS 行为已证实）

### 14.1 这次做了什么

1. `BootRamDisk.c` 已正式接进 UniXNU 包：
   - `Library/UniXNULib/Internal.h`：新增 `UniXNUInstallBootRamDisk()` / `UniXNUGetBootRamDiskStatus()` 原型。
   - `Library/UniXNULib/Main.c`：在 `UniXNUConnectAll()` 之前调用，保证 FAT 驱动能绑定到新块设备。
   - `Library/UniXNULib/UniXNULib.inf`：`[Sources]` 加入 `BootRamDisk.c`。
   - `Library/UniXNULib/Menu.c`：把定位结果画到菜单第 0 行，无串口也能看到原因。
2. `BootRamDisk.c` 现在有两条定位路径：
   - 第一条：固件 FDT 的 `/chosen` → `linux,initrd-start/end`（原计划）。
   - 第二条（新增）：扫描 UEFI 内存里的 `fastboot boot` 镜像缓冲，按 Android boot header 找到 ramdisk 段。
     依据：GBL 的 `CmdBoot` 在 `LoadImage` 前只 `FastbootUsbDeviceStop()`，不会释放 `mDataBuffer`，整张 boot.img 仍在内存里。
3. 建立 Windows 原生构建链（WSL 在当前 Codex 沙箱被 `E_ACCESSDENIED` 挡住）：
   - VS2022 BuildTools（`vcvars64.bat`）+ LLVM clang/lld + GnuWin32 GNU make + Codex 内置 Python。
   - EDK2 BaseTools 的 Win64 版本已编好（`work/uni-mu-basecore/BaseTools/Bin/Win64/`），与 Linux 的 ELF 版共存。
   - 新增 `tools/TrimLauncher.c`，解决 Windows GNU make 无法执行 `Trim.bat` 的问题。
   - 构建目录独立：`work/uni-build-win/`，不碰 WSL 的 `work/uni-build/`。

### 14.2 一键命令（推荐）

```powershell
cd C:\Users\27699\Documents\Codex\2026-11-09\unixnu-oppo-pad-mini-opd2515-12

.\build-efi-win.cmd          # 编 EFI + 重打 boot 镜像（约 20 秒）
.\build-efi-win.cmd -boot    # 再执行 fastboot boot（只内存启动）
```

脚本会：检查 BaseTools / Trim → `build.py` 编 `UniXNU.efi` → 用 `work/opd2515-payload.img` 重打 boot 镜像 → 输出路径与大小。
日志：`outputs/opd2515-build/logs/efi-win-build.log`、`basetools-win.log`。

WSL 路径（`build-opd2515.cmd -Stage kernel`）仍是内核构建入口；本次只改 EFI/引导层，没有重编内核。

### 14.3 关键证据：BDS 会丢弃 ramdisk

设备上实际运行的 `BDS.efi`（`D:\IDM Download\oppo_pad_mini_gbl_root_canoe\BDS.efi`，290,816 B）字符串检查：

| 字符串 | 是否存在 |
|---|---|
| `CmdBoot` | 是 |
| `Booting EFI image` | 是 |
| `No EFI image found` | 是 |
| `linux,initrd-start` | **否** |

对应源码 `work/gbl_root_canoe/submodules/uefi/edk2/QcomModulePkg/Library/FastbootLib/FastbootCmds.c` 的 `CmdBoot`：

- 只检查 `kernel` 字段是不是 PE（`MZ`），是就 `LoadImage(EfiData, EfiSize)` + `StartImage`；
- 完全不解析 `ramdisk` 字段，也不调用 `AndroidBootImgUpdateFdt`。

结论：**第 8.A 节原先设想的“FDT /chosen 里有 initrd”在该 BDS 上不成立**。菜单里应看到
`ramdisk: not found in FDT or memory` 或 `ramdisk: … from boot.img buffer`。

### 14.4 产物（本轮）

| 产物 | 大小 | SHA-256 |
|---|---|---|
| `work/uni-build-win/Build/UniXNU/DEBUG_CLANGPDB/AARCH64/UniXNU.efi` | 97,280 B | `11D53055505E77F20EF60D2D46A3A25A95D344820E539A2729EE16AEBF96C1B1` |
| `work/opd2515-xnu-payload-bootramdisk-fastboot.img` | 218,206,208 B | `7184B69569F1B13D80D94ABBEEAF4B1CBA42917347739A51AB8C1A75CACE9295` |
| `work/opd2515-payload.img`（从旧镜像抽出的 FAT 卷） | 218,103,808 B | — |

`UniXNU.efi` 为 PE32+ / machine `0xAA64`，已确认链接进新增的 ramdisk 字符串。

### 14.5 实机状态与下一步

- 截至 04:25，`pnputil /enum-devices /class USB` 里所有 Android/OPPO 相关设备均为 **Disconnected**，`fastboot devices` 为空。
  因此本轮**没有执行** `fastboot boot`，还没有实机结果。
- 设备重新插上并进入 fastboot 后，直接跑：

```powershell
.\build-efi-win.cmd -boot
```

预期菜单底部多一行：

- `ramdisk: 208 MiB from boot.img buffer, first eb3c` → 内存扫描命中，payload 应可见，条目出现；
- `ramdisk: not found in FDT or memory` → 内存缓冲被覆盖或 BDS 走了别的路径，转 8.A 备选。

### 14.6 8.A 备选路径的当前判断

| 备选 | 状态 | 备注 |
|---|---|---|
| 1. Mu-Silicium 固件卷 + `UniXNURamDiskDxe` | 未启动 | 工作量大；需要 BootShim 路径，和当前 `CmdBoot` 直接跳 EFI 的方式不同。 |
| 2. 改 GBL/BDS 支持 boot.img ramdisk | **不可行** | 需要写 `efisp`/BDS 分区，违反红线。 |
| 3. payload 嵌进 `UniXNU.efi` 镜像 | 备选 | 若 14.5 的内存扫描失败，再做：把 FAT 卷作为 PE 段或用 `.incbin` 附加，`LoadImage` 后自取。 |

### 14.7 未提交改动（本轮新增）

- 主仓 `work/UniXNU`：`BootRamDisk.c`（新）、`Internal.h`、`Main.c`、`Menu.c`、`UniXNULib.inf`。
- 设备仓 `work/UniXNU-opd2515` 未改动。
- 工作区新增：`build-efi-win.cmd`、`tools/TrimLauncher.c`、`tools/extract-payload.py`、`work/tools/pack-bootimg.py`、`work/uni-build-win/`。


## 15. 持久日志接入 userdata（2026-11-09 06:xx）

### 15.1 结论

支持。走 UEFI 阶段直接写 userdata 分区末尾 4 MiB，进 REC 用 dd 读裸块即可，不依赖内核、不依赖解密。

### 15.2 实现

- 新增 package/UniXNUPkg/Library/UniXNULib/BootLog.c，已接入 UniXNULib.inf 与 Internal.h。
- 通过 EFI_PARTITION_INFO_PROTOCOL 找 GPT 分区名 userdata，取 EFI_BLOCK_IO_PROTOCOL。
- 窗口 = 分区最后 4 MiB：4 KiB 头（magic UNIXNULG）+ 128 KiB 文本，sequence 递增重写。
- 安装点：UniXNUInstallBootLog() 在 UniXNURun 里调用两次 —— ramdisk 扫描前一次（存储已被 BDS 连上时生效），UniXNUConnectAll() 后一次重试。
- 落盘点：安装后、config 载入后、菜单出现后（倒计时开始前）、选中条目后、DT 准备好后、跳 XNU/StartImage 前。
- 早期行先进 4 KiB 预缓冲，安装成功后并入，UniXNU starting 不会丢。
- 菜单第 1 行显示 log: userdata @0x... / log: no writable userdata / log: write failed。

### 15.3 读取

进 TWRP/REC（adb 可用）后，在仓库根目录跑：

    read-log.cmd

它 push tools/read-log-device.sh，按 blockdev --getsize64 算偏移，dd 最后 4 MiB 到 /tmp，pull 回 outputs/opd2515-build/logs/，再由 tools/decode-boot-log.ps1 解出 .txt 并打印。

手工等价命令：

    P=/dev/block/by-name/userdata
    S=$(blockdev --getsize64 $P)
    dd if=$P of=/tmp/unixnu-log.bin bs=1048576 skip=$(( S/1048576 - 4 )) count=4

### 15.4 边界

- 只覆盖 UEFI 阶段。跳进 XNU 后 boot services 结束，EFI 无法再写；XNU 内 panic 需要内核侧 writer（参考 work/ref-UniXNU-sheng/package/BootLog.c）。
- 若崩溃发生在 BDS LoadImage 之前，本方案拿不到任何东西。
- 写分区末尾会破坏 userdata 文件系统尾部；用户已清空并备份，可接受。以后要回 Android 需重新 format userdata。
- 红线未变：只用 fastboot boot，不 flash 任何分区。

### 15.5 本轮产物

| 产物 | 大小 | SHA-256 |
|---|---|---|
| UniXNU.efi（含 BootLog） | 100,864 B | 05187307EC2CF2078DE75659D39DE23D331DCAFF8396BF0241137C926C828AD0 |
| opd2515-xnu-payload-bootramdisk-fastboot.img | 218,210,304 B | C73554FA46168048293F8AD5FFF5D80350F6ADB639D2B7EF2982DF580AF39C8E |

### 15.6 实机

- 06:0x fastboot boot 成功（Sending/Booting OKAY，4.6 s），随后黑屏，设备不重新枚举（fastboot/adb 均为空），与上一轮一致。
- 待办：强制重启进 REC，跑 read-log.cmd，看日志停在 menu: shown / boot ramdisk / xnu: handoff 哪一步。

### 15.7 首次实测结果与修正（06:4x）

- REC 里 `adb` 可用，设备自报 `macan` / `OnePlus_15R`，实际系统指纹是 `oplus/ossi/ossi:16`，按 ossi 机型判断就是这台平板（OrangeFox 用了 macan 的壳）。
- userdata = 491,334,463,488 B（`/dev/block/sda15`），日志窗口应在偏移 491,330,207,744。
- **读回 4 MiB 全是 0，没有 UNIXNULG 头**。说明 UniXNU 在第一次 UniXNULogFlush() 之前就挂了。
- 结合上一轮“只加 BootRamDisk 也黑屏”，最可能是卡在 BootRamDisk 的 UEFI 内存扫描，或更早的 BDS LoadImage。

已修正两个读取端 bug：

1. Android 的 sh 是 32 位算术，491 GB 分区上 `S/1048576-4` 溢出成 1625，读到 1.7 GB 处。偏移改由主机 PowerShell 计算后传给 dd。
2. `adb wait-for-device` 只认 Android 的 device 状态，REC 永远等不到；read-log.cmd 改成直接 `adb devices`，失败由 push 报错。

下一步（明天）：

- 在 UniXNURun 最前面画一块纯色/文字，确认 EFI 是否真的跑起来（区分 BDS 没跳进来 vs 我们自己崩）。
- 把 `UniXNUConnectAll()` 提到 `UniXNUInstallBootRamDisk()` 之前，装好日志并 flush 后再做 ramdisk 扫描，最后再 ConnectAll 一次让 FAT 绑定新 ramdisk。
- 若 `EFI_PARTITION_INFO_PROTOCOL` 不存在，加 GPT 直读兜底：拿整盘 BlockIo（`Media->LogicalPartition == FALSE` 且容量最大），读 LBA1 GPT 头，扫分区项找 `userdata`。
- 先用 `work/opd2515-newmenu-nopayload-fastboot.img` 做对照，确认新 EFI 本身还能出菜单。

## 16. 接手文档（2026-11-09 07:00）

当前状态的**唯一入口**请看 `docs/HANDOFF-CURRENT.md`（也复制到了 `outputs/OPD2515-接手文档-2026-11-09.md`）。
本文保留为历史过程记录，不再作为“当前状态”的依据。

## 17. S1 屏幕打点接手（2026-11-09，实机颜色反馈待补）

- 已完整阅读 HANDOFF-CURRENT.md；严格从第 8 节 S1 开始。未进行 S2/S3/S4/S5/S6 改动。
- 本轮仅修改 work/UniXNU/package/UniXNUPkg/Library/UniXNULib/Main.c，保留此前未提交改动。新增 UniXNUScreenCheckpoint，通过现有 GOP 的 EfiBltVideoFill 在左上角绘制最多 512x512 色块，成功绘制后停 1 秒；不调用 UI、日志或存储，也不设置显示模式。
- 三处打点：UniXNURun 第一条执行语句品红（早于 watchdog/LogInit）；InstallBootRamDisk 前黄色；调用返回后绿色。存储连接顺序、ramdisk 扫描和 payload 均未修改。
- 主机验收：build-efi-win.cmd 成功；Main.c 的 git diff --check 通过；独立解析确认 ARM64 PE、Android v0 header/page、镜像内 EFI 与构建产物一致、ramdisk 与原 payload 字节一致。
- EFI：101376 B，SHA256 411A253427C1895595CB181B3D6F121180D3E63C187C792EE6D13C1351916185。
- work/opd2515-xnu-payload-bootramdisk-fastboot.img：218210304 B，SHA256 8ADB9B964F90139A231D07FA159628E9F57FD846DF1CF3DD8485A9F3BEF10FC2。
- REC 身份：adb 42d72758；指纹 oplus/ossi/ossi:16/BP2A.250605.015/1785854446088:user/release-keys；device=macan；userdata=491334463488 B；DT model=Qualcomm Technologies, Inc. Alor MTP,ivy。fb0/modes 不存在，改读 /sys/class/drm/card0-DSI-1/modes，得到 1680x2520，60/90/120/144 Hz，status=connected。
- 从同一 adb 设备执行 reboot bootloader，本轮 fastboot 序列号为 42d72758（并非历史记录的全零），已完成同一连接的交叉确认。
- 执行 fastboot -s 42d72758 boot work/opd2515-xnu-payload-bootramdisk-fastboot.img：Sending OKAY 4.487s；Booting OKAY 0.175s；总计 4.759s。未执行 flash、格式化或引导分区写入。镜像保留原有已获授权的 userdata 尾部日志逻辑，是否实际写成功尚未验证。
- S1 状态：主机构建和传输通过，等待用户反馈肉眼颜色序列，不能把 Booting OKAY 当作 EFI 执行证明。S1 尚未验收，不进入 S2。
- 解释边界：未见任何颜色也可能是 GOP 未就绪或 Blt 失败，不能单独证明 BDS 未跳转；黄色未变绿定位在调用区间（也可能长时间扫描），尚不能单独断言异常；绿色只能证明调用返回，不能证明发现 ramdisk。历史全零日志仅证明未读到有效落盘记录，不能独立确定崩溃点。

### 17.1 S1 首次实机反馈及引导模式纠正（2026-11-09）

- 用户原话：“卡在ABL了，显示已进入fast boot，长按电源键6~10秒或重装电池退出”。未报告 S1 颜色序列，S1 未通过。
- 随后只读检查：fastboot devices 仍为 42d72758；getvar product=canoe；is-userspace=no；version-bootloader 为空；adb 无设备。不是此前“启动后 adb/fastboot 均消失”的表现。
- 本地 work/gbl_root_canoe/README_zh.md 第 4 节说明：开机小白字时按音量减进入 Superfastboot/BDS；reboot bootloader 进入官方 Fastboot。
- 纠正第 17 节操作判断：REC 身份已确认，但同一硬件序列号并不证明进入了预期 BDS。此前 adb reboot bootloader 后直接发送镜像，没有确认 BDS 环境，是本轮流程失误。Sending/Booting OKAY 不能证明 EFI 已执行，本轮不能据此支持 BootRamDisk 崩溃假设。
- 下一步：用户手动重启进入已安装的 BDS/Superfastboot，核对环境后重跑同一 S1 镜像。没有改动 S2 或扫描逻辑，没有执行 flash 或安装/修改任何 ABL/BDS 工具。

### 17.2 从已确认的 BDS 重跑 S1（2026-11-09）

- 用户确认“进入BDS的fastboot了”。主机枚举为 0000000000000000，与历史 BDS 一致；product=canoe；version-bootloader 返回 GetVar Variable Not found（此前 ABL 返回空值）。product 本身不能区分两种环境。
- 执行 fastboot -s 0000000000000000 boot work/opd2515-xnu-payload-bootramdisk-fastboot.img，使用第 17 节同一 S1 镜像。Sending OKAY 4.485s，Booting OKAY 0.000s，总计 4.574s。
- 等待用户反馈此次颜色序列和最终画面；S1 尚未验收，不推进 S2。没有执行 flash。

### 17.3 S1 实测定位与 S2 首次启动（2026-11-09）

- S1 用户原话：“粉色到黄色，然后黑屏”。入口品红和调用前黄色已观察到，S1 达到可见定位目的；没有观察到调用后绿色。
- 已证实新 EFI 进入 UniXNURun 并到达 InstallBootRamDisk 调用前，排除“此次 BDS 根本没执行新 EFI”。结果支持调用附近失效的假设，但未证明一定是内存扫描异常，也不能排除绿色绘制失败。
- 按第 8 节进入 S2：Main.c 在 InstallBootRamDisk 前先 ConnectAll、InstallBootLog、记录 S2 标记并 Flush；保留 ramdisk 返回后第二次 ConnectAll/日志重试及三色打点。未修改 BootRamDisk 扫描范围，未进入 S3/S4/S5/S6。
- build-efi-win.cmd 和 Main.c diff --check 通过。EFI 101376 B，SHA256 647B8D9951DC141954568DA8E04C1309E9BBF4638FB36B0242F7E54E01617093；boot 镜像 218210304 B，SHA256 C5EE53CC5B008627CFB0D74684748FB4A135E30DBF6B4B04553C306C2608ACBB。通用产物路径现为 S2 版本。
- 用户确认重入 BDS，枚举 0000000000000000。fastboot boot S2：Sending OKAY 4.486s，Booting OKAY 0.000s，总计 4.565s。没有 flash。
- S2 验收待完成：等待颜色/菜单反馈及 REC 日志，须出现 starting、boot log: userdata，且菜单发现 xnu 条目才算完整通过。S2 日志中的 storage connected 仅表示 ConnectAll 返回，不保证内部所有 ConnectController 成功。
- 读取端新发现：491334463488 % 1048576 = 61440。原 read-log.cmd 用 floor(size/1MiB)-4，会比真实末尾 4MiB 起点早读 60KiB；真实起点为 491330269184（size-4194304），交接文档原记 491330207744 是取整后的错误值。本轮应按精确 4096 字节块偏移读取（skip=119953679，count=1024），并验证实际分区大小；此前“全零”的证据需结合原始内容及该偏移问题重新审视。

### 17.4 S2 屏幕反馈，等待 REC 日志（2026-11-09）

- 用户反馈仍为粉色到黄色，然后黑屏；OLED 是否有背光无法判断。这不影响颜色证据，未观察到绿色或菜单。
- 黄色在提前 ConnectAll/InstallBootLog/Flush 之后，说明这些调用已返回；不能据此认定存储连接或写入成功。S2 完整验收尚未通过。
- adb/fastboot 当前均未枚举到设备，已请用户进入 REC 读取日志。未推进 S3-S6。
- 修正 read-log.cmd 和 tools/read-log-device.sh 的读取起点：主机按 (size-4194304)/4096 精确算 skip，dd 使用 bs=4096 count=1024；拒绝过小或非 4096 字节对齐的分区大小。该变更只影响读取端，无设备分区写入。待 REC 上实测。

### 17.5 S2 读回成功，进入 S4 对照（2026-11-09）

- 设备曾短暂枚举为正常 Android（OPD2515，bootmode=normal），随后用户自行进入 REC。未发送额外 reboot 命令。回 REC 后序列号 42d72758、userdata 大小仍为 491334463488 B。
- 修正后的 read-log.cmd 实测读取精确末尾 4MiB 成功：bs=4096 skip=119953679 count=1024。有效 UNIXNULG：version=1，header=4096，text=224，sequence=1，partition bytes=491334463488，region offset=0x726590F000。
- 日志原文：
    UNIXNU: UniXNU 0.1.0 starting as application, firmware Qualcomm Technologies, Inc. rev 0x60260721
    UNIXNU: boot log: userdata 468573 MiB, window at 0x726590F000
    UNIXNU: S2: storage connected; entering boot ramdisk install
- 原始日志保存在 outputs/opd2515-build/logs/unixnu-log-周一022611-144734.bin/.txt（旧脚本日期截取受区域设置影响，文件名不作为日期证据）。
- 结论：S2 提前落盘子项通过；菜单和 xnu 条目未出现，S2 整体验收仍未通过。S3 前提不成立（userdata 已可写），跳过 GPT 兜底。日志未证明进入扫描的具体分支，需继续按 S4 做无 payload 对照。
- S4 使用本轮当前 EFI（SHA256 647B8D9951DC141954568DA8E04C1309E9BBF4638FB36B0242F7E54E01617093）打包 work/opd2515-s4-current-nopayload-fastboot.img，ramdisk=0；尚未实机启动。

### 17.6 S4 无 payload 对照已内存启动（2026-11-09）

- 用户确认进入 BDS；fastboot devices 枚举 0000000000000000。
- 镜像 work/opd2515-s4-current-nopayload-fastboot.img，106496 B，SHA256 22612C7A6EE1E92C384CCED47338C7DA309F50F5FC464BE2D3FE3DEBEE1678B2；kernel 为当前 S2 EFI，ramdisk=0。
- 执行 fastboot -s 0000000000000000 boot work/opd2515-s4-current-nopayload-fastboot.img：Sending 104 KB OKAY 0.003s，Booting OKAY 0.000s，总计 0.005s。未执行 flash。
- 等待用户反馈颜色序列、菜单及 ramdisk/log 状态行；S4 尚未验收，不进入 S5。

### 17.7 S4 菜单出现（2026-11-09）

- 用户原话：“粉色到黄色到绿色，然后进入 UNIX nu 的菜单了”。
- 已确认当前 S2 EFI 在无 payload 镜像中可执行完 InstallBootRamDisk 并显示菜单。S4 的菜单显示子项通过；ramdisk/log 两行具体内容待用户提供，暂不标记完整验收。
- 与带 payload 的黄色后黑屏形成对照，说明故障与带 payload 路径有关；目前不能区分扫描命中后的校验、注册 BlockIo、其他内存访问或时序影响，不把异常直接定性为某行 CompareMem。
- 下一步先补齐 S4 状态行证据，再按 S5 重跑带 payload 并读 REC 日志。S6 尚未修改。
- 补充静态检查：FindBootImageRamDisk 在 BootImageLayout 命中分支中先 FreePool(Map)，随后使用 Desc->PhysicalStart；Desc 指向已释放 Map 内部，存在明确的释放后访问缺陷。尚未实机证明它就是黑屏根因，待 S6 一并修正，当前未改动扫描代码。另当前实现只检查每个描述符的起始地址，并非逐页遍历整个区域；交接中的“全内存扫描”描述应据此细化。

### 17.8 S4 照片证据与状态行修正（2026-11-09）

- 用户照片已留存 work/device-capture/s4-menu-before-status-fix.jpg。可见 UniXNU 0.1.0、built-in configuration、四个内置动作、log: userdata @0x726590F000、no boot entry found；没有可见 ramdisk 行。
- 静态确认 Menu.c 的 DrawCountdown 在空闲状态把第 0 行替换为 Select an entry，覆盖了之前绘制的 ramdisk 状态。不能把照片解释为 ramdisk 未执行。
- 最小修复：无倒计时时 DrawCountdown 优先显示非空 ramdisk 状态；有倒计时仍保留原启动提示。未改 ramdisk 扫描、存储、启动策略。
- 构建成功，Menu.c diff --check 通过。重新打包 work/opd2515-s4-status-nopayload-fastboot.img（106496 B，SHA256 086A00E2B121B8AF4B820D3B307D9B89D7BF6B2DAE33AE0F4746234ACF43D3DA）。通用 payload 镜像也已由构建脚本更新为同一新 EFI。
- 初次 USB 枚举 ???????????? 且 getvar 返回 no link；用户重新进入后恢复 0000000000000000。fastboot boot 修正后的 S4 镜像成功：Sending 0.003s、Booting 0.000s、总计 0.005s。
- 等待两条状态行的实机反馈，补齐 S4 验收后继续 S5；未执行 flash。

### 17.9 S4 修正版照片处于倒计时（2026-11-09）

- 第二张照片留存 work/device-capture/s4-menu-countdown-status-fix.jpg，显示 Booting Return to firmware in 7 s、log: userdata @0x726590F000、no boot entry found。
- 修复仅在 RemainingMs<0 时保留 ramdisk 行；照片拍摄时倒计时仍有效，因此不能从这张照片确认 ramdisk 状态。未误报 S4 完整通过。
- 已检查输入代码：首次方向键会停止倒计时，音量方向键用于选择；下一轮绘制会显示 ramdisk 状态。请用户短按音量键后读取，避免不必要的重新构建。若已自动 Return to firmware，则重新进入 BDS 后可重跑现有 S4 修正版。
- 当前 fastboot 枚举为 ????????????，adb 为空；未在失效连接上发送启动命令。

### 17.10 S4 完整验收通过（2026-11-09）

- 用户说明上一张照片发错，补发正确照片，已保存 work/device-capture/s4-menu-verified.jpg。此前倒计时照片仅保留历史，不作为当前状态证据。
- 正确照片清晰显示：ramdisk: not found in FDT or memory；log: userdata @0x726590F000；no boot entry found；UniXNU 菜单及内置动作正常。
- 结合此前品红→黄→绿，S4 无 payload 对照的菜单和两条状态行验收完整通过。无 payload 未找到 ramdisk 为预期结果。
- 下一步 S5：使用当前同一 EFI 的带 payload 镜像内存启动，再回 REC 精确读取日志；尚未修改 S6 扫描代码。

### 17.11 S5 带 payload 复测已启动（2026-11-09）

- S4 完整通过后，用户确认重入 BDS；枚举 0000000000000000。
- 镜像 work/opd2515-xnu-payload-bootramdisk-fastboot.img，SHA256 CD7B97D844B707790AB207A72BE5266D78E4B7945540330627A5FC7CDE7A45BC；使用与 S4 状态行修正版相同的 EFI，附带原 208 MiB payload。
- fastboot -s 0000000000000000 boot：Sending 213096 KB OKAY 4.487s，Booting OKAY 0.000s，总计 4.579s。未执行 flash。
- 等待颜色/菜单反馈，再进 REC 读取精确 userdata 尾部日志，以最后一条 UNIXNU 行定位。S5 尚未完成，S6 尚未改动。

### 17.12 S5 日志确认与 S6 实现（2026-11-09）

- S5 用户反馈品红→黄色→黑屏。REC 精确读回日志 version=1、sequence=14、text=224，末行仍为 S2: storage connected; entering boot ramdisk install；保存在 outputs/opd2515-build/logs/unixnu-log-周一022611-145611.bin/.txt。S5 复测和定位已完成，进入 S6。
- BootRamDisk.c：仅接受 EfiLoaderData/EfiBootServicesData、EFI_MEMORY_WB，排除 RP/runtime 属性，校验非零页对齐起点、长度移位和区间溢出；最多 64 候选、候选区域累计最多 2GiB，GetMemoryMap 最多 4 次尝试。仍只检查描述符起始地址，不新增逐页任意探测。
- 当前 OPD2515 诊断配置最小候选大小固定为 218210304 B，对应本轮整个 boot 镜像；后续更改 EFI/payload 大小时必须重新核对。独立解析已验证当前镜像大小相符、嵌入 EFI 与构建产物一致、payload 字节未变。
- 修正确定存在的释放后访问：命中时先从局部 Base 计算 Start/End，之后才 FreePool(Map)，不再访问释放后的 Desc。
- 增加 FDT、候选地址、layout 命中、协议安装和控制器连接前后的分段日志/flush。所有写入仍走已有 userdata 尾部授权窗口。
- 构建及 diff --check 通过。EFI 101888 B，SHA256 80B83845E3A17318226BA68B5F5487679791382AEB36CAE859EE01FC4715A453；boot 镜像 218210304 B，SHA256 867D0F5204BD5B8A4A4A50FD10C7B590CB1A7DD37181C7B64115064340367C2F。
- BDS 枚举 0000000000000000，fastboot boot S6：Sending OKAY 4.485s、Booting OKAY 0.000s、总计 4.565s。没有 flash。

### 17.13 S6 带 payload 菜单成功，XNU 条目返回 Unsupported（2026-11-09）

- 用户反馈品红→黄→绿并进入菜单；照片保存 work/device-capture/s6-payload-menu-unsupported.jpg。
- 照片可见 config: \EFI\UniXNU\unixnu.toml；OPPO Pad mini - Darwin XNU 条目（xnu）；ramdisk: 208 MiB from boot.img buffer, first 58EB；log: userdata @0x726590F000。
- 同时可见 'OPPO Pad mini - Darwin XNU' returned: Unsupported。只证明加载器尝试启动该条目后返回错误，不证明已进入 XNU。
- S6 菜单/xnu 子项通过，待 REC 读出 found boot image ramdisk 行完成日志子项。早期黑屏本轮未复现；由于本轮同时收紧过滤并修复释放后访问，尚不能把根因唯一归于其中一项。
- 下一步读取本轮日志，完成 S6 验收并定位 Unsupported，禁止格式化、flash 或新增未授权设备持久化写入。

### 17.14 S6 完整验收通过与当前阻塞结论（2026-11-09）

- REC 42d72758，userdata 491334463488 B，精确尾部读取成功。日志 version=1、sequence=30、text=1518，文件 outputs/opd2515-build/logs/unixnu-log-周一022611-145944.bin/.txt。
- 关键原文：
    UNIXNU: boot ramdisk: no valid firmware FDT: Not Found
    UNIXNU: S6: candidate 1 base 0xAA0000000 bytes 0x60000000 type 4
    UNIXNU: S6: boot image layout matched
    UNIXNU: boot ramdisk: found boot image ramdisk at 0xAA001A000-0xAAD01A000
    UNIXNU: boot ramdisk: initrd 0xAA001A000-0xAAD01A000, 218103808 bytes, first words 4D9058EB 344F4F54
    UNIXNU: S6: ramdisk controller connect returned
    UNIXNU: config: loaded \EFI\UniXNU\unixnu.toml
    UNIXNU: menu: shown 4 entries, default 0 'xnu', timeout 3000 ms, input yes, rotate 0 ms
    UNIXNU: xnu: no loader protocol installed; UniXNU does not provide one
    UNIXNU: menu: entry 0 returned Unsupported
- S6 要求的 found boot image ramdisk 日志和 xnu 菜单均已证实，完整通过。S2 的提前写日志与双 ConnectAll 后 payload 可发现两项也至此得到验证。
- 验收总表：S1 通过；S2 最终通过；S3 条件不成立、未实施；S4 通过；S5 已复现并读日志定位；S6 通过。仅完成这段 EFI/payload 排障，不代表 XNU/iOS 启动成功。
- 当前阻塞已确定：Boot.c 的 RunXnu 调用 LocateProtocol(gUniXNULoaderProtocolGuid) 失败，返回 EFI_UNSUPPORTED；尚未调用 Loader->Boot，没有 xnu: handoff。下一阶段需接入实现 UniXNULoader 协议的加载器并核对其配置与设备树输入，不能将此错误归因于 XNU 内核崩溃。
- 本轮 FDT 配置表查询为 Not Found，boot: dt 0 bytes at 0x0；这与先前“FDT 存在但无 initrd”的历史假设不同，应以本轮实测为准，后续加载器接入需单独处理。
- 当前设备在 REC；全程无 flash、无格式化、未执行留档 ABL 工具。固件阶段持久化写入仍限于已授权 userdata 尾部日志窗口。
- 保留限制：S6 是 OPD2515 当前镜像诊断配置，最小候选大小固定为 218210304 B，只检查合格描述符起始地址；未来改 payload/EFI 或更换固件需重新验证。黑屏根因未做单变量隔离，不声称唯一由释放后访问导致。

## 18. 接入 DarwinBoot 加载器（2026-11-09）

- 已确认 Unsupported 的直接原因：RunXnu 找不到 gUniXNULoaderProtocolGuid；当前 payload 未携带实现该协议的驱动。
- 从 drivers/DarwinBoot 使用 CLANGPDB/AARCH64 成功构建 DarwinBoot.efi，27136 B，SHA256 952B7636124D5454BABCBAFE6000D15E29A8588C1A2DA2D444E77BBEC73E5FDF。
- 新增 tools/install-payload-driver.py：以原 payload 为输入，幂等写入 EFI/UniXNU/Drivers/DarwinBoot.efi，并在 unixnu.toml 根配置加入唯一 [[driver]]（connect=false）；写后执行驱动字节和配置读回校验。工具只修改主机上的 payload 镜像，不触碰设备分区。
- build-efi-win.cmd 扩展为 5 步：BaseTools、Trim、DarwinBoot、UniXNU、注入 payload + 打包 boot image；-boot 仍只调用 fastboot boot。
- 板级源配置 work/UniXNU-opd2515/package/unixnu.toml 已加入同一 driver 配置，避免后续 payload 重建丢接线。
- 完整构建通过。payload 现含驱动，配置只有一份 [[driver]]；驱动回读、ARM64 PE、kernel/ADT/trustcache 保留均经独立检查。当前 boot 镜像 218210304 B，SHA256 7D29F469219E97EDD809630331C210868E74AD04FA96F6041B21CE9D48B0FC27；UniXNU.efi 仍为 101888 B，SHA256 80B83845E3A17318226BA68B5F5487679791382AEB36CAE859EE01FC4715A453。
- 下一步需要实机从 BDS 内存启动，验收驱动 started、xnu: handoff 及 DarwinBoot 后续输出；主机验证不能证明协议启动或 XNU 已运行。

### 18.1 DarwinBoot 路径式 LoadImage 被 Security2 拒绝（2026-11-09）

- S7 带 payload 实机启动后，菜单与 xnu 条目均出现，驱动配置被发现；屏幕原文为 config error: driver \EFI\UniXNU\Drivers\DarwinBoot.efi: load failed: Access Denied，drivers 0 loaded / 1 failed。证据照片：work/device-capture/darwinboot-driver-load-denied.jpg。
- 对照 work/uni-mu-basecore/MdeModulePkg/Core/Dxe/Image/Image.c 1310-1362，EFI_ACCESS_DENIED 只会由 gSecurity2->FileAuthentication() 返回。此次失败发生在 LoadImage 阶段，DarwinBoot 的入口尚未执行，因此不能归因于 DarwinBoot、loader protocol 或 XNU。
- UniXNU 官方 docs/drivers/uefi-drivers.md 规定 payload 驱动通过 [[driver]] 路径加载；当前 payload 配置和驱动字节均已按该流程就绪。由于 BDS 的文件路径策略拒绝了该路径，源码增加了 Access Denied 后的内存缓冲区重试：先用 UniXNUReadFile 读取同一配置路径，再以 SourceBuffer 和非空 NULL FilePath 调用 LoadImage。重试仍调用固件自己的 Security2，不关闭认证、不修改 BDS、不写引导分区。
- 主机完整构建通过。新 UniXNU.efi 102400 B，SHA256 579F5C017B122283DBAD2A41502B6EBE2066D295862DE329253C37D82779CA28；DarwinBoot.efi 27136 B，SHA256 952B7636124D5454BABCBAFE6000D15E29A8588C1A2DA2D444E77BBEC73E5FDF；boot 镜像 218210304 B，SHA256 2C4E70CC57D58696D8ACC28BCA30BA64FA00DCE99D651034A5710BEE2667702A。
- 主机回读 payload 通过：[[driver]] 仅一份，配置恰有一条 Drivers/DarwinBoot.efi，FAT 内驱动与构建产物逐字节一致；boot 头为 ANDROID!，kernel 102400 B，ramdisk 218103808 B。EFI 类型分别是 application 与 boot service driver。
- 2026-11-09 从 BDS 序列号 0000000000000000 发送新镜像时，两次均在 Sending 阶段返回 Write to device failed (no link)，没有执行 Boot OKAY，因此这次修正尚未得到实机结论。全程仅执行 fastboot boot，没有 flash、erase、format，也未修改持久分区。
- 下一次 S7 实机验收需观察 driver ...: path load failed ...; memory load ...、driver ...: started、drivers 1 loaded，以及 xnu: handoff 和 DarwinBoot 的 DARWINBOOT: 输出；若仍拒绝，进入 REC 读取本次日志后再决定是否改为直接静态并入。

### 18.2 DarwinBoot 已成功加载，`Compromised Data` 定位为 trust cache 文件格式（2026-11-09）

- S7 第二版实机内存启动成功，`fastboot boot` 返回 `Sending OKAY [4.487s]`、`Booting OKAY [0.000s]`。这证明前一版针对 `EFI_ACCESS_DENIED` 的“路径加载失败后改用私有池内存缓冲重试”修复有效：本版菜单状态为 `drivers 1 loaded / 0 failed`，DarwinBoot 已执行并安装 loader protocol，菜单中的 XNU 条目也正常出现。
- 选择 `OPPO Pad mini - Darwin XNU` 后返回 `Compromised Data`，没有进入 XNU handoff。菜单同时显示 `ramdisk: found ... 208 MiB`，因此本轮不能再归因于 ramdisk 查找、payload 发现、驱动加载或 ADT 缺失。实机证据照片：`work/device-capture/s7-darwinboot-compromised-data.jpg`。
- 直接原因已定位：payload 中的 `EFI/UniXNU/Payloads/kernel.macho.trustcache` 被直接放入了原始 Apple IM4P 文件（66,265 B，DER 头、`IM4P`/`trst`），而 DarwinBoot 的 `ValidTrustCaches()` 要求的是带模块计数和偏移表、模块版本为 2 的 DarwinBoot bundle。原文件前缀与外层结构不符合该函数要求，故返回 `EFI_COMPROMISED_DATA`。
- ADT 已排除为本轮直接原因：ADT 共 14,288 B，独立解析恰好到 EOF；`/chosen/memory-map/TrustCache` 占位符存在且为 16 字节零值，符合 DarwinBoot 在成功校验后回填地址和大小的要求。当前 XNU 条目没有 initrd，ADT 中没有 `RAMDisk` 占位符与这一现状一致。
- 已按 UniXNU 官方文档和源码要求运行 `scripts/bundle-ipsw-trust.py`，将原始静态 trust cache 无损转换为 DarwinBoot bundle。产物 `work/opd2515-static.trustcache.bundle` 为 66,248 B，单模块版本 2，2,759 条记录；SHA-256 为 `96F873DF1F5B6B39DBC15D23F8AC04585F7C8C7FCE687E80C0FF458951737EDB`。JSON 元数据在旁路生成，记录 `modified: false`。
- 新增 `tools/install-payload-trustcache.py`：在主机 payload 副本上验证 bundle 的模块数量、版本、边界、条目表，替换原 trust cache 后立即回读并再次验证；对已处理的 payload 可重复执行。`build-efi-win.cmd` 的打包步骤现依次调用官方转换脚本、驱动安装器、trust cache 安装器，再重打 boot image。
- 完整构建通过。构建脚本使用固定 runtime Python 调用官方转换脚本，使用带 `pyfatfs` 的系统 Python 执行两个 payload 安装器；只修改主机上的 `work/opd2515-payload.img` 和最终 boot image。
- 主机回读验收通过：`[[driver]]` 恰有一份；FAT 内 `DarwinBoot.efi` 与构建产物逐字节一致；FAT 内 trust cache 与 bundle 逐字节一致；bundle 为单模块 v2，哈希与记录顺序通过独立检查，解出的模块与原始 IM4P 内嵌 payload 逐字节一致；`kernel.macho` 与 `kernel.macho.adt` 均保留。boot 头为 `ANDROID!`、header v0、4096 B page，kernel 段与 `UniXNU.efi` 逐字节一致，ramdisk 段与 payload 逐字节一致。
- 本轮产物：`UniXNU.efi` 102,400 B，SHA-256 `579F5C017B122283DBAD2A41502B6EBE2066D295862DE329253C37D82779CA28`；`DarwinBoot.efi` 27,136 B，SHA-256 `952B7636124D5454BABCBAFE6000D15E29A8588C1A2DA2D444E77BBEC73E5FDF`；payload 218,103,808 B，SHA-256 `33374A9ABA47C411D1094FB50E02B5D39122B9D33A9D5B3A3F38A61C63C8A905`；boot image 218,210,304 B，SHA-256 `6112BC4C613F03CAA12EB4753E3358AB07240BB914260431CFA2C6C1AA992001`。
- 待实机 S8 验收：确认不再显示 `Compromised Data`，并记录 DarwinBoot 的第一个新结果；可能进入 256 MiB/6 GiB 内存窗口分配、GIC/XNU handoff、绿色顶栏，或出现另一个明确的 loader 错误。主机校验不能证明 XNU 已运行。
- 本轮仍只使用主机文件修改；设备侧下一步只允许从 BDS 执行 `fastboot boot work\opd2515-xnu-payload-bootramdisk-fastboot.img`。没有 flash、erase、format，没有修改任何分区。
- 2026-11-09 16:03:35 +08:00 首次尝试 S8 时，主机仍能枚举 fastboot 条目，但发送 218,210,304 B 镜像过程中返回 `Write to device failed (no link)`，未出现 `Booting OKAY`。这次失败发生在传输阶段，不能用于评价新 trust cache；设备侧没有执行启动，也没有任何分区写入。


### 18.3 S8 越过 `Compromised Data` 并进入 XNU 早期入口（2026-11-09）

- 修正后的 S8 镜像从 BDS 内存启动成功：`Sending OKAY [4.487s]`、`Booting OKAY [0.000s]`，总耗时 4.568 s。菜单正常显示 `drivers 1 loaded / 0 failed`、`kits 0`、`acpi 0`，选择 XNU 后不再返回 `Compromised Data`，确认 18.2 的 trust cache bundle 修复通过实机验收。
- DarwinBoot 实机画面明确显示：`inputs validated; exiting boot services` 与 `hand-off to the kernel`；随后显示内核 `va=0xFFFFFFF003D0000`、`pa=0x8C01D0000`、`args=0x8C45EC000`、视频 `base=0xFC800000`、`width=1680`、`height=2520`、`row=6720`、32 bpp，以及 `CurrentEL=1`、`SCTLR_EL1=0x30D01980`、`TCR_EL1=0x4B8003514`、`PARange 4`、`4 KiB granule supported`。这是 DarwinBoot 已退出启动服务并开始分支到 XNU 的直接证据。
- 实机照片 1：`work/device-capture/s8-darwinboot-xnu-handoff.jpg`，SHA-256 `46E73D13ECF40F43BC1F5C66BC07BA782A033CBDE95D881ADA08176B033384D4`。
- 实机照片 2：`work/device-capture/s8-post-handoff-unixnu-menu.jpg`，SHA-256 `5ECB83BC4C14871A30A10193C927F10A2E5D41498A98E448531D1113ED2146B4`。照片显示顶部同时存在绿色、蓝色、品红色三条，以及旧菜单画面和一个新的 `Booting OPPO Pad mini - Darwin XNU in 1 s` 倒计时。
- 按 UniXNU 官方 `docs/guide/debugging.md` 的 green-bar/color-bar 定义：绿色表示 DarwinBoot 已退出 boot services 并进入交接；其下蓝色表示内核入口已在 MMU 关闭状态下执行；品红表示 CPU 已到打开 MMU 前的位置。故本轮不仅进入 DarwinBoot handoff，而且 XNU 入口探针阶段 1、2 均实际执行。不能据绿色条单独判断后续故障。
- 主机独立检查确认当前 payload 的 `kernel.macho` 已包含阶段 1 蓝条和阶段 2 品红条补丁，并已把 `_panic` 分支接到 panic 屏幕；payload 中没有阶段 3 的定时复位分支。该检查与实机三色带相互印证，也说明后续菜单重现不是由本项目配置的 stage 3 定时复位产生。
- S8 照片只能确定已经到达品红检查点；第二张照片中新倒计时的出现时序、这是否由一次完整复位造成、以及复位后是否再次自动进入 XNU，仍需结合用户时序反馈和 REC 持久日志确认。当前不能宣称 XNU 已完成 MMU 初始化、已进入内核 C 启动路径或已启动 iOS。
- 官方文档给出的下一步是先记录最后的 `DARWINBOOT:` 行，并检查 panic 屏幕、蓝色/品红条、复位时序、串口和 payload 报告；当前板级配置已设 `panic_screen = true`，但无串口，所以下一轮诊断应基于本次日志判断是否需要启用 `entry_probe_reset_delay` 或其他 `reset_after` 单变量检查点。
- 本轮仍只执行 `fastboot boot`，没有 flash、erase、format，也没有修改任何设备分区。

### 18.4 源码成果已提交并推送到 UniXNU fork（2026-11-09）

- 当前 OPD2515 移植成果已整理为提交 `de8962a9bcf838bfc16b8571f43449663d094194`，标题为 `feat(opd2515): advance firmware boot to XNU handoff`，包含早期屏幕检查点、userdata 尾部持久日志、boot ramdisk 恢复、菜单状态、payload 驱动 Security2 拒绝后的内存缓冲重试、iOS 16.5 profile、ADT 生成修正和 XNU 构建记录保留。提交前 `git diff --check` 和改动 Python 文件的语法检查通过。
- 提交已变基到 UniXNU 上游 `main` 的 `8ec13bb1077502e53e8ba3b82c56842589b5c837`，对应子模块随后同步到仓库锁定版本，工作树保持干净。
- 直接向 `UniXNU/UniXNU` 推送被 GitHub 以 403 拒绝，当前账号 `Axiang-dev` 没有目标仓库写权限。未改写上游 `main`，也未强制推送。已创建 `Axiang-dev/UniXNU` fork，并把分支 `opd2515-oppopadmini-ui` 成功推送到同名远端；远端回读同样指向提交 `de8962a9bcf838bfc16b8571f43449663d094194`。
- 变基后重新完整构建通过，payload 内容回读校验通过：单一 `[[driver]]`、DarwinBoot 与构建产物一致、trust cache 为单模块 v2/2,759 条、kernel 与 ADT 保留、boot 头及 kernel/ramdisk 段逐字节匹配。
- 变基后最新主机产物：`UniXNU.efi` 102,400 B，SHA-256 `BD781B444EFBB55254622E3C47A113E2C066EC72993D5E5DF842F88A6F7CD4CF`；payload 218,103,808 B，SHA-256 `567330FF26814DDFFF14DB4812E11C9D3C7AE686C22A1FE3CD5A6E34744FE588`；boot image 218,210,304 B，SHA-256 `902C6D3FC978E6468A8C0A136A7C09FF24C22799E4E5C7E54347C0AA17AC3C2D`。DarwinBoot 与 trust cache 哈希不变。
- S8 实机证据来自变基前的同一修复版本；变基后的最新 EFI/boot image 已通过主机构建和结构校验，但尚未再次实机启动。后续设备测试仍只允许 `fastboot boot`。

## 19. 独立设备仓库与旧 fork 清理（2026-11-09）

### 19.1 公开独立仓

- 本仓库以 `Axiang-dev/UniXNU-opd2515` 发布，默认分支为 `main`。初始提交 `175fd0a9dfeb6aca606d2e9e20232966e89b584e` 的远端回读一致。
- GitHub 描述为 `UniXNU board port for the OPPO Pad mini (OPD2515, SM8845P / Alor)`，包含 `unixnu` topic，被识别为 Python 仓库。
- 初始推送触发并通过 `Verify repository`（run 42585943269）与 `Porting record`（run 42585943530）；`Package preflight` 是手动工作流。
- 本地 `scripts/verify.py`、13 区域 `porting.toml` 校验及上游 `8ec13bb1077502e53e8ba3b82c56842589b5c837` 上的补丁应用检查均通过。
- 没有提交平台 seed、Apple IPSW、内核、payload、boot image、厂商固件、token 或本机日志。

### 19.2 旧 fork 删除

- 用户明确确认删除先前的 `Axiang-dev/UniXNU` fork。删除前在 GitHub 页面核对仓库名，并在最终验证框输入 `Axiang-dev/UniXNU`。
- GitHub 返回删除成功；随后 API 回查旧地址为 HTTP 404。新仓 `Axiang-dev/UniXNU-opd2515` 保持公开并可访问。
- 本地旧的失效 remote 已移除；所用源码提交由 `patches/unixnu/` 固定并可直接应用到上述 UniXNU 上游提交。
