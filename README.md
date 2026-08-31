<p align="center">
  <img src="https://raw.githubusercontent.com/PC-Supporting-GmbH/HomeAssistant-HACS-GHL/master/images/logo.png" alt="GHL Home Assistant Integration" width="250">
</p>

<h1 align="center">GHL</h1>

<p align="center">
  A custom Home Assistant integration for selected GHL aquarium controllers and luminaires.
</p>

---

## About

This custom integration connects supported GHL devices directly to Home Assistant using the GHL API.

Depending on the connected device and the features provided by the GHL API, the integration can expose measurements, states, controls and actions in Home Assistant.

This allows GHL data and functions to be used in dashboards, automations and other Home Assistant features.

<p align="center">
  <img src="https://raw.githubusercontent.com/PC-Supporting-GmbH/HomeAssistant-HACS-GHL/master/images/ghl-dashboard-example.png" alt="GHL integration in Home Assistant">
</p>

## Disclaimer

This is an unofficial Home Assistant integration and is not developed, maintained or supported by GHL.

The integration is privately developed and provided as-is.

The integration can only expose functionality that is available through the official GHL API. Features or information that are not provided by the GHL API cannot be made available by this integration.

For information about the GHL API and its capabilities, see: https://www.aquariumcomputer.com/software/ghl-api/

> [!WARNING]
> This integration is under development.
> Current development focuses on:
> - Illumination overviews
> - Illumination control
> - Water change functionality

> [!TIP]
> 
> If you find this integration useful and would like to support its development:
>
> <a href="https://www.buymeacoffee.com/HA.GHL.Integration" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/arial-yellow.png" alt="Buy Me a Coffee" style="height: 60px !important;width: 217px !important;" ></a>


## Supported devices

The following GHL device series are supported:

- ProfiLux 4 Series (incl. Industrial Line / IL)
- Mitras LX8 Series
- Mitras LX7 Series (incl. Industrial Line / IL)

The following firmware versions are required:

- ProfiLux 4 firmware 7.52
- Mitras LX7 firmware 1.22
- Mitras LX8 firmware 2.05

Support in this integration is limited to functionality made available by the GHL API for the respective device. 

> [!NOTE]
> The API version currently used in this integration is **1.1**.

## Installation

### HACS

The recommended installation method is through HACS.

[![Open your Home Assistant instance and open this repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=PC-Supporting-GmbH&repository=HomeAssistant-HACS-GHL&category=integration)

After adding the repository to HACS:

1. Install the **GHL** integration.
2. Restart Home Assistant.
3. Go to **Settings → Devices & services**.
4. Select **Add Integration**.
5. Search for **GHL**.

### Manual installation

Alternatively, download the latest version from GitHub.

Copy the `hacs_ghl` folder from `custom_components` into the `custom_components` directory of your Home Assistant installation.

Restart Home Assistant afterwards and add the integration through:

**Settings → Devices & services → Add Integration → GHL**

## Enable the GHL API

The GHL API is disabled by default and must be enabled before Home Assistant can communicate with the device.

Use **GHL Control Center → System → GHL API** to enable API access.

For full functionality of this integration, including functions that write values or start actions, select:

**GHL API is enabled, full access read and write**

Read-only API access is also supported. However, functions that require write access, such as starting or stopping maintenance modes or feed pauses, will not be available when the API is configured for read-only access.

<p align="center">
  <img src="https://raw.githubusercontent.com/PC-Supporting-GmbH/HomeAssistant-HACS-GHL/master/images/ghl-api-settings.png" alt="GHL API settings in GHL Control Center">
</p>

After a firmware update, the GHL API may need to be enabled again. If the integration can no longer communicate with the device after updating its firmware, check this setting first.

More information about enabling the GHL API is available here:

https://www.aquariumcomputer.com/software/ghl-api/

## Configuration

When adding the integration to Home Assistant, enter the network information of your GHL device and select the required API access mode.

The integration connects to the device and discovers the supported GHL resources.

Because the GHL API does not provide the type of an attached sensor, the integration will ask you to assign the appropriate type to detected sensors during setup.

After the initial setup, additional configuration options are available through:

**Settings → Devices & services → GHL → Configure**

## Options

The integration provides additional options after the initial setup.

### General settings

The connection settings can be adjusted if required.

The API access mode can also be changed between read-only and read/write access.

### Show all available resources

The **Show all available resources** option is available after the integration has been set up for the first time.

By default, the integration uses the device configuration to avoid exposing GHL resources that appear to be unused.

Enabling this option also exposes supported resources that would normally be detected as unused and therefore hidden based on the device configuration.

This can be useful if you intentionally want Home Assistant to expose all supported resources reported by the GHL device.

### Sensor configuration

Sensor types assigned during the initial setup can later be changed through the integration options.

This allows the sensor configuration to be corrected or adjusted without removing and setting up the integration again.

## Changing values from Home Assistant

Some values and descriptions exposed by the GHL API can be changed directly from the Home Assistant user interface.

An **Entities card** is recommended for these controls because it displays the selection, input field and write button together.

### Sensor setpoints

To change a sensor setpoint:

1. Select the desired GHL sensor.
2. Enter the new setpoint.
3. Press **Write setpoint**.

The new value is then sent to the GHL device. No Automation required, however you can use one.

### Descriptions

Descriptions of supported GHL elements can also be changed directly from Home Assistant.

To change a description:

1. Select the desired GHL element.
2. Enter the new description in the **Description** field.
3. Press **Write description**.

No Home Assistant automation is required. But you can use it.

## Current limitations

The integration is limited by the functionality and information provided by the GHL API.

Currently known limitations include:

- **Sensor types cannot be read from the GHL API.**  
  The sensor type therefore has to be assigned separately during setup. The assignment can later be changed through the integration options.

- **Timers are currently not imported.**  
  The GHL API exposes the timer description, but not the timer switching times. Importing timers would therefore currently provide little useful functionality in Home Assistant.

## Issues and feature requests

If you find a problem or have an idea for improving the integration, please use the GitHub issue forms.

**Bug reports:**  
https://github.com/PC-Supporting-GmbH/HomeAssistant-HACS-GHL/issues/new?template=bug_report.yml

**Feature requests:**  
https://github.com/PC-Supporting-GmbH/HomeAssistant-HACS-GHL/issues/new?template=feature_request.yml

Before opening a new issue, please check whether the same problem or request has already been reported.