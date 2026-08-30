# Changelog

## 1.4.1 — 2026-08-30

- 补齐集成品牌图标的发布说明与 SHA-256 完整性清单。
- 清理误提交的 `__pycache__` / `.pyc` 生成文件。
- CI 增加被 `.gitignore` 忽略文件的跟踪检查，防止生成缓存再次进入发布标签。

## 1.4.0 — 2026-08-30

- 将风速寄存器从 10 秒完整轮询拆出，改为每 4 秒专用读取；其他属性仍保持 10 秒轮询。
- 快速风速读取继续共用 Hub I/O 锁、轮询开关、故障熔断、退避和重连保护。
- ActualFanSpeedSensor 继续订阅共享缓存，不直接重复访问 Modbus。
- 示例 Package 补齐中低档和中高档，同时保留标准 `low/medium/high` 内部值。
- 增加 `brand/icon.png`（512×512）和 `brand/icon@2x.png`（1024×1024）集成品牌图标。

## 1.3.1 — 2026-08-29

- 修复 RestoreEntity 恢复为 auto 后，线控器物理改为低/中/高档时 Climate 不更新的问题。
- 有效实际风速读值现在会覆盖旧的 auto 缓存；写入后的 20 秒 pending 保护保持不变。
- 风机停、超低速、静音档和未配置档位仍保持 Climate 旧值，由独立实际风速 Sensor 展示完整状态。

## 1.3.0 — 2026-08-29

- ActualFanSpeedSensor 改为订阅 Climate 的共享风速读值，不再重复访问 Modbus。
- 实际风速实体跟随共享轮询熔断状态，在通信失败时正确标记 unavailable。
- Climate 使用 Home Assistant RestoreEntity 恢复上次风速设定和开机模式。
- 保持既有实体名称、unique_id 和 YAML 配置兼容。
- 修正示例 Package 中 5 台室内机的实际风速 Sensor 地址。

## 1.2.0 — 2026-08-29

- Climate 增加实际风速轮询和读写枚举转换。
- 增加 ActualFanSpeedSensor，区分风速设定与实际运行档位。
- 增加风速写入后的 pending 乐观更新。

## 1.1.1 — 2026-08-14

- 修正 `manifest.json` 版本号，使其与 GitHub Release 一致。
- 清理仓库中不应发布的 `__pycache__` 和 `.pyc` 文件。
- 增加 HACS 仓库配置与自动验证工作流。
- 增加完整 Package 示例和 HA 2026.8 Modbus Hub 兼容说明。
- 提供独立快速恢复附件。
- 保持现有实体名称和 `unique_id` 生成规则不变。

## 1.1.0

- 增加同一 Hub 的共享 Modbus I/O 锁。
- 增加通信失败退避、轮询熔断和自动重连。
- 增加 YAML 重载保护和旧实例隔离。
- 增加轮询状态传感器与轮询开关。
- 增加写入后的短期状态保持，减少界面回跳。

