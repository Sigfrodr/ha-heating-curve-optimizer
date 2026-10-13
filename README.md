# Optimiseur de courbe de chauffe Viessmann (intégration Home Assistant)

Ajuste automatiquement la **pente** et le **décalage** de la courbe de chauffe d'une
chaudière Viessmann connectée via ViCare, pour que les pièces atteignent leur consigne avec la
température de départ la plus basse possible (meilleure condensation, cycles brûleur plus longs).

## Principe

1. Toutes les 10 min, l'intégration enregistre T° extérieure, T° ambiante et consigne, **uniquement**
   en régime stable : programme surveillé actif depuis ≥ 2 h, chauffage actif, T° ext. < 16 °C,
   et pas de grand soleil (filtre solaire : hauteur du soleil + couverture nuageuse de la météo).
   Si ViCare ne renvoie pas la consigne courante, elle est lue sur l'entité `number` du programme
   actif (`comfortEnergySaving` → température de confort, etc.).
2. **Mode multi-pièces** (thermostats Better Thermostat / Versatile Thermostat) : l'écart retenu est
   celui de la pièce la plus difficile à chauffer. Parmi les pièces qui demandent de la chaleur, la plus
   froide décide ; quand plus aucune ne demande, la marge de la moins chaude permet de baisser la courbe.
   Les pièces fenêtre ouverte sont ignorées.
3. Chaque nuit (04:00), les mesures sont regroupées par tranche de 1 K de T° extérieure, puis la
   formule de courbe Viessmann donne la correction de départ nécessaire, ajustée par moindres carrés :
   - écart identique partout → **décalage** ;
   - écart qui dépend de la T° extérieure → **pente** (seulement si la T° ext. a varié d'au moins 5 K).
4. Garde-fous : 50 % de la correction seulement, ±0,1 de pente et ±3 K de décalage max par jour,
   bornes min/max, tolérance de 0,3 K, écrêtage des écarts aberrants.
5. Après un ajustement, les mesures sont remises à zéro (elles décrivaient l'ancienne courbe).

## Pilotage de la consigne (désactivé / simulation / actif)

ViCare ne permet ni de modifier le planning de la chaudière ni de forcer un programme : le pilote agit
sur la **consigne du programme actif**, comme l'appli ViCare. Il applique :

- un **planning hebdomadaire** édité dans le panneau (grille par pas de 30 min), importable depuis les
  plannings des têtes thermostatiques ;
- la **veille sur demande** : en période confort, consigne de veille (15 °C par défaut) quand aucune pièce
  ne demande de chaleur depuis 20 min, retour immédiat dès qu'une pièce réclame ;
- la **relance optimale** : vitesse de remontée apprise sur les relances passées, corrigée par la
  **prévision météo** (froid annoncé → relance plus tôt) ;
- l'**anticipation solaire** : consigne baissée d'1 °C quand un soleil franc est prévu.

En **simulation**, le pilote calcule et affiche ses décisions sans rien écrire. En **actif**, les consignes
d'origine des programmes sont mémorisées et remises au retour en simulation / désactivé.
Garde-fous : 5 min minimum entre deux écritures, 48 écritures par jour au plus.

## Panneau « Courbe de chauffe »

Panneau dans la barre latérale (administrateurs), avec bandeau d'alerte et sept onglets :

| Onglet | Contenu |
|---|---|
| **Courbe** | Courbe actuelle + proposition / réglage en cours, zone de condensation (départ < 55 °C), départ mesuré, réglage manuel avec aperçu, écarts par T° extérieure, historique |
| **Planning** | Mode de pilotage, consigne calculée et raison, grille hebdomadaire, import depuis les têtes, frise des décisions sur 48 h |
| **Pièces** | Ambiance / consigne / demande de chaleur de chaque pièce suivie, part du temps où chaque pièce est limitante |
| **Économies** | Gaz de chauffage par degré-jour (base 18 °C) sur 60 jours, coût en €, économie estimée depuis le dernier ajustement ; analyse des relances du matin après réduit |
| **Chaudière** | Démarrages et durée de cycle du brûleur, part du temps en condensation (7 j), pression d'eau, démarrages par jour |
| **Eau chaude** | Consigne, ballon, part du gaz, recommandation 50 °C, montée anti-légionelle hebdomadaire |
| **Diagnostic** | Déperditions de la maison (W/K) par saison de chauffe, équilibrage des radiateurs (puissance apprise par Better Thermostat), aperçu et envoi du bilan hebdomadaire |

**Carte de tableau de bord** : ajouter une carte « Courbe de chauffe » (type `custom:heating-curve-card`) pour
l'état, l'écart, le pilotage, les alertes, et les boutons Évaluer / Ajustement auto.

API websocket : `heating_curve_optimizer/get`, `/set_curve`, `/recoveries`, `/set_control_mode`,
`/set_schedule`, `/diagnostics`, `/weekly_report`.
L'icône est fournie localement dans `brand/` (HA ≥ 2026.3), générée par `tools/make_icon.py`.

## Entités créées

| Entité | Rôle |
|---|---|
| `switch.…_ajustement_automatique` | **Éteint = simulation** (propositions en notification). Allumé = applique les ajustements. |
| `switch.…_montee_anti_legionelle_hebdomadaire` | Monte l'eau chaude à 60 °C une fois par semaine puis remet la consigne |
| `button.…_evaluer_maintenant` | Évaluation immédiate |
| `binary_sensor.…_alerte_chaudiere` | Pression basse, chaudière injoignable, antigel, cycles courts (avec notification) |
| `sensor.…_etat` | État (collecte, en attente, proposition…) + dernière proposition en attributs |
| `sensor.…_ecart_moyen_ambiance_consigne` | Écart moyen retenu sur les mesures en cours |
| `sensor.…_echantillons` | Nombre de mesures collectées |
| `sensor.…_demarrages_bruleur_24_h` | Démarrages du brûleur sur 24 h |
| `sensor.…_duree_moyenne_de_cycle_bruleur_24_h` | Minutes de flamme par démarrage sur 24 h |
| `select.…_pilotage_de_la_consigne` | Désactivé / Simulation / Actif |
| `sensor.…_consigne_pilotee` | Consigne calculée par le pilote (mode et raison en attributs) |

Réglages : Paramètres › Appareils et services › Optimiseur de courbe de chauffe › Configurer
(sections Pièces et météo, Pilotage, Coûts et rapport hebdomadaire, Alertes, Eau chaude, Algorithme).
Renseigner le **prix du kWh de gaz** et la conversion m³ → kWh de la facture pour des coûts justes.

## Installation / mise à jour

- **HACS** (dépôt personnalisé, catégorie Intégration) : le dépôt contient `hacs.json`.
- **Manuel** : copier `custom_components/heating_curve_optimizer/` dans `/config/custom_components/`,
  puis redémarrer Home Assistant. Un changement limité au panneau (`frontend/`) ne demande qu'un rechargement de la page.

## Points d'attention

- **Robinets thermostatiques** de la pièce de la sonde chaudière : les ouvrir à fond.
- ViCare écrit pente et décalage dans le même appel en relisant l'autre valeur dans son cache :
  quand les deux changent, la pente est écrite, puis le décalage une fois la nouvelle pente relue.
- La durée de cycle est approximative : ViCare compte les heures brûleur en heures entières.
- La condensation est estimée sur la température de **départ** (pas de sonde de retour).

## Tests

```bash
# Tests unitaires (n'importe quel Python 3.12+)
python -m pytest tests
# Tests unitaires + intégration Home Assistant (Linux ou WSL : le harnais HA exige Linux)
bash tools/ha-tests.sh
```

## Licence

MIT, voir [LICENSE](LICENSE).
