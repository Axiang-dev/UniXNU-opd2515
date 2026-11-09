# OPD2515 tools

这些工具只处理离线的 payload、boot image 和 REC 日志，不会执行任何分区写入。

| 文件 | 用途 |
|---|---|
| `install-payload-driver.py` | 把已构建的 DarwinBoot 安装到 FAT payload，并校验回读 |
| `install-payload-trustcache.py` | 安装并校验 DarwinBoot 兼容的 trust cache bundle |
| `extract-payload.py` | 从 Android boot image v0 抽取 payload/ramdisk |
| `pack-bootimg.py` | 打包 boot header v0 boot image；只用于之后手动 `fastboot boot` |
| `read-log-device.sh` | 在设备端按主机计算的块偏移读取 userdata 尾部 4 MiB |
| `decode-boot-log.ps1` | 解码 `.bin` 中的 `UNIXNULG` 头并导出文本 |
| `/read-log.cmd` | Windows 上通过 REC ADB 拉取并解码 UEFI 日志 |

安装 Python 依赖：

```text
python -m pip install -r requirements.txt
```

`read-log.cmd` 只读裸块，不挂载、不格式化 userdata。不要在 BDS fastboot 中运行
`flash` 命令。`pack-bootimg.py` 只生成文件，是否启动必须由人工单独执行
`fastboot boot <image>`。