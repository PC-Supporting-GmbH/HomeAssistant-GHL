<hr>

[English](../README.md) · [Deutsch](README.de.md) · [Français](README.fr.md) (traducción automática) · **Español** (traducción automática)

<hr>

<p align="center">
  <img src="https://raw.githubusercontent.com/PC-Supporting-GmbH/HomeAssistant-GHL/master/docs/images/logo.png" alt="Integración GHL para Home Assistant" width="250">
</p>

<h1 align="center">GHL</h1>

<p align="center">
  Una integración personalizada para Home Assistant compatible con determinados controladores de acuario y luminarias GHL.
</p>

## Índice

- [1. Acerca de la integración](#1-acerca-de-la-integración)
- [2. Aviso de responsabilidad](#2-aviso-de-responsabilidad)
- [3. Dispositivos compatibles](#3-dispositivos-compatibles)
- [4. Instalación](#4-instalación)
- [5. Activar la API de GHL](#5-activar-la-api-de-ghl)
- [6. Configuración](#6-configuración)
- [7. Opciones](#7-opciones)
- [8. Cambiar valores desde Home Assistant](#8-cambiar-valores-desde-home-assistant)
- [9. Limitaciones actuales](#9-limitaciones-actuales)
- [10. Problemas y solicitudes de funciones](#10-problemas-y-solicitudes-de-funciones)
- [11. Para entusiastas de Home Assistant](#11-para-entusiastas-de-home-assistant)

<hr>

## 1. Acerca de la integración

Esta integración personalizada conecta directamente los dispositivos GHL compatibles con Home Assistant mediante la API de GHL.

Según el dispositivo conectado y las funciones proporcionadas por la API de GHL, la integración puede ofrecer mediciones, estados, controles y acciones en Home Assistant.

Esto permite utilizar los datos y las funciones de GHL en paneles, automatizaciones y otras funciones de Home Assistant.

<p align="center">
  <img src="https://raw.githubusercontent.com/PC-Supporting-GmbH/HomeAssistant-GHL/master/docs/images/ghl-dashboard-example.png" alt="Integración GHL en Home Assistant" width="800">
</p>

## 2. Aviso de responsabilidad

Esta es una integración no oficial para Home Assistant. GHL no la desarrolla, mantiene ni proporciona soporte para ella.

La integración se desarrolla de forma privada y se proporciona tal cual.

La integración solo puede ofrecer funciones disponibles a través de la API oficial de GHL. Las funciones o la información que no proporciona la API de GHL no pueden estar disponibles mediante esta integración.

Para obtener información sobre la API de GHL y sus posibilidades, consulta: https://www.aquariumcomputer.com/software/ghl-api/

> [!WARNING]
> Esta integración está en desarrollo.

> [!TIP]
>
> Si esta integración te resulta útil y deseas apoyar su desarrollo:
>

<p align="center">
  <a href="https://www.buymeacoffee.com/HA.GHL.Integration" target="_blank"><img height="60" src="https://raw.githubusercontent.com/PC-Supporting-GmbH/HomeAssistant-GHL/master/docs/images/buymeacoffee.png" alt="Apoyar el desarrollo de la integración GHL"></a>
</p>

## 3. Dispositivos compatibles

Se admiten las siguientes series de dispositivos GHL:

- Serie ProfiLux 4 (incluida Industrial Line / IL)
- Serie Mitras LX8
- Serie Mitras LX7 (incluida Industrial Line / IL)

Se requieren las siguientes versiones de firmware:

- ProfiLux 4: firmware 7.52
- Mitras LX7: firmware 1.22
- Mitras LX8: firmware 2.05

La compatibilidad de esta integración se limita a las funciones que la API de GHL ofrece para cada dispositivo.

> [!NOTE]
> La versión de la API que utiliza actualmente esta integración es la **1.1**.

## 4. Instalación

### 4.1 HACS

Se recomienda instalar la integración mediante HACS.

[![Abre tu instancia de Home Assistant y este repositorio en Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=PC-Supporting-GmbH&repository=HomeAssistant-GHL&category=integration)

Después de añadir el repositorio a HACS:

1. Instala la integración **GHL**.
2. Reinicia Home Assistant.
3. Ve a **Ajustes → Dispositivos y servicios**.
4. Selecciona **Añadir integración**.
5. Busca **GHL**.

### 4.2 Instalación manual

También puedes descargar la última versión desde GitHub.

Copia la carpeta `pcs_ghl` de `custom_components` al directorio `custom_components` de tu instalación de Home Assistant.

Después, reinicia Home Assistant y añade la integración desde:

**Ajustes → Dispositivos y servicios → Añadir integración → GHL**

## 5. Activar la API de GHL

La API de GHL está desactivada de forma predeterminada y debe activarse para que Home Assistant pueda comunicarse con el dispositivo.

Activa el acceso a la API en **GHL Control Center → System → GHL API**.

Para disponer de todas las funciones de esta integración, incluidas la escritura de valores y la ejecución de acciones, selecciona:

**GHL API is enabled, full access read and write**

También se admite el acceso a la API en modo de solo lectura. Sin embargo, las funciones que requieren acceso de escritura, como iniciar o detener modos de mantenimiento o pausas de alimentación, no están disponibles cuando la API está configurada en modo de solo lectura.

<p align="center">
  <img src="https://raw.githubusercontent.com/PC-Supporting-GmbH/HomeAssistant-GHL/master/docs/images/ghl-api-settings.png" alt="Ajustes de la API de GHL en GHL Control Center" width="400">
</p>

Después de actualizar el firmware, puede ser necesario volver a activar la API de GHL. Si la integración deja de comunicarse con el dispositivo después de una actualización, comprueba primero este ajuste.

Encontrarás más información sobre cómo activar la API de GHL aquí:

https://www.aquariumcomputer.com/software/ghl-api/

## 6. Configuración

Al añadir la integración a Home Assistant, introduce los datos de red de tu dispositivo GHL y selecciona el modo de acceso a la API deseado.

La integración se conecta al dispositivo y detecta los recursos GHL compatibles.

Como la API de GHL no proporciona el tipo de los sensores conectados, la integración te pedirá que asignes el tipo adecuado a los sensores detectados durante la configuración inicial.

Después de la configuración inicial, hay opciones adicionales disponibles en:

**Ajustes → Dispositivos y servicios → GHL → Configurar**

## 7. Opciones

La integración ofrece opciones adicionales después de la configuración inicial.

> [!NOTE]
> Algunas opciones solo están disponibles después de conectarse correctamente al dispositivo GHL y una vez que la integración se haya cargado.

### 7.1 Ajustes generales

Los ajustes de conexión pueden modificarse si es necesario.

El modo de acceso a la API también puede cambiarse entre solo lectura y lectura/escritura.

#### 7.1.1 Mostrar todos los recursos disponibles

Esta opción está disponible después de configurar la integración por primera vez.

De forma predeterminada, la integración utiliza la configuración del dispositivo para evitar mostrar recursos GHL que parecen no utilizarse.

Al activar esta opción, también se muestran recursos compatibles que normalmente se detectarían como no utilizados y, por tanto, se ocultarían según la configuración del dispositivo.

Esto puede resultar útil si quieres mostrar deliberadamente en Home Assistant todos los recursos compatibles que comunica el dispositivo GHL.

#### 7.1.2 Importar datos históricos de sensores nuevos

Activa esta opción para importar automáticamente los datos históricos cuando se detectan y configuran por primera vez sensores o fuentes compatibles. Activar esta opción más adelante no importa automáticamente los datos de fuentes que ya están presentes.

### 7.2 Configuración de sensores

Los tipos de sensor asignados durante la configuración inicial pueden cambiarse posteriormente desde las opciones de la integración.

Esto permite corregir o adaptar la configuración de los sensores sin eliminar y volver a configurar la integración.

### 7.3 Detectar sensores/dispositivos nuevos

Después de añadir sensores o dispositivos a tu sistema GHL, selecciona la opción para detectar sensores/dispositivos nuevos en las opciones de la integración.
Esto vuelve a cargar la integración y ejecuta de nuevo la detección de recursos. No es necesario reiniciar Home Assistant. Es posible que debas asignar un tipo a los sensores recién detectados.

### 7.4 Importación de datos históricos

Para importar manualmente los datos almacenados de todas las fuentes disponibles y compatibles, selecciona **Datos históricos: importar ahora** en las opciones de la integración.
Se excluyen los sensores sin un tipo asignado o configurados como ocultos. La detección de duplicados ayuda a evitar que los mismos datos históricos se importen más de una vez.
La importación de una gran cantidad de datos almacenados puede tardar varios minutos.

## 8. Cambiar valores desde Home Assistant

Algunos valores y descripciones que ofrece la API de GHL pueden modificarse directamente desde la interfaz de Home Assistant.

Para cambiar valores, se requiere acceso de escritura tanto en el dispositivo GHL como en la integración. En modo de solo lectura, se muestran las consignas de los sensores, pero los cambios se rechazan con el mensaje correspondiente. El control de brillo general no está disponible en modo de solo lectura.

Se recomienda utilizar una **tarjeta Entidades** para estos controles.

### 8.1 Consignas de los sensores

Cambia el valor en el campo de consigna del sensor deseado. El valor se envía directamente al dispositivo GHL. Esto también se aplica a las consignas compatibles de KH Director e ION Director.

### 8.2 Brillo general

Cambia el valor del brillo general (0–100 %). El valor se envía directamente al dispositivo GHL.

### 8.3 Descripciones

Las descripciones de los elementos GHL compatibles también pueden cambiarse directamente desde Home Assistant.

Para cambiar una descripción:

1. Selecciona el elemento GHL deseado.
2. Introduce la nueva descripción en el campo **Descripción**.
3. Pulsa **Escribir descripción**.

No se necesita una automatización de Home Assistant. No obstante, puedes utilizar una.

## 9. Limitaciones actuales

La integración está limitada por las funciones y la información que proporciona la API de GHL.

Entre las limitaciones conocidas actualmente se incluyen:

- **Los tipos de sensor no pueden leerse mediante la API de GHL.**  
  Por tanto, el tipo de sensor debe asignarse por separado durante la configuración inicial. Esta asignación puede cambiarse después desde las opciones de la integración.

- **Actualmente no se importan los temporizadores.**  
  La API de GHL ofrece su descripción, pero no sus horarios de conmutación. Por ello, importar temporizadores aportaría actualmente pocas funciones útiles en Home Assistant.

## 10. Problemas y solicitudes de funciones

Si encuentras un problema o tienes una idea para mejorar la integración, utiliza los formularios de incidencias de GitHub.

**Informes de errores:**  
https://github.com/PC-Supporting-GmbH/HomeAssistant-GHL/issues/new?template=bug_report.yml

**Solicitudes de funciones:**  
https://github.com/PC-Supporting-GmbH/HomeAssistant-GHL/issues/new?template=feature_request.yml

Antes de abrir una nueva incidencia, comprueba si ya se ha comunicado el mismo problema o la misma solicitud.

## 11. Para entusiastas de Home Assistant

### 11.1 Filtrar entidades por recurso y función

La integración añade dos atributos a las entidades correspondientes:

- **`ghl_resource_type`** identifica el grupo de recursos, por ejemplo `switch_channel`, `sensor` o `illumination`.
- **`ghl_feature_type`** identifica la función dentro de ese grupo, por ejemplo `state`, `value` o `setpoint`.

Estos atributos permiten seleccionar entidades para paneles o plantillas sin tener que analizar sus nombres.

Se utilizan las siguientes combinaciones. Las entidades disponibles dependen del dispositivo, de sus funciones disponibles y de tu configuración.

| Entidades o funciones | `ghl_resource_type` | `ghl_feature_type` |
|---|---|---|
| Valores medidos de los sensores | `sensor` | `value` |
| Consignas de los sensores | `sensor` | `setpoint` |
| Estados de los canales de conmutación | `switch_channel` | `state` |
| Corrientes eléctricas de los canales de conmutación | `switch_channel` | `electric_current` |
| Valores de brillo de los canales de iluminación | `illumination` | `channel_brightness` |
| Valores de brillo general – indicadores y controles | `illumination` | `master_brightness` |
| Niveles de llenado de las bombas dosificadoras | `doser` | `fill_level` |
| Capacidades de las bombas dosificadoras | `doser` | `capacity` |
| Mediciones de caudal | `flow_sensor` | `value` |
| Estados de los sensores de nivel | `level_sensor` | `state` |
| Inicio y parada de las pausas de alimentación | `special_function` | `feed` |
| Inicio y parada de los modos de mantenimiento | `special_function` | `maintenance` |
| Inicio y parada de los cambios de agua | `special_function` | `waterchange` |
| Tormentas y escenas de iluminación | `special_function` | `light` |
| Acciones de KH Director | `special_function` | `khdirector` |
| Acciones de ION Director | `special_function` | `iondirector` |
| Información del sistema, por ejemplo firmware, número de serie, etc. | `system` | `info` |
| Información de diagnóstico, por ejemplo última actualización, etc. | `diagnostic` | `info` |

### 11.2 Ejemplo con Auto-Entities

Con la tarjeta opcional para paneles [Auto-Entities](https://github.com/thomasloven/lovelace-auto-entities), puedes agrupar automáticamente en una tarjeta las entidades que coincidan con sus atributos. Auto-Entities debe instalarse por separado.

El siguiente ejemplo muestra los estados de todos los canales de conmutación GHL:

```yaml
type: custom:auto-entities
card:
  type: entities
  title: Canales de conmutación GHL
filter:
  include:
    - attributes:
        ghl_resource_type: switch_channel
        ghl_feature_type: state
```

Si hay varios dispositivos GHL configurados, el ejemplo incluye las entidades correspondientes de todos ellos. En ese caso, añade el filtro `device` de Auto-Entities para limitar la selección a un dispositivo concreto. Por ejemplo, añade `device: "Mi acuario"` al mismo nivel de sangría que `attributes` y sustituye «Mi acuario» por el nombre del dispositivo en Home Assistant. `device` es un filtro independiente y no debe colocarse dentro de `attributes`. Encontrarás más opciones de filtrado en la [documentación de Auto-Entities](https://github.com/thomasloven/lovelace-auto-entities#filters).
