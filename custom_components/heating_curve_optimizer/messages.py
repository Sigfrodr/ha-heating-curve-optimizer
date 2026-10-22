"""Traduction des messages générés (états, raisons, alertes, conseils, rapports).

Le code produit ses messages en français ; ils sont traduits en sortie (notifications,
états d'entités, données du panneau) selon la langue de Home Assistant. Chaque modèle
français peut contenir des variables {nom} ; leurs valeurs sont elles-mêmes traduites
(une raison à l'intérieur d'un résumé, une liste d'alertes séparées par « ; »).
"""

from __future__ import annotations

import re

CATALOG: dict[str, dict[str, str]] = {
    "en": {
        # états
        "démarrage": "starting",
        "climate indisponible": "climate unavailable",
        "chauffage arrêté": "heating off",
        "programme {p} non surveillé": "program {p} not monitored",
        "mesure manquante": "missing measurement",
        "T° ext. ≥ {t} °C": "outdoor ≥ {t} °C",
        "stabilisation (programme/consigne)": "settling (program/setpoint change)",
        "stabilisation (après ajustement)": "settling (after an adjustment)",
        "pilotage hors confort (mesure ignorée)": "pilot outside comfort (sample skipped)",
        "gains solaires (mesure ignorée)": "solar gains (sample skipped)",
        "sonde d'ambiance figée (mesure ignorée)": "room sensor frozen (sample skipped)",
        "collecte (sonde de référence)": "collecting (reference sensor)",
        "collecte": "collecting",
        "chauffage inactif (mesure ignorée)": "heating not running (sample skipped)",
        "en attente de données ({n}/{m})": "waiting for data ({n}/{m})",
        "pente/décalage indisponibles": "slope/shift unavailable",
        "évalué, rien à changer": "evaluated, nothing to change",
        "proposition (simulation)": "proposal (dry run)",
        "ajustement appliqué": "adjustment applied",
        # notifications
        "Chaudière : alerte": "Boiler: alert",
        "Courbe de chauffe : proposition": "Heating curve: proposal",
        "Courbe de chauffe ajustée": "Heating curve adjusted",
        "Courbe de chauffe": "Heating curve",
        "Chauffage : bilan de la semaine": "Heating: weekly report",
        "Appliquer": "Apply",
        "Ignorer": "Ignore",
        "Pente non confirmée par ViCare, décalage non appliqué.": "Slope not confirmed by ViCare, shift not applied.",
        "Pente {a} → {b}, décalage {c} → {d} (écart moyen {e} K, {n} échantillons). {reason}.":
            "Slope {a} → {b}, shift {c} → {d} (mean deviation {e} K, {n} samples). {reason}.",
        "Pente {a} → {b}, décalage {c} → {d} ({reason}).": "Slope {a} → {b}, shift {c} → {d} ({reason}).",
        # raisons des propositions
        "pas assez de données exploitables": "not enough usable data",
        "écart dans la tolérance": "deviation within tolerance",
        "ajustement pente + décalage (amplitude ext. {x} K)": "slope and shift adjustment (outdoor range {x} K)",
        "ajustement du décalage seul (amplitude ext. {x} K insuffisante pour la pente)":
            "shift-only adjustment (outdoor range {x} K too narrow for the slope)",
        "correction inférieure à la résolution du régulateur": "correction below the controller resolution",
        "réglage manuel": "manual setting",
        "proposition validée manuellement": "proposal approved manually",
        "proposition validée depuis le téléphone": "proposal approved from the phone",
        # alertes
        "Pression d'eau basse : {p} bar (minimum {m} bar). Remettre de l'eau dans le circuit.":
            "Low water pressure: {p} bar (minimum {m} bar). Top up the heating circuit.",
        "Chaudière injoignable via ViCare depuis {n} min.": "Boiler unreachable through ViCare for {n} min.",
        "Protection antigel de la chaudière active.": "Boiler frost protection is active.",
        "Température ambiante figée à {v} °C depuis {h} h alors que le brûleur a démarré {n} fois : "
        "thermostat d'ambiance à vérifier (le redémarrer s'il est éteint). Les mesures sont ignorées en attendant.":
            "Room temperature stuck at {v} °C for {h} h while the burner started {n} times: check the room "
            "thermostat (restart it if it is off). Samples are skipped meanwhile.",
        "Sonde d'ambiance à {a} °C, sonde de référence à {b} °C depuis {n} min : thermostat d'ambiance à vérifier. "
        "La sonde de référence prend le relais pour les mesures.":
            "Room sensor at {a} °C, reference sensor at {b} °C for {n} min: check the room thermostat. "
            "The reference sensor takes over for samples.",
        "Surchauffe ({r} °C mesurés par la sonde de référence) avec une sonde d'ambiance défaillante : "
        "consignes de la chaudière abaissées à {s} °C jusqu'au retour de la sonde.":
            "Overheating ({r} °C on the reference sensor) with a faulty room sensor: boiler setpoints lowered "
            "to {s} °C until the sensor recovers.",
        "Cycles courts : {a} démarrages en {b} h, {c} min de flamme en moyenne par démarrage.":
            "Short cycling: {a} burner starts in {b} h, {c} min of flame per start on average.",
        "La pression baisse lentement ({t} bar/semaine sur 4 semaines) : petite fuite ou vase d'expansion à vérifier.":
            "Pressure is slowly dropping ({t} bar/week over 4 weeks): check for a small leak or the expansion vessel.",
        "Entretien annuel de la chaudière dépassé (échéance {d}).": "Annual boiler service overdue (due {d}).",
        "Entretien annuel de la chaudière à prévoir (échéance {d}).": "Annual boiler service coming up (due {d}).",
        "Consommation d'hier {x} % au-dessus de la normale pour la météo ({a} kWh au lieu de {b}) : "
        "fenêtre ouverte, réglage, encrassement ?":
            "Yesterday's consumption was {x} % above normal for the weather ({a} kWh instead of {b}): "
            "open window, settings, fouling?",
        # relance du matin
        "Aucune relance après réduit détectée : la chaudière ne passe peut-être jamais en réduit.":
            "No morning recovery detected: the boiler may never switch to reduced mode.",
        "La consigne n'est souvent pas atteinte après la relance : avancer l'heure de relance ou remonter la consigne réduite.":
            "The setpoint is often not reached after recovery: start earlier or raise the reduced setpoint.",
        "Relance longue ({m} min en médiane) : avancer la relance d'environ {a} min ou remonter la consigne réduite d'1 °C.":
            "Long recovery ({m} min median): start about {a} min earlier or raise the reduced setpoint by 1 °C.",
        "La maison perd peu la nuit ({d} K) et remonte vite ({m} min) : on peut baisser la consigne réduite d'1 °C ou retarder la relance pour économiser.":
            "The house loses little heat at night ({d} K) and recovers fast ({m} min): lower the reduced setpoint by 1 °C or start later to save energy.",
        "Réduit bien réglé : {d} K perdus la nuit, consigne atteinte en {m} min.":
            "Night setback well tuned: {d} K lost overnight, setpoint reached in {m} min.",
        # décisions du pilote
        "relance anticipée : {a} min de chauffe estimées, confort dans {b} min":
            "early start: {a} min of heating estimated, comfort in {b} min",
        "période réduite du planning": "reduced period of the schedule",
        "aucune pièce ne demande de chaleur depuis {n} min": "no room has called for heat for {n} min",
        "soleil franc attendu : on le laisse chauffer": "strong sun expected: letting it heat the house",
        "période confort du planning": "comfort period of the schedule",
        "chaudière à l'arrêt (vacances ou veille) : pilotage en pause":
            "boiler switched off (holiday or standby): pilot paused",
        # équilibrage
        "chauffe bien plus vite que les autres : refermer un peu son té de réglage":
            "heats much faster than the others: close its lockshield valve a little",
        "chauffe bien plus lentement : ouvrir son té de réglage, purger, ou radiateur trop petit":
            "heats much more slowly: open its lockshield valve, bleed it, or the radiator is too small",
        "équilibrée": "balanced",
        "Compteur Linky": "Linky meter",
        "Conso API refuse le jeton (expiré ou révoqué) : renouvelle-le sur conso.boris.sh, puis colle-le "
        "dans l'onglet Réglages du panneau.":
            "Conso API rejects the token (expired or revoked): renew it on conso.boris.sh, then paste it "
            "in the panel's Settings tab.",
        "plages qui se chevauchent": "overlapping slots",
        "Planning de la chaudière indisponible (intégration ViCare non chargée ?)":
            "Boiler schedule unavailable (ViCare integration not loaded?)",
        "Budget d'écritures ViCare atteint : réessaie plus tard": "ViCare write budget reached: try again later",
        "La chaudière n'accepte pas l'écriture du planning": "The boiler does not accept schedule writes",
        "ViCare a refusé le planning : {err}": "ViCare rejected the schedule: {err}",
        "à confirmer : la cuisson ou une autre source de chaleur peut gonfler la mesure":
            "to be confirmed: cooking or another heat source can inflate the measurement",
        # rapport hebdomadaire
        "Gaz chauffage : {x} m³ (≈ {y} €).": "Heating gas: {x} m³ (≈ €{y}).",
        "Gaz chauffage : {x} m³.": "Heating gas: {x} m³.",
        "{r} m³ par degré-jour ({p} % par rapport à la semaine précédente).": "{r} m³ per degree-day ({p} % vs previous week).",
        "{r} m³ par degré-jour.": "{r} m³ per degree-day.",
        "Ajustements de courbe : {n}.": "Curve adjustments: {n}.",
        "Chaudière mise en veille faute de demande : {h} h.": "Boiler in standby for lack of demand: {h} h.",
        "Alertes : aucune.": "Alerts: none.",
        "Budget d'écritures ViCare atteint ({n}/{b} sur 24 h) : plus de changement de consigne avant demain, "
        "pour ne pas dépasser le quota Viessmann.":
            "ViCare write budget reached ({n}/{b} over 24 h): no more setpoint changes until tomorrow, "
            "to stay within the Viessmann quota.",
        "Alertes : {list}.": "Alerts: {list}.",
    }
}

_compiled: dict[str, list[tuple[re.Pattern, str]]] = {}


def _patterns(lang: str) -> list[tuple[re.Pattern, str]]:
    if lang not in _compiled:
        entries = []
        for fr, other in CATALOG.get(lang, {}).items():
            regex = re.escape(fr)
            regex = re.sub(r"\\\{(\w+)\\\}", r"(?P<\1>.+?)", regex)
            entries.append((re.compile(f"^{regex}$", re.S), other))
        # les modèles les plus longs d'abord : un modèle générique ne masque pas un plus précis
        entries.sort(key=lambda e: -len(e[0].pattern))
        _compiled[lang] = entries
    return _compiled[lang]


def translate(text: str, language: str | None) -> str:
    """Texte traduit dans la langue de HA (français ou inconnu : inchangé)."""
    lang = (language or "fr")[:2].lower()
    if lang == "fr" or not text or lang not in CATALOG:
        return text
    if "\n" in text:
        return "\n".join(translate(line, language) for line in text.split("\n"))
    for pattern, template in _patterns(lang):
        match = pattern.match(text)
        if match:
            values = {
                key: "; ".join(translate(part, language) for part in value.split("; "))
                for key, value in match.groupdict().items()
            }
            return template.format(**values)
    return text
