# Cong Modbus Climate v1.5

本版本保留 v1.4.1 的 Modbus 读写和原始 Climate 功能，并提供可选的 HomeKit 风速代理。

- 完整附件 `congmodbus-v1.5-full.zip` 包含 `congmodbus` 主组件、`homekit_climate_proxy`、两个 Package 示例和说明文档；包内 `SHA256SUMS.txt` 可校验各文件。
- 代理把现有中文手动档位映射为 HomeKit 的 `low`、`medium`、`high`，不修改原始 Climate 的七个选项，也不增加 Modbus 轮询。
- HACS 仍只安装和更新 `congmodbus` 主组件；代理需按 README 手动安装，并在 HomeKit Bridge 中选用 `thermostat` accessory type。
- 现场已确认五张 Apple“家庭”卡片均正常响应且出现风速入口。尚未通过实际调档和物理风速读回验证控制链路。

安装、桥接和回滚步骤见 [README](https://github.com/cong86/congmodbus#可选homekit-风速代理v15)。
