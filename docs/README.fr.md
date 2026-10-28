[English](../README.md) · [Deutsch](README.de.md) · **Français** (traduction automatique) · [Español](README.es.md) (traduction automatique)

<p align="center">
  <img src="https://raw.githubusercontent.com/PC-Supporting-GmbH/HomeAssistant-GHL/master/docs/images/logo.png" alt="Intégration GHL pour Home Assistant" width="250">
</p>

<h1 align="center">GHL</h1>

<p align="center">
  Une intégration personnalisée pour Home Assistant destinée à certains contrôleurs d’aquarium et luminaires GHL.
</p>

---

## Présentation

Cette intégration personnalisée connecte directement les appareils GHL compatibles à Home Assistant à l’aide de l’API GHL.

Selon l’appareil connecté et les fonctionnalités fournies par l’API GHL, l’intégration peut rendre disponibles des mesures, des états, des commandes et des actions dans Home Assistant.

Les données et fonctions GHL peuvent ainsi être utilisées dans les tableaux de bord, les automatisations et les autres fonctionnalités de Home Assistant.

<p align="center">
  <img src="https://raw.githubusercontent.com/PC-Supporting-GmbH/HomeAssistant-GHL/master/docs/images/ghl-dashboard-example.png" alt="Intégration GHL dans Home Assistant" width: "75%">
</p>

## Avertissement

Il s’agit d’une intégration non officielle pour Home Assistant. Elle n’est ni développée, ni maintenue, ni prise en charge par GHL.

L’intégration est développée à titre privé et fournie en l’état.

L’intégration peut uniquement rendre disponibles les fonctionnalités accessibles par l’API officielle GHL. Les fonctions ou informations non fournies par l’API GHL ne peuvent pas être rendues disponibles par cette intégration.

Pour en savoir plus sur l’API GHL et ses possibilités : https://www.aquariumcomputer.com/software/ghl-api/

> [!WARNING]
> Cette intégration est en cours de développement.

> [!TIP]
>
> Si cette intégration vous est utile et que vous souhaitez soutenir son développement
>

<p align="center">
  <a href="https://www.buymeacoffee.com/HA.GHL.Integration" target="_blank"><img height="60" src="https://raw.githubusercontent.com/PC-Supporting-GmbH/HomeAssistant-GHL/master/docs/images/buymeacoffee.png" alt="Intégration GHL dans Home Assistant"></a>
</p>

## Appareils compatibles

Les séries d’appareils GHL suivantes sont prises en charge :

- Série ProfiLux 4 (y compris Industrial Line / IL)
- Série Mitras LX8
- Série Mitras LX7 (y compris Industrial Line / IL)

Les versions de micrologiciel suivantes sont requises :

- ProfiLux 4 : micrologiciel 7.52
- Mitras LX7 : micrologiciel 1.22
- Mitras LX8 : micrologiciel 2.05

La prise en charge par cette intégration est limitée aux fonctionnalités fournies par l’API GHL pour l’appareil concerné.

> [!NOTE]
> La version de l’API actuellement utilisée par cette intégration est **1.1**.

## Installation

### HACS

L’installation via HACS est recommandée.

[![Ouvrez votre instance Home Assistant et ce dépôt dans le Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=PC-Supporting-GmbH&repository=HomeAssistant-GHL&category=integration)

Après avoir ajouté le dépôt à HACS :

1. Installez l’intégration **GHL**.
2. Redémarrez Home Assistant.
3. Accédez à **Paramètres → Appareils et services**.
4. Sélectionnez **Ajouter une intégration**.
5. Recherchez **GHL**.

### Installation manuelle

Vous pouvez également télécharger la dernière version depuis GitHub.

Copiez le dossier `pcs_ghl` situé dans `custom_components` dans le répertoire `custom_components` de votre installation Home Assistant.

Redémarrez ensuite Home Assistant et ajoutez l’intégration depuis :

**Paramètres → Appareils et services → Ajouter une intégration → GHL**

## Activer l’API GHL

L’API GHL est désactivée par défaut et doit être activée pour que Home Assistant puisse communiquer avec l’appareil.

Activez l’accès à l’API dans **GHL Control Center → System → GHL API**.

Pour bénéficier de toutes les fonctionnalités de cette intégration, notamment l’écriture de valeurs et le lancement d’actions, sélectionnez :

**GHL API is enabled, full access read and write**

L’accès à l’API en lecture seule est également pris en charge. Toutefois, les fonctions nécessitant un accès en écriture, comme le démarrage ou l’arrêt des modes de maintenance ou des pauses de nourrissage, ne sont pas disponibles lorsque l’API est configurée en lecture seule.

<p align="center">
  <img src="https://raw.githubusercontent.com/PC-Supporting-GmbH/HomeAssistant-GHL/master/docs/images/ghl-api-settings.png" alt="Paramètres de l’API GHL dans GHL Control Center">
</p>

Après une mise à jour du micrologiciel, il peut être nécessaire de réactiver l’API GHL. Si l’intégration ne parvient plus à communiquer avec l’appareil après une mise à jour, vérifiez d’abord ce réglage.

Pour en savoir plus sur l’activation de l’API GHL :

https://www.aquariumcomputer.com/software/ghl-api/

## Configuration

Lorsque vous ajoutez l’intégration à Home Assistant, saisissez les informations réseau de votre appareil GHL et sélectionnez le mode d’accès à l’API souhaité.

L’intégration se connecte à l’appareil et détecte les ressources GHL prises en charge.

L’API GHL ne fournissant pas le type des capteurs connectés, l’intégration vous demande d’attribuer le type approprié aux capteurs détectés lors de la configuration initiale.

Après la configuration initiale, des options supplémentaires sont disponibles dans :

**Paramètres → Appareils et services → GHL → Configurer**

## Options

L’intégration propose des options supplémentaires après la configuration initiale.

> [!NOTE]
> Certaines options ne sont disponibles qu’après une connexion réussie à l’appareil GHL et une fois l’intégration chargée.

### Paramètres généraux

Les paramètres de connexion peuvent être modifiés si nécessaire.

Le mode d’accès à l’API peut également être basculé entre lecture seule et lecture/écriture.

#### Afficher toutes les ressources disponibles

Cette option est disponible après la première configuration de l’intégration.

Par défaut, l’intégration utilise la configuration de l’appareil pour éviter d’afficher les ressources GHL qui semblent inutilisées.

L’activation de cette option affiche également les ressources prises en charge qui seraient normalement détectées comme inutilisées et donc masquées d’après la configuration de l’appareil.

Cela peut être utile si vous souhaitez délibérément afficher dans Home Assistant toutes les ressources prises en charge signalées par l’appareil GHL.

#### Importer les données historiques des nouveaux capteurs

Activez cette option pour importer automatiquement les données historiques lorsque des capteurs ou sources compatibles sont détectés et configurés pour la première fois. L’activation ultérieure de cette option n’importe pas automatiquement les données des sources déjà présentes.

### Configuration des capteurs

Les types de capteurs attribués lors de la configuration initiale peuvent être modifiés ultérieurement dans les options de l’intégration.

Cela permet de corriger ou d’adapter la configuration des capteurs sans supprimer puis reconfigurer l’intégration.

### Détecter de nouveaux capteurs/appareils

Après avoir ajouté des capteurs ou des appareils à votre système GHL, sélectionnez l’option de détection de nouveaux capteurs/appareils dans les options de l’intégration.
Cela recharge l’intégration et relance la détection des ressources. Il n’est pas nécessaire de redémarrer Home Assistant. Un type devra éventuellement être attribué aux nouveaux capteurs détectés.

### Importation des données historiques

Pour importer manuellement les données stockées pour toutes les sources actuellement disponibles et compatibles, sélectionnez **Données historiques : importer maintenant** dans les options de l’intégration.
Les capteurs sans type attribué ou configurés comme masqués sont exclus. La détection des doublons contribue à éviter que les mêmes données historiques soient importées plusieurs fois.
L’importation d’un grand volume de données stockées peut prendre plusieurs minutes.

## Modifier des valeurs depuis Home Assistant

Certaines valeurs et descriptions fournies par l’API GHL peuvent être modifiées directement depuis l’interface de Home Assistant.

La modification des valeurs nécessite un accès en écriture à la fois sur l’appareil GHL et dans l’intégration. En lecture seule, les consignes des capteurs sont affichées, mais les modifications sont refusées avec un message correspondant. La commande de luminosité générale n’est pas disponible en lecture seule.

Une **carte Entités** est recommandée pour ces commandes.

### Consignes des capteurs

Modifiez la valeur dans le champ de consigne du capteur souhaité. La valeur est envoyée directement à l’appareil GHL. Cela s’applique également aux consignes compatibles des KH Director et ION Director.

### Luminosité générale

Modifiez la luminosité générale (0–100 %). La valeur est envoyée directement à l’appareil GHL.

### Descriptions

Les descriptions des éléments GHL compatibles peuvent également être modifiées directement depuis Home Assistant.

Pour modifier une description :

1. Sélectionnez l’élément GHL souhaité.
2. Saisissez la nouvelle description dans le champ **Description**.
3. Appuyez sur **Écrire la description**.

Aucune automatisation Home Assistant n’est nécessaire. Vous pouvez toutefois en utiliser une.

## Limitations actuelles

L’intégration est limitée par les fonctionnalités et les informations fournies par l’API GHL.

Les limitations actuellement connues sont les suivantes :

- **Les types de capteurs ne peuvent pas être lus via l’API GHL.**  
  Le type de capteur doit donc être attribué séparément lors de la configuration initiale. Cette attribution peut ensuite être modifiée dans les options de l’intégration.

- **Les minuteries ne sont pas importées actuellement.**  
  L’API GHL fournit leur description, mais pas leurs horaires de commutation. Leur importation apporterait donc actuellement peu de fonctionnalités utiles dans Home Assistant.

## Problèmes et demandes de fonctionnalités

Si vous rencontrez un problème ou avez une idée pour améliorer l’intégration, veuillez utiliser les formulaires d’issues GitHub.

**Signalements de bugs :**  
https://github.com/PC-Supporting-GmbH/HomeAssistant-GHL/issues/new?template=bug_report.yml

**Demandes de fonctionnalités :**  
https://github.com/PC-Supporting-GmbH/HomeAssistant-GHL/issues/new?template=feature_request.yml

Avant d’ouvrir une nouvelle issue, vérifiez si le même problème ou la même demande a déjà été signalé.
