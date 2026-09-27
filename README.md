# Cong Modbus Climate

用于 Home Assistant 的 Modbus 空调自定义组件。当前配置已经在格力水多联机、
Modbus TCP 网关以及 Home Assistant 2026.8.3 环境中验证。

## 功能

- 空调开机、关机
- 制冷、制热、除湿、送风和自动模式
- 目标温度设置与当前温度读取
- 风速控制
- 独立展示实际运行风速，并复用 Climate 的 4 秒专用风速读取
- 重启后恢复上次已知的风速初始值；有效现场读值到达后以实际速度为准
- 线控器物理改档后，Climate 在下一轮有效实际风速读值时同步更新
- 风速寄存器每 4 秒读取，其余空调属性保持 10 秒轮询
- 同一 Modbus Hub 共享 I/O 锁，避免并发读写冲突
- 通信失败后暂停轮询、退避重试和自动重连
- YAML 重载后的旧实例隔离与连接保护
- 自动生成轮询状态传感器和轮询控制开关
- 在 Home Assistant 集成页面显示 Cong Modbus Climate 品牌图标
- 可选的 HomeKit 三档风速代理，不改变原 Climate 的风速选项和 Modbus 轮询

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

## 可选：HomeKit 风速代理（v1.5）

HA 内的原始格力 Climate 可以保留自动和六个手动档位。若它们使用中文
`fan_modes`，HomeKit Bridge 不一定会为直接桥接的空调显示风速入口。
本仓库提供独立的 `homekit_climate_proxy`，只向 HomeKit 暴露 `low`、
`medium`、`high` 三档，原 Climate 的实体 ID、档位和控制方式均不变。
它订阅源实体状态，不增加 Modbus 轮询；只有用户操作代理实体时才调用
源 Climate 的服务。映射关系如下：

| HomeKit 显示 | 写入源实体 | 源实体读回后显示为该档 |
| --- | --- | --- |
| low | 低档 | 低档、中低档 |
| medium | 中档 | 中档、中高档 |
| high | 高档 | 高档、强劲档 |

源实体为 `auto` 或 `fan_mode` 尚未确定时，代理不猜测具体档位。
这个可选代理适用于上述中文档位配置；其他命名应先调整映射并验证。

HACS 只管理本仓库的 `congmodbus` 集成，**不会自动安装可选代理**。
`v1.5` GitHub Release 的 `congmodbus-v1.5-full.zip` 同时包含两个
`custom_components` 目录、两个 Package 示例和本说明。手动安装步骤：

1. 从仓库的 `extras/homekit_climate_proxy/`，或从完整 ZIP 的
   `custom_components/homekit_climate_proxy/`，把代理文件复制到
   `/config/custom_components/homekit_climate_proxy/`。
2. 参考 `examples/packages/homekit_climate_proxy.yaml`，将五个
   `source_entity_id` 改成现场原 Climate 实体 ID，放入已启用的 HA Packages。
3. 运行 HA 配置检查，成功后重启 Core；确认代理实体在 HA 中可用。
4. 创建一座 HomeKit Bridge，只包含这些代理 Climate；将各空调的
   accessory type 设为 `thermostat`。这会发布温控与风扇服务。
5. 在 Apple“家庭”配对新桥，逐台确认响应和风速入口。需要迁移房间、
   场景或自动化引用时，先完成新卡片验证，再移除旧桥。

2026-09-28 的现场验收限于五张新卡片正常响应、均出现风速入口；
没有主动调节风速做物理控制验证。`thermostat` 类型是这次现场验证的
必要配置；此前以 `heater_cooler` 类型发布时，iPhone 没有显示风速入口。

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
- 同一风速寄存器读取时返回的是实际运行档位，不能直接证明设备当前的设定档位；组件通过 HA RestoreEntity 提供重启初始值，收到有效实际风速后以现场读值为准，独立 Sensor 展示完整实际档位。

## 问题反馈

请在 [GitHub Issues](https://github.com/cong86/congmodbus/issues) 提交问题，并附上：

- Home Assistant 版本
- CongModbus 版本
- 脱敏后的 Package 配置
- 相关 `congmodbus`、`gree_bms` 或 `pymodbus` 日志

