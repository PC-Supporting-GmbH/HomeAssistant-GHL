"""Constants for the GHL integration."""

DOMAIN = "hacs_ghl"

DEFAULT_PORT = 10002

DISCOVERY_LIMIT = 0

UPDATE_INTERVAL_SECONDS = 30

DESCRIPTION_TEXT_MAX_LENGTH = 16

CONF_ACCESS_MODE = "access_mode"
CONF_DEVICE_TYPE = "device_type"
CONF_SENSOR_TYPE = "sensor_type"
CONF_SENSOR_TYPES = "sensor_types"
CONF_SENSOR_UNIT = "sensor_unit"
CONF_SENSOR_UNITS = "sensor_units"
CONF_KNOWN_SENSORS = "known_sensors"
CONF_SHOW_ALL_RESOURCES = "show_all_resources"

ACCESS_MODE_READ_ONLY = "read_only"
ACCESS_MODE_FULL_ACCESS = "full_access"

DEVICE_TYPE_PROFILUX_4 = "profilux_4"
DEVICE_TYPE_MITRAS_LX7 = "mitras_lx7"
DEVICE_TYPE_MITRAS_LX8 = "mitras_lx8"

SENSOR_TYPE_UNKNOWN = "unknown"
SENSOR_TYPE_HIDDEN = "hidden"
SENSOR_TYPE_TEMPERATURE = "temperature"
SENSOR_TYPE_PH = "ph"
SENSOR_TYPE_REDOX = "redox"
SENSOR_TYPE_CONDUCTIVITY_FRESHWATER = "conductivity_freshwater"
SENSOR_TYPE_CONDUCTIVITY_SEAWATER = "conductivity_seawater"
SENSOR_TYPE_OXYGEN = "oxygen"
SENSOR_TYPE_HUMIDITY = "humidity"
SENSOR_TYPE_AIR_TEMPERATURE = "air_temperature"
SENSOR_TYPE_VOLTAGE = "voltage"

SENSOR_UNIT_MS = "ms"
SENSOR_UNIT_PSU = "psu"
SENSOR_UNIT_KG_L = "kg_l"