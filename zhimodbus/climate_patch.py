from .climate import ZhiModbusClimate, REG_FAN_MODE

# 给 ZhiModbusClimate 打补丁，只修改风速逻辑
async def patched_async_set_fan_mode(self, fan_mode):
    """Set new fan mode with optimistic update."""
    await self.set_mode(self._bus.fan_modes, REG_FAN_MODE, fan_mode)
    # 乐观更新：立即更新面板显示，不依赖寄存器反馈
    self._values[REG_FAN_MODE] = self._bus.fan_modes[fan_mode]
    self.async_write_ha_state()

# 替换原方法
ZhiModbusClimate.async_set_fan_mode = patched_async_set_fan_mode
import logging
logging.getLogger(__name__).warning("climate_patch loaded")
