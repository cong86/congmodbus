# Cong Modbus Climate

用于 Home Assistant 的 Modbus 空调自定义组件。当前配置已经在格力水多联机、
Modbus TCP 网关以及 Home Assistant 2026.8.1 环境中验证。

## 功能

- 空调开机、关机
- 制冷、制热、除湿、送风和自动模式
- 目标温度设置与当前温度读取
- 风速控制
- 同一 Modbus Hub 共享 I/O 锁，避免并发读写冲突
- 通信失败后暂停轮询、退避重试和自动重连
- YAML 重载后的旧实例隔离与连接保护
- 自动生成轮询状态传感器和轮询控制开关

## 安装

### HACS 自定义仓库

1. 在 HACS 中打开“自定义仓库”。
2. 添加：`https://github.com/cong86/congmodbus`
3. 类型选择“集成”。
4. 下载最新 Release。
5. 复制并修改示例 Package，然后检查配置并重启 Home Assistant。

### 手动安装

将仓库中的：

```text
custom_components/congmodbus
```

复制到：

```text
/config/custom_components/congmodbus
```

## 配置

本组件依赖 Home Assistant 原生 `modbus` 集成。推荐使用 Package，把：

```text
examples/packages/congmodbus.yaml
```

复制到：

```text
/config/packages/congmodbus.yaml
```

然后在现有 `homeassistant:` 段中启用 Packages：

```yaml
homeassistant:
  packages: !include_dir_named packages
```

不要创建第二个 `homeassistant:` 段。

示例预置参数：

```text
网关：192.168.1.100:502
Hub：gree_bms
Slave：2
内机：10、20、30、40、50
```

如果现场网关 IP 不同，修改 Package 顶部的 `host`。

## HA 2026.8 Modbus 注意事项

HA 2026.8 的 YAML Modbus Hub 至少需要一个原生 Modbus 实体，否则 Hub 会被拒绝加载。
示例 Package 中的“格力Hub保活”传感器每 300 秒读取一次寄存器，是当前架构的兼容性
支撑项，不要删除。

## 示例寄存器

| 内机 | 开关 | 模式 | 目标温度 | 风速 | 当前温度 |
|---|---:|---:|---:|---:|---:|
| 10 | 327 | 328 | 329 | 330 | 341 |
| 20 | 577 | 578 | 579 | 580 | 591 |
| 30 | 827 | 828 | 829 | 830 | 841 |
| 40 | 1077 | 1078 | 1079 | 1080 | 1091 |
| 50 | 1327 | 1328 | 1329 | 1330 | 1341 |

这些地址是现场示例，不代表所有设备都使用相同寄存器。部署前请按照自己的设备文档调整。

## 升级

升级前备份：

```text
/config/custom_components/congmodbus
/config/packages/congmodbus.yaml
```

升级组件不会自动覆盖 Package。完成后执行 Home Assistant 配置检查，检查通过再重启 Core。

## 快速恢复

GitHub Release 附件提供 `congmodbus-recovery-v1.1.1.zip`，其中包含组件、Package、
安装检查脚本和回滚说明。恢复包中的现场地址应在安装前确认。

## 已知说明

- 这是自定义集成，Home Assistant 会显示“未经测试的自定义集成”提示，属于正常现象。
- 轮询状态传感器在已有实体注册表中可能带 `_2` 后缀；全新安装时可能不带后缀。
- `domain`、空调名称和 `unique_id` 生成规则保持不变，以兼容已有仪表盘和自动化。

## 问题反馈

请在 [GitHub Issues](https://github.com/cong86/congmodbus/issues) 提交问题，并附上：

- Home Assistant 版本
- CongModbus 版本
- 脱敏后的 Package 配置
- 相关 `congmodbus`、`gree_bms` 或 `pymodbus` 日志

