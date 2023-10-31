"""The Tuya BLE integration."""
from __future__ import annotations

from dataclasses import dataclass, field

import logging
from typing import Any, Callable
from enum import IntEnum, StrEnum, Enum
from homeassistant.components.tuya.const import (
    DPCode,
)

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ATTR_WHITE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_COLOR_MODE,
    ColorMode,
    LightEntity,
    LightEntityFeature,
    LightEntityDescription,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .devices import TuyaBLEData, TuyaBLEEntity, TuyaBLEProductInfo
from .tuya_ble import TuyaBLEDataPointType, TuyaBLEDevice

_LOGGER = logging.getLogger(__name__)

# TODO : support for other kind of lights, configuration for min/max values for
#        brightness or others, colors parameters...
# Note: only "dd" devices have been tested

# Actually might need to be defined in the mapping
class WorkMode(IntEnum):
    """Work modes."""

    COLOUR = 0
    SCENE = 1
    WHITE = 2
    MUSIC = 3

@dataclass
class TuyaBLELightMapping:
    description: LightEntityDescription
    dp_ids: dict[DPCode, int]
    min_color_temp = 2700
    max_color_temp = 6500

@dataclass
class TuyaBLECategoryLightMapping:
    products: dict[str, list[TuyaBLELightMapping]] | None = None
    mapping: list[TuyaBLELightMapping] | None = None


mapping: dict[str, TuyaBLECategoryLightMapping] = {
    # String Lights
    # https://developer.tuya.com/en/docs/iot/dc?id=Kaof7taxmvadu
    "dc": TuyaBLECategoryLightMapping(
        # fill  with { <some product ID> : TuyaBLELightMapping } if the values returned from the cloud aren't usable
        products =  {},

        # default mapping
        mapping = [
                # dp_ids will be filled by using the cloud values
                TuyaBLELightMapping(
                    dp_ids = {},
                    description = LightEntityDescription(
                        key = DPCode.SWITCH_LED,
                    ),
                ),
            ],
        ),


    # Strip Lights
    # https://developer.tuya.com/en/docs/iot/dd?id=Kaof804aibg2l
    "dd": TuyaBLECategoryLightMapping(
        # fill  with { <some product ID> : TuyaBLELightMapping } if the values returned from the cloud aren't usable
        products =  {},

        # default mapping
        mapping = [
                # dp_ids will be filled by using the cloud values
                TuyaBLELightMapping(
                    dp_ids = {},
                    description = LightEntityDescription(
                        key = DPCode.SWITCH_LED,
                    ),
                ),
            ],
        ),

    # Light
    # https://developer.tuya.com/en/docs/iot/categorydj?id=Kaiuyzy3eheyy
    "dj": TuyaBLECategoryLightMapping(
        # fill  with { <some product ID> : TuyaBLELightMapping } if the values returned from the cloud aren't usable
        products =  {},

        # default mapping
        mapping = [
                # dp_ids will be filled by using the cloud values
                TuyaBLELightMapping(
                    dp_ids = {},
                    description = LightEntityDescription(
                        key = DPCode.SWITCH_LED,
                    ),
                ),
            ],
        ),

    # Ambient Light
    # https://developer.tuya.com/en/docs/iot/ambient-light?id=Kaiuz06amhe6g
    "fwd": TuyaBLECategoryLightMapping(
        # fill  with { <some product ID> : TuyaBLELightMapping } if the values returned from the cloud aren't usable
        products =  {},

        # default mapping
        mapping = [
                # dp_ids will be filled by using the cloud values
                TuyaBLELightMapping(
                    dp_ids = {},
                    description = LightEntityDescription(
                        key = DPCode.SWITCH_LED,
                    ),
                ),
            ],
        ),
}


def get_mapping_by_device(device: TuyaBLEDevice) -> list[TuyaBLECategoryLightMapping]:
    category = mapping.get(device.category)
    if category is not None:
        if category.products is not None:
            product_mapping = category.products.get(device.product_id)
            if product_mapping is not None:
                return product_mapping
        if category.mapping is not None:
            return category.mapping
        else:
            return []
    else:
        return []


class TuyaBLELight(TuyaBLEEntity, LightEntity):
    """Representation of a Tuya BLE Light."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: DataUpdateCoordinator,
        device: TuyaBLEDevice,
        product: TuyaBLEProductInfo,
        mapping: TuyaBLELightMapping,
    ) -> None:
        super().__init__(hass, coordinator, device, product, mapping.description)
        self._mapping = mapping

        color_modes = { ColorMode.ONOFF }

        self._attr_color_mode = ColorMode.ONOFF

        if mapping.dp_ids.get(DPCode.BRIGHT_VALUE):
            color_modes.add(ColorMode.BRIGHTNESS)
            self._attr_color_mode = ColorMode.BRIGHTNESS

        if mapping.dp_ids.get(DPCode.TEMP_VALUE):
            color_modes.add(ColorMode.COLOR_TEMP)
            self._attr_color_mode = ColorMode.COLOR_TEMP
            self._attr_min_color_temp_kelvin = mapping.min_color_temp
            self._attr_max_color_temp_kelvin = mapping.max_color_temp

        if mapping.dp_ids.get(DPCode.COLOUR_DATA):
            color_modes.add(ColorMode.HS)
            self._attr_color_mode = ColorMode.HS

        self._attr_supported_color_modes = color_modes

        self._attr_brightness = 0
        self._attr_hs_color = (0, 0)
        self._attr_is_on = False

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        dpid = self._mapping.dp_ids.get(DPCode.WORK_MODE)
        if dpid:
            datapoint = self._device.datapoints[dpid]
            if datapoint:
                if datapoint.value == WorkMode.WHITE:
                    self._attr_color_mode = ColorMode.WHITE
                else:
                    self._attr_color_mode = ColorMode.HS

        dpid = self._mapping.dp_ids.get(DPCode.BRIGHT_VALUE)
        if dpid:
            datapoint = self._device.datapoints[dpid]
            if datapoint:
                self._attr_color_mode = ColorMode.WHITE
                self._attr_brightness = float(datapoint.value) * 255 / 1000

        dpid = self._mapping.dp_ids.get(DPCode.TEMP_VALUE)
        if dpid:
            datapoint = self._device.datapoints[dpid]
            if datapoint:
                val = float(datapoint.value)
                self._attr_color_mode = ColorMode.WHITE
                self._attr_color_temp_kelvin = self._attr_min_color_temp_kelvin + val * (self._attr_max_color_temp_kelvin - self._attr_min_color_temp_kelvin) / 1000

        dpid = self._mapping.dp_ids.get(DPCode.COLOUR_DATA)
        if dpid:
            datapoint = self._device.datapoints[dpid]
            if datapoint:
                # from Tuya doc:
                # color format :
                # Value: 000011112222
                # 0000: H (chromaticity: 0-360, 0X0000-0X0168)
                # 1111: S (saturation: 0-1000, 0X0000-0X03E8)
                # 2222: V (Brightness: 0-1000, 0X0000-0X03E8)

                hsl_string = datapoint.value
                if len(hsl_string) == 12:
                    h = float(int(hsl_string[:4], 16))
                    s = float(int(hsl_string[4:8], 16)) * 100 / 1000
                    b = float(int(hsl_string[8:], 16)) * 255 / 1000
                    self._attr_color_mode = ColorMode.HS
                    self._attr_hs_color = (h,s)
                    self._attr_brightness = b


        dpid = self._mapping.dp_ids.get(DPCode.SWITCH_LED)
        if dpid:
            datapoint = self._device.datapoints[dpid]
            if datapoint:
                self._attr_is_on = datapoint.value

        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""

        if self._mapping.dp_ids and self._mapping.dp_ids.get(DPCode.SWITCH_LED):
            datapoint = self._device.datapoints[self._mapping.dp_ids[DPCode.SWITCH_LED]]
            if datapoint:
                return bool(datapoint.value)
        return False

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""

        color_mode = self._attr_color_mode
        if ATTR_COLOR_MODE in kwargs:
            color_mode =  kwargs[ATTR_COLOR_MODE]

        brightness = self._attr_brightness
        if ATTR_BRIGHTNESS in kwargs:
            brightness =  kwargs[ATTR_BRIGHTNESS]

        color_temp = self._attr_color_temp_kelvin
        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            color_temp =  kwargs[ATTR_COLOR_TEMP_KELVIN]
            color_mode = ColorMode.WHITE

        if ATTR_WHITE in kwargs:
            brightness =  kwargs[ATTR_WHITE]
            color_mode = ColorMode.WHITE

        hs_color = self._attr_hs_color
        if ATTR_HS_COLOR in kwargs:
            hs_color =  kwargs[ATTR_HS_COLOR]
            color_mode = ColorMode.HS

        if hs_color == None:
            color_mode = ColorMode.WHITE

        if color_mode == ColorMode.WHITE:
            self.send_color_temp(color_temp)
            self.send_brightness(brightness)

        if color_mode == ColorMode.HS:
            self.send_hsb(hs_color, brightness)

        self.send_onoff(True)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""

        self.send_onoff(False)

    # brightness is 0..255
    def send_brightness(self, brightness : Int) -> None:

        _LOGGER.debug("Send Brightness %d", brightness)

        if self._attr_color_mode != ColorMode.WHITE:
            self.send_dp_value(DPCode.WORK_MODE, TuyaBLEDataPointType.DT_ENUM, WorkMode.WHITE)

        new_value = brightness * 1000 / 255
        self.send_dp_value(DPCode.BRIGHT_VALUE, TuyaBLEDataPointType.DT_VALUE, new_value)


    def send_color_temp(self, color_temp : Int) -> None:

        _LOGGER.debug("Send Color Temp %d", color_temp)

        if self._attr_color_mode != ColorMode.WHITE:
            self.send_dp_value(DPCode.WORK_MODE, TuyaBLEDataPointType.DT_ENUM, WorkMode.WHITE)

        new_value = float(color_temp - self._attr_min_color_temp_kelvin) / float(self._attr_max_color_temp_kelvin - self._attr_min_color_temp_kelvin) * 1000
        self.send_dp_value(DPCode.TEMP_VALUE, TuyaBLEDataPointType.DT_VALUE, int(new_value))



    def send_hsb(self, hs : float[2], brightness: Int) -> None:

        _LOGGER.debug("Send HSB %f %f %f", hs[0], hs[1], float(brightness))

        if self._attr_color_mode != ColorMode.HS:
            self.send_dp_value(DPCode.WORK_MODE, TuyaBLEDataPointType.DT_ENUM, WorkMode.COLOUR)

        h = int(hs[0])
        s = int(hs[1] * 1000 / 100)
        b = int(brightness * 1000 / 255)

        new_value = ("%04X" % h) + ("%04X" % s) + ("%04X" % b)
        self.send_dp_value(DPCode.COLOUR_DATA, TuyaBLEDataPointType.DT_STRING, new_value)


    def send_onoff(self, onoff: bool) -> None:

        self.send_dp_value(DPCode.SWITCH_LED, TuyaBLEDataPointType.DT_BOOL, onoff)

    def send_dp_value(self,
        key: DPCode,
        type: TuyaBLEDataPointType,
        value: bytes | bool | int | str | None = None) -> None:

        dpid = self._mapping.dp_ids.get(key)
        if dpid:
            datapoint = self._device.datapoints.get_or_create(
                    dpid,
                    type,
                    value,
            )
            if datapoint:
                self._hass.create_task(datapoint.set_value(value))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Tuya BLE sensors."""
    data: TuyaBLEData = hass.data[DOMAIN][entry.entry_id]
    mappings = get_mapping_by_device(data.device)
    entities: list[TuyaBLELight] = []

    for mapping in mappings:
        if not mapping.dp_ids:
            # Fill it by using the values retrieved from the cloud
            functions = data.device.device_functions
            if functions:
                dp_ids = {}
                for function in functions:
                    code = function.get("code")
                    dp_id = function.get("dp_id")
                    if code and dp_id:
                        dp_ids[code] = dp_id
                mapping.dp_ids = dp_ids
                _LOGGER.debug("Setting DP_IDs from cloud info : %s", str(mapping.dp_ids))
            else:
                _LOGGER.debug("No functions for product %s:%s", data.device.category(), data.device.product_id())

        if mapping.dp_ids:
            entities.append(
                TuyaBLELight(
                        hass,
                        data.coordinator,
                        data.device,
                        data.product,
                        mapping,
                )
        )
    async_add_entities(entities)
