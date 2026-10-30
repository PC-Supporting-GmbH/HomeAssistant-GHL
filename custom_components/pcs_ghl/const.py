"""Constants for the GHL integration."""

from datetime import timedelta

DOMAIN = "pcs_ghl"

DEFAULT_PORT = 10002

DISCOVERY_LIMIT = 0

UPDATE_INTERVAL_SECONDS = 30

DESCRIPTION_CHECK_EVERY_N_UPDATES = 5

ILLUMINATION_CURVE_CHECK_EVERY_N_UPDATES = 60

SETUP_CONNECTION_ATTEMPTS = 3
SETUP_CONNECTION_RETRY_DELAY_SECONDS = 3
SETUP_CONNECTION_TIMEOUT_SECONDS = 3

DESCRIPTION_TEXT_MAX_LENGTH = 16

CONF_ACCESS_MODE = "access_mode"
CONF_DEVICE_TYPE = "device_type"
CONF_SENSOR_TYPE = "sensor_type"
CONF_SENSOR_TYPES = "sensor_types"
CONF_SENSOR_UNIT = "sensor_unit"
CONF_SENSOR_UNITS = "sensor_units"
CONF_KNOWN_SENSORS = "known_sensors"
CONF_SHOW_ALL_RESOURCES = "show_all_resources"
CONF_IMPORT_HISTORICAL_DATA = "import_historical_data"
CONF_HISTORY_PRESENT_RESOURCES = "history_present_resources"

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

IONDIRECTOR_PARAMETER_KEYS = {
    0: "calcium",
    1: "magnesium",
    2: "potassium",
    3: "sodium",
    4: "nitrate",
}

THUNDERSTORM_DEFAULT_DURATION = 5

LIGHTSCENE_DEFAULT_FADETIME = 0

SENSOR_SETPOINT_MIN_VALUE = -10000

SENSOR_SETPOINT_MAX_VALUE = 10000

SENSOR_SETPOINT_STEP = 0.000001

# ProfiLux 4 programming manual, 2021-11-22, section 5.2, page 45.
# Only types with documented setpoint limits matching the current native unit.
SENSOR_SETPOINT_LIMITS = {
    SENSOR_TYPE_PH: (4.5, 9.5, 0.1),
    SENSOR_TYPE_TEMPERATURE: (1.0, 36.0, 0.1),
    SENSOR_TYPE_REDOX: (-300, 600, 1),
    SENSOR_TYPE_CONDUCTIVITY_FRESHWATER: (10, 1900, 1),
    SENSOR_TYPE_CONDUCTIVITY_SEAWATER: (0.5, 99.5, 0.1),
    SENSOR_TYPE_HUMIDITY: (2.0, 98.0, 0.1),
    SENSOR_TYPE_AIR_TEMPERATURE: (0.0, 50.0, 0.1),
    SENSOR_TYPE_VOLTAGE: (0.0, 10.0, 0.01),
}

CONF_INITIAL_HISTORY_PENDING = "initial_history_pending"

_SENSOR_ERROR_MASK = 512 | 1024

_HISTORY_RESOURCE_TYPES = {
    "SENSOR",
    "KHDIRECTOR",
    "IONDIRECTOR",
}

UPDATE_INTERVAL = timedelta(seconds=UPDATE_INTERVAL_SECONDS)

PLATFORMS = [
    "sensor",
    "binary_sensor",
    "button",
    "number",
    "select",
    "text",
]

ISSUE_NEW_SENSORS_PREFIX = "new_sensors"

FEEDPAUSE_COUNT = 4

MAINTENANCE_COUNT = 4

WATERCHANGE_COUNT = 4

LIGHTSCENE_COUNT = 8

DESCRIPTION_RESOURCE_TYPES = {
    "SENSOR",
    "SWITCHCHANNEL",
    "ILLUMINATION",
    "TIMER",
    "DOSER",
    "FLOWSENSOR",
    "LEVELSENSOR",
}

DESCRIPTION_RESOURCE_ORDER = {
    "SENSOR": 0,
    "SWITCHCHANNEL": 1,
    "ILLUMINATION": 2,
    "TIMER": 3,
    "DOSER": 4,
    "FLOWSENSOR": 5,
    "LEVELSENSOR": 6,
}

DESCRIPTION_UPDATE_PLATFORMS = {
    "SENSOR": [
        "sensor",
        "number",
    ],
    "SWITCHCHANNEL": [
        "sensor",
        "binary_sensor",
    ],
    "ILLUMINATION": [
        "sensor",
    ],
    "TIMER": [],
    "DOSER": [
        "sensor",
    ],
    "FLOWSENSOR": [
        "sensor",
    ],
    "LEVELSENSOR": [
        "binary_sensor",
    ],
}

DESCRIPTION_RESOURCE_TRANSLATION_KEYS = {
    "SENSOR": "description_resource_sensor",
    "SWITCHCHANNEL": "description_resource_switchchannel",
    "ILLUMINATION": "description_resource_illumination",
    "TIMER": "description_resource_timer",
    "DOSER": "description_resource_doser",
    "FLOWSENSOR": "description_resource_flowsensor",
    "LEVELSENSOR": "description_resource_levelsensor",
}

DESCRIPTION_RESOURCE_FALLBACKS = {
    "SENSOR": "Sensor {index}",
    "SWITCHCHANNEL": "Switch Channel {index}",
    "ILLUMINATION": "Illumination {index}",
    "TIMER": "Timer {index}",
    "DOSER": "Dosing Pump {index}",
    "FLOWSENSOR": "Flow Sensor {index}",
    "LEVELSENSOR": "Level Sensor {index}",
}

ILLUMINATION_MAX_CURVE_POINTS = 24

KHDIRECTOR_ACTION_COUNT = 5

IONDIRECTOR_ACTION_COUNT = 6

API_COMMAND_ATTEMPTS = 2

API_COMMAND_TIMEOUT_SECONDS = 10

API_COMMAND_RETRY_DELAY_SECONDS = 3

API_COMMAND_REPLY_DELAY_SECONDS = 0.1

API_REPLY_BUFFER_SIZE = 256

ATTR_GHL_RESOURCE_TYPE = "ghl_resource_type"

ATTR_GHL_FEATURE_TYPE = "ghl_feature_type"
