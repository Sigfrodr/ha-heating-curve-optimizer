# Optimiseur de courbe de chauffe Viessmann (intégration Home Assistant)

Ajuste automatiquement la **pente** et le **décalage** de la courbe de chauffe d'une
chaudière Viessmann connectée via ViCare, pour que la température ambiante colle à la
consigne avec la température de départ la plus basse possible (meilleure condensation).

## Principe

1. Toutes les 10 min, l'intégration enregistre T° extérieure, T° ambiante et consigne, **uniquement**
   en régime stable (programme surveillé actif depuis ≥ 2 h, chauffage actif, T° ext. < 16 °C).
   Si ViCare ne renvoie pas la consigne courante, elle est lue sur l'entité `number` du programme
   actif (`comfortEnergySaving` → température de confort, etc.).
2. Chaque nuit (04:00), les mesures sont regroupées par tranche de 1 K de T° extérieure et
   l'écart médian ambiance − consigne est calculé pour chaque tranche.
3. À partir de la formule de courbe Viessmann, on en déduit la correction de départ
   nécessaire, puis on ajuste par moindres carrés :
   - écart identique partout → **décalage** ;
   - écart qui dépend de la T° extérieure → **pente** (seulement si la T° ext. a varié d'au moins 5 K).
4. Garde-fous : 50 % de la correction seulement, ±0,1 de pente et ±3 K de décalage max par jour,
   bornes min/max, tolérance de 0,3 K, écrêtage des écarts aberrants.
5. Après un ajustement, l'historique est vidé (il décrivait l'ancienne courbe) et la collecte
   reprend après 2 h de stabilisation.

## Panneau « Courbe de chauffe »

Un panneau dédié apparaît dans la barre latérale (administrateurs) :

- état de l'optimiseur, bascule **Simulation / Ajustement automatique**, bouton **Évaluer maintenant** ;
- indicateurs en direct : ambiance, écart moyen, extérieur, départ mesuré vs calculé, courbe, brûleur ;
- **graphique de la courbe** actuelle avec la proposition ou le réglage en cours superposé, et le point de départ mesuré ;
- **réglage manuel** pente / décalage avec aperçu de l'effet à -10, 0 et 10 °C avant application ;
- **graphique des écarts** ambiance − consigne par température extérieure (mesures + médianes), progression de la collecte ;
- historique des ajustements.

Le panneau utilise l'API websocket `heating_curve_optimizer/get` et `heating_curve_optimizer/set_curve`.
L'icône de l'intégration est fournie localement dans `brand/` (HA ≥ 2026.3), générée par `tools/make_icon.py`.

## Entités créées

| Entité | Rôle |
|---|---|
| `switch.optimiseur_courbe_de_chauffe_ajustement_automatique` | **Éteint = simulation** (propositions en notification). Allumé = applique les ajustements. |
| `button.optimiseur_courbe_de_chauffe_evaluer_maintenant` | Évaluation immédiate |
| `sensor.optimiseur_courbe_de_chauffe_etat` | État (collecte, en attente, proposition…) + dernière proposition en attributs |
| `sensor.optimiseur_courbe_de_chauffe_ecart_moyen_ambiance_consigne` | Écart moyen sur les mesures en cours |
| `sensor.optimiseur_courbe_de_chauffe_echantillons` | Nombre de mesures collectées |

Réglages : Paramètres > Appareils et services > Optimiseur de courbe de chauffe > Configurer.

## Installation / mise à jour

Copier `custom_components/heating_curve_optimizer/` dans `/config/custom_components/`
puis ajouter l'intégration « Optimiseur de courbe de chauffe » (les entités ViCare sont pré-remplies).

## Points d'attention

- **Robinets thermostatiques** de la pièce où se trouve la sonde : les ouvrir à fond.
- ViCare écrit pente et décalage dans le même appel en relisant l'autre valeur dans son cache :
  quand les deux changent, la pente est écrite, puis le décalage une fois la nouvelle pente relue.
- Quota API ViCare : 1 à 2 écritures par jour seulement.

## Tests (hors HA)

```bash
python -m pytest tests
```
