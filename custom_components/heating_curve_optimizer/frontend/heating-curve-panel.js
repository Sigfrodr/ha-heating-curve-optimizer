// Panneau « Courbe de chauffe » — composant web autonome (sans dépendance).
const DOMAIN = "heating_curve_optimizer";
const X_MIN = -15;
const X_MAX = 20;
const CHART_H = 300;
const MARGIN = { l: 44, r: 16, t: 14, b: 30 };
const SERIES = {
  light: { s1: "#2a78d6", s2: "#eb6834", s3: "#1baf7a", s4: "#eda100" },
  dark: { s1: "#3987e5", s2: "#d95926", s3: "#199e70", s4: "#c98500" },
};

// --- Traductions (clé = texte français, {nom} = valeur insérée) ----------------
let LANG = "fr";
let LOCALE = "fr-FR";
const EN = {
  // Général / barre d'état
  "Courbe de chauffe": "Heating curve",
  "Chargement…": "Loading…",
  "Impossible de charger les données": "Unable to load data",
  "Programme {p} · évaluation chaque jour à {h}": "Program {p} · evaluated daily at {h}",
  "pilotage actif : {mode} {v} °C": "setpoint pilot active: {mode} {v} °C",
  "pilotage simulé : {mode} {v} °C": "setpoint pilot dry run: {mode} {v} °C",
  "Ajustement automatique": "Automatic adjustment",
  "Simulation": "Dry run",
  "la courbe est modifiée chaque nuit": "the curve is adjusted every night",
  "propose sans rien modifier": "suggests without changing anything",
  "Évaluer maintenant": "Evaluate now",
  "Alerte chaudière": "Boiler alert",
  "confort": "comfort",
  "réduit": "reduced",
  "veille": "standby",
  "relance": "recovery",
  "soleil": "sun",
  // Onglets
  "Courbe": "Curve",
  "Planning": "Schedule",
  "Pièces": "Rooms",
  "Économies": "Savings",
  "Chaudière": "Boiler",
  "Eau chaude": "Hot water",
  "Diagnostic": "Diagnostics",
  // Actions, confirmations et messages
  "Activer l'ajustement automatique ?\n\nChaque nuit, l'optimiseur modifiera lui-même la courbe de la chaudière (au plus ±{slope} de pente et ±{shift} K de décalage).":
    "Enable automatic adjustment?\n\nEvery night, the optimizer will change the boiler's heating curve by itself (at most ±{slope} slope and ±{shift} K shift).",
  "Ajustement automatique activé": "Automatic adjustment enabled",
  "Mode simulation : plus aucune modification automatique": "Dry run mode: no more automatic changes",
  "Évaluation lancée": "Evaluation started",
  "Montée anti-légionelle hebdomadaire activée": "Weekly anti-legionella boost enabled",
  "Montée anti-légionelle désactivée": "Anti-legionella boost disabled",
  "Régler la consigne d'eau chaude sur {v} °C ?": "Set the hot water setpoint to {v} °C?",
  "Consigne d'eau chaude envoyée : {v} °C": "Hot water setpoint sent: {v} °C",
  "Activer le pilotage ?\n\nLe pilote écrira la consigne du programme actif de la chaudière (planning, veille sans demande, relance anticipée). Les consignes d'origine sont mémorisées et remises si tu repasses en Désactivé ou Simulation.":
    "Enable the setpoint pilot?\n\nThe pilot will write the setpoint of the boiler's active program (schedule, standby when there is no demand, early morning recovery). The original setpoints are saved and restored if you switch back to Off or Dry run.",
  "Pilotage désactivé": "Setpoint pilot off",
  "Pilotage en simulation": "Setpoint pilot in dry run",
  "Pilotage actif": "Setpoint pilot active",
  "Échec : {msg}": "Failed: {msg}",
  "Planning enregistré": "Schedule saved",
  "Planning des têtes importé : vérifie puis enregistre": "Thermostatic head schedule imported: check it, then save",
  "Consignes des pièces enregistrées": "Room setpoints saved",
  "Enregistrer un entretien au {date} ?": "Record a service on {date}?",
  "Enregistrer un entretien aujourd'hui ?": "Record a service today?",
  "Entretien enregistré": "Service recorded",
  "Ne plus collecter de mesures au-dessus de {v} °C extérieur ?": "Stop collecting measurements above {v} °C outdoor?",
  "Seuil enregistré (l'intégration se recharge)": "Threshold saved (the integration is reloading)",
  "Bilan envoyé": "Report sent",
  "Appliquer sur la chaudière ?\n\nPente {s0} → {s1}\nDécalage {h0} → {h1}": "Apply to the boiler?\n\nSlope {s0} → {s1}\nShift {h0} → {h1}",
  "\n\nLa pente est écrite tout de suite, le décalage environ 5 min après (contrainte ViCare).":
    "\n\nThe slope is written immediately, the shift about 5 min later (ViCare limitation).",
  "Pente envoyée, décalage dans ~5 min": "Slope sent, shift in ~5 min",
  "Courbe envoyée à la chaudière": "Curve sent to the boiler",
  // Tuiles
  "Ambiance": "Room",
  "consigne {v} °C": "setpoint {v} °C",
  "Écart moyen mesuré": "Measured mean deviation",
  "{n} mesures en cours": "{n} current measurements",
  "{n} mesure en cours": "{n} current measurement",
  "Extérieur": "Outdoor",
  "chauffe surveillée sous {v} °C": "heating monitored below {v} °C",
  "Départ chaudière": "Boiler flow",
  "courbe à cette T° ext. : {v} °C": "curve at this outdoor temp.: {v} °C",
  "Courbe actuelle": "Current curve",
  "pente · décalage (K)": "slope · shift (K)",
  "Brûleur": "Burner",
  "Allumé": "On",
  "Éteint": "Off",
  "état en direct": "live state",
  // Onglet Courbe
  "Réglage en cours": "Pending setting",
  "Proposition": "Proposal",
  "Température de départ calculée selon la température extérieure (consigne {v} °C)":
    "Flow temperature computed from the outdoor temperature (setpoint {v} °C)",
  "Actuelle (pente {s}, décalage {h})": "Current (slope {s}, shift {h})",
  "{label} (pente {s}, décalage {h})": "{label} (slope {s}, shift {h})",
  "Départ mesuré maintenant": "Flow measured now",
  "Écart ambiance − consigne": "Room − setpoint deviation",
  "Mesures collectées depuis le dernier ajustement, selon la température extérieure":
    "Measurements collected since the last adjustment, by outdoor temperature",
  "Mesure (toutes les 10 min)": "Measurement (every 10 min)",
  "Médiane par tranche de 1 °C": "Median per 1 °C band",
  "Tolérance ±{v} K": "Tolerance ±{v} K",
  "Date": "Date",
  "Pente": "Slope",
  "Décalage": "Shift",
  "Écart moyen": "Mean deviation",
  "Origine": "Origin",
  "Aucun ajustement pour l'instant.": "No adjustments yet.",
  "Historique des ajustements": "Adjustment history",
  "Réglage manuel": "Manual setting",
  "Modifie la courbe et visualise l'effet avant d'appliquer": "Change the curve and preview the effect before applying",
  "inclinaison de la courbe": "steepness of the curve",
  "translation verticale (K)": "vertical offset (K)",
  "Diminuer": "Decrease",
  "Augmenter": "Increase",
  "Température de départ": "Flow temperature",
  "à {ot} °C :": "at {ot} °C:",
  "Appliquer à la chaudière": "Apply to the boiler",
  "Annuler": "Cancel",
  "Un réglage appliqué remet à zéro les mesures en cours : elles décrivaient l'ancienne courbe.":
    "Applying a setting resets the current measurements: they described the old curve.",
  "Pente {s0} → <b>{s1}</b>, décalage {h0} → <b>{h1}</b>": "Slope {s0} → <b>{s1}</b>, shift {h0} → <b>{h1}</b>",
  "écart moyen {v} K": "mean deviation {v} K",
  "Appliquer la proposition": "Apply the proposal",
  "Ajuster avant": "Adjust first",
  "Courbe calculée": "Computed curve",
  "modèle physique des radiateurs": "physical radiator model",
  "Pente <b>{s}</b>, décalage <b>{h}</b>": "Slope <b>{s}</b>, shift <b>{h}</b>",
  "Calculée d'un coup à partir des mesures en cours, extrapolée aux grands froids (écart au modèle {v} K). À vérifier avant d'appliquer.":
    "Computed in one go from the current measurements, extrapolated to very cold weather (model deviation {v} K). Check before applying.",
  "Voir sur le graphique": "Show on the chart",
  "{n} mesures, minimum de {min} atteint : évaluation possible": "{n} measurements, minimum of {min} reached: evaluation possible",
  "{n} / {min} mesures avant la prochaine évaluation": "{n} / {min} measurements before the next evaluation",
  "prêt": "ready",
  "Pente, décalage ou consigne indisponibles pour l'instant.": "Slope, shift or setpoint unavailable for now.",
  "Actuelle": "Current",
  "{v} °C extérieur": "{v} °C outdoor",
  "{label} : {v} °C": "{label}: {v} °C",
  "Courbe de chauffe : température de départ selon la température extérieure": "Heating curve: flow temperature by outdoor temperature",
  "hors chauffe": "no heating",
  "condensation assurée (départ &lt; {v} °C)": "condensing guaranteed (flow &lt; {v} °C)",
  "Pas encore de mesures. La collecte démarre quand il fait moins de {v} °C dehors et que la chaudière est en programme {p} depuis au moins 2 h.":
    "No measurements yet. Collection starts when it is below {v} °C outside and the boiler has been in program {p} for at least 2 h.",
  "Écart médian : {v} K": "Median deviation: {v} K",
  "Écart : {v} K": "Deviation: {v} K",
  "{n} mesures": "{n} measurements",
  "{n} mesure": "{n} measurement",
  "trop chaud": "too warm",
  "trop froid": "too cold",
  "dans la tolérance": "within tolerance",
  "Écart entre température ambiante et consigne selon la température extérieure":
    "Deviation between room temperature and setpoint by outdoor temperature",
  "Pas de données": "No data",
  // Onglet Pièces
  "{name} (sonde chaudière)": "{name} (boiler sensor)",
  "Pièce": "Room",
  "Consigne": "Setpoint",
  "Écart": "Deviation",
  "État": "State",
  "Limitante": "Limiting",
  "arrêt": "off",
  "demande de chaleur": "calling for heat",
  "satisfaite": "satisfied",
  "fenêtre ouverte": "window open",
  "{v} % du temps": "{v} % of the time",
  "La courbe est réglée pour la pièce la plus difficile à chauffer : parmi les pièces qui demandent de la chaleur, c'est la plus froide qui décide. Quand plus aucune ne demande, la marge de la moins chaude permet de baisser la courbe.":
    "The curve is tuned for the hardest room to heat: among the rooms calling for heat, the coldest one decides. When none is calling any more, the margin of the least warm room allows the curve to be lowered.",
  "Mode multi-pièces inactif : seule la sonde de la chaudière est utilisée. Ajoute tes thermostats dans Paramètres › Appareils et services › Optimiseur de courbe de chauffe › Configurer › Pièces et météo.":
    "Multi-room mode inactive: only the boiler sensor is used. Add your thermostats in Settings › Devices & services › Heating curve optimizer › Configure › Rooms and weather.",
  "Pièces suivies": "Monitored rooms",
  "« Limitante » : part des {n} mesures en cours où la pièce a fixé l'écart retenu.":
    "“Limiting”: share of the {n} current measurements in which the room set the retained deviation.",
  "Filtre solaire actif : les mesures prises par grand soleil sont ignorées ({name}).":
    "Solar filter active: measurements taken in strong sunshine are ignored ({name}).",
  // Onglet Économies
  "Chargement des statistiques…": "Loading statistics…",
  "m³ par degré-jour (30 j)": "m³ per degree-day (30 d)",
  "≈ {v} €": "≈ €{v}",
  "gaz chauffage sur 30 j ({p} €/kWh)": "heating gas over 30 d (€{p}/kWh)",
  "{v} €": "€{v}",
  "économie estimée sur 30 j depuis le dernier ajustement": "estimated 30-day saving since the last adjustment",
  "m³/DJU avant le dernier ajustement": "m³/DD before the last adjustment",
  "m³/DJU depuis": "m³/DD since",
  "m³ de gaz par degré-jour (base {b} °C)": "m³ of gas per degree-day (base {b} °C)",
  "Ajustement de la courbe": "Curve adjustment",
  "Aucune consommation de gaz de chauffage sur la période : la saison de chauffe n'a pas encore commencé.":
    "No heating gas consumption over the period: the heating season has not started yet.",
  "{gas} m³ · {dju} DJU (ext. {ext} °C)": "{gas} m³ · {dju} DD (outdoor {ext} °C)",
  "Pas encore assez de jours de chauffe (au moins 2 degrés-jours par jour).": "Not enough heating days yet (at least 2 degree-days per day).",
  "Un degré-jour (DJU) mesure le besoin de chauffage : {b} °C moins la température extérieure moyenne du jour.":
    "A degree-day (DD) measures the heating need: {b} °C minus the day's mean outdoor temperature.",
  "Diviser le gaz par les DJU compare des périodes de météo différente : si le ratio baisse après un ajustement, l'économie est réelle.":
    "Dividing gas by degree-days compares periods with different weather: if the ratio drops after an adjustment, the saving is real.",
  "Tableau Énergie de Home Assistant : sources gaz = consommations ViCare du jour, prix = entité « Prix du gaz » de l'optimiseur.":
    "Home Assistant Energy dashboard: gas sources = ViCare daily consumption, price = the optimizer's “Gas price” entity.",
  "Consommation corrigée de la météo": "Weather-corrected consumption",
  "Gaz de chauffage par degré-jour sur 60 jours": "Heating gas per degree-day over 60 days",
  "Actualiser": "Refresh",
  "Analyse de l'historique…": "Analysing history…",
  "Relance": "Recovery",
  "Baisse la nuit": "Night drop",
  "Ambiance → consigne": "Room → setpoint",
  "Consigne atteinte en": "Setpoint reached in",
  "non atteinte": "not reached",
  "Réduit de nuit": "Night setback",
  "Relances du matin sur les 7 derniers jours (sonde de la chaudière)": "Morning recoveries over the last 7 days (boiler sensor)",
  // Onglet Chaudière
  "{n} démarrages": "{n} starts",
  "{h} h de flamme · {m} min par cycle": "{h} h of flame · {m} min per cycle",
  "Pas encore de statistiques de démarrage.": "No burner start statistics yet.",
  "Cycles courts : la chaudière s'allume et s'éteint souvent. Un départ moins chaud (courbe plus basse) allonge les cycles et améliore le rendement.":
    "Short cycling: the boiler turns on and off often. A cooler flow (lower curve) lengthens the cycles and improves efficiency.",
  "Moins de la moitié du temps de chauffe se fait avec un départ sous {v} °C : baisser la courbe améliorerait la condensation, donc le rendement.":
    "Less than half of the heating time runs with a flow below {v} °C: lowering the curve would improve condensing, and therefore efficiency.",
  "Fonctionnement correct.": "Operating normally.",
  "Les indicateurs se remplissent au fil des heures de chauffe.": "The indicators fill in as heating hours accumulate.",
  "Brûleur et rendement": "Burner and efficiency",
  "Une chaudière à condensation récupère la chaleur des fumées quand l'eau revient froide : un départ sous {v} °C la garantit.":
    "A condensing boiler recovers heat from the flue gases when the water returns cold: a flow below {v} °C guarantees it.",
  "démarrages sur {h} h": "starts over {h} h",
  "de flamme par démarrage": "of flame per start",
  "cycles courts": "short cycling",
  "du temps de chauffe en condensation (7 j)": "of heating time in condensing mode (7 d)",
  "pression d'eau (alerte sous {v} bar)": "water pressure (alert below {v} bar)",
  "Démarrages du brûleur par jour (30 j)": "Burner starts per day (30 d)",
  "Pression d'eau": "Water pressure",
  "Pression minimale de chaque jour. Une baisse lente sur plusieurs semaines signale une petite fuite ou un vase d'expansion à regonfler.":
    "Minimum pressure of each day. A slow drop over several weeks indicates a small leak or an expansion vessel that needs re-pressurising.",
  "par semaine (tendance sur 4 semaines)": "per week (4-week trend)",
  "Pression minimale du jour (bar)": "Daily minimum pressure (bar)",
  "{v} bar au plus bas": "{v} bar at lowest",
  "La pression est relevée chaque jour à partir de maintenant.": "Pressure is recorded every day from now on.",
  "Entretien annuel": "Annual service",
  "Obligatoire chaque année en France pour une chaudière gaz. Un rappel arrive 30 jours avant l'échéance.":
    "Mandatory every year in France for a gas boiler. A reminder arrives 30 days before the due date.",
  "dernier entretien": "last service",
  "dépassé de {n} j": "overdue by {n} d",
  "dans {n} j": "in {n} d",
  "prochaine échéance": "next due date",
  "de brûleur depuis": "of burner time since",
  "Date de l'entretien": "Service date",
  "Enregistrer l'entretien": "Record the service",
  // Onglet Eau chaude
  "gaz eau chaude sur 30 j": "hot water gas over 30 d",
  "({v} % du total)": "({v} % of total)",
  "Consigne à {v} °C : 50 °C suffisent au quotidien et réduisent les pertes du ballon, à condition d'activer la montée hebdomadaire à {lt} °C contre la légionelle (ci-dessous).":
    "Setpoint at {v} °C: 50 °C is enough for daily use and reduces tank losses, provided you enable the weekly boost to {lt} °C against legionella (below).",
  "Passer à 50 °C": "Switch to 50 °C",
  "Eau chaude sanitaire": "Domestic hot water",
  "consigne": "setpoint",
  "ballon actuellement": "tank right now",
  "Montée anti-légionelle hebdomadaire": "Weekly anti-legionella boost",
  "Chaque {day} à {time} : {temp} °C pendant {min} min, puis retour à la consigne":
    "Every {day} at {time}: {temp} °C for {min} min, then back to the setpoint",
  "en cours": "running",
  "dernière le {d}": "last on {d}",
  "Montée anti-légionelle": "Anti-legionella boost",
  "Activée": "Enabled",
  "Désactivée": "Disabled",
  // Onglet Planning
  "Désactivé": "Off",
  "Actif": "Active",
  "Confort": "Comfort",
  "Veille (pas de demande)": "Standby (no demand)",
  "Relance anticipée": "Early start",
  "En pause": "Paused",
  "Confirmer": "Confirm",
  "En savoir plus": "Learn more",
  "Pilote": "Pilot",
  "désactivé": "off",
  "actif": "active",
  "simulé": "dry run",
  "Évaluation de la courbe": "Curve evaluation",
  "Confort (éco)": "Comfort (eco)",
  "Normal": "Normal",
  "Normal (éco)": "Normal (eco)",
  "Réduit (éco)": "Reduced (eco)",
  "Veille": "Standby",
  "Forcé (planning)": "Forced (schedule)",
  "Éco": "Eco",
  "Vacances": "Holiday",
  "Vacances à la maison": "Holiday at home",
  "Fixe": "Fixed",
  "Tableau Énergie de Home Assistant : source gaz = compteur Gazpar (ou consommations ViCare), prix = entité « Prix du gaz (kWh) » de l'optimiseur, qui suit les Réglages.":
    "Home Assistant Energy dashboard: gas source = Gazpar meter (or ViCare consumption), price = the optimizer's \"Gas price (kWh)\" entity, which follows the Settings.",
  "Vitesse de chauffe apprise par Better Thermostat pour chaque pièce, comparée à la médiane.": "Heating rate learned by Better Thermostat for each room, compared with the median.",
  "Un radiateur qui chauffe beaucoup plus vite que les autres « vole » l'eau chaude aux pièces lentes.": "A radiator that heats much faster than the others \"steals\" hot water from the slow rooms.",
  "La courbe est réglée pour la pièce la plus difficile à chauffer.": "The curve is tuned for the hardest room to heat.",
  "Mode multi-pièces inactif : seule la sonde de la chaudière est utilisée. Ajoute tes thermostats dans l'onglet Réglages › Pièces et météo.":
    "Multi-room mode off: only the boiler's room sensor is used. Add your thermostats in the Settings tab › Rooms and weather.",
  "Parmi les pièces qui demandent de la chaleur, c'est la plus froide qui décide. Quand plus aucune ne demande, la marge de la moins chaude permet de baisser la courbe.":
    "Among the rooms calling for heat, the coldest one decides. When none calls for heat, the margin of the least warm room lets the curve go down.",
  "Relevés ViCare corrigés de {p} % d'après le compteur Gazpar ({n} mois comparés). La prévision de facture utilise directement les relevés du compteur.":
    "ViCare readings corrected by {p} % from the Gazpar meter ({n} months compared). The bill forecast uses the meter readings directly.",
  "Réglages": "Settings",
  "Général": "General",
  "— aucun —": "— none —",
  "Enregistrer": "Save",
  "Modifications non enregistrées": "Unsaved changes",
  "Tous les réglages de l'optimiseur, au même endroit.": "All optimizer settings in one place.",
  "Réglages enregistrés : l'optimiseur redémarre avec les nouvelles valeurs": "Settings saved: the optimizer restarts with the new values",
  "Échec : {e}": "Failed: {e}",
  "Calcul en cours…": "Calculating…",
  "Renseigne ta facture dans l'onglet Réglages (section « Facture et mensualités ») : début de période, mensualité, abonnement et consommation de référence.":
    "Enter your bill in the Settings tab (\"Bill and instalments\" section): period start, monthly instalment, standing charge and reference consumption.",
  "≈ {v} à payer à la régularisation": "≈ {v} to pay at the yearly settlement",
  "≈ {v} remboursés à la régularisation": "≈ {v} refunded at the yearly settlement",
  "consommés depuis le {d}": "used since {d}",
  "estimés sur l'année (reste selon un profil mensuel type)": "estimated for the year (remainder from a typical monthly profile)",
  "facture annuelle estimée TTC": "estimated yearly bill incl. VAT",
  "mensualités prévues": "scheduled instalments",
  "(fin de période le {d})": "(period ends {d})",
  "Estimation : elle s'affine au fil de l'hiver, et dépend surtout de la météo à venir.": "Estimate: it gets more accurate through the winter and mostly depends on the weather to come.",
  "Prévision de la facture": "Bill forecast",
  "écritures ViCare sur 24 h (quota Viessmann)": "ViCare writes over 24 h (Viessmann quota)",
  "Soleil attendu": "Sun expected",
  "Réduit": "Reduced",
  "Pilotage": "Setpoint pilot",
  "Le planning et les consignes de la chaudière s'appliquent comme d'habitude.": "The boiler's schedule and setpoints apply as usual.",
  "Le pilote calcule la consigne qu'il appliquerait, sans rien écrire sur la chaudière : regarde la frise ci-dessous pendant quelques jours.":
    "The pilot computes the setpoint it would apply, without writing anything to the boiler: watch the timeline below for a few days.",
  "Le pilote écrit la consigne du programme actif de la chaudière. Les consignes d'origine seront remises si tu le désactives.":
    "The pilot writes the setpoint of the boiler's active program. The original setpoints will be restored if you turn it off.",
  "consigne appliquée": "applied setpoint",
  "consigne calculée": "computed setpoint",
  "vitesse de relance apprise": "learned recovery rate",
  "de veille sur 7 jours": "of standby over 7 days",
  "(simulées)": "(simulated)",
  "Lun": "Mon",
  "Mar": "Tue",
  "Mer": "Wed",
  "Jeu": "Thu",
  "Ven": "Fri",
  "Sam": "Sat",
  "Dim": "Sun",
  "Planning hebdomadaire": "Weekly schedule",
  "Aucune décision enregistrée pour l'instant.": "No decisions recorded yet.",
  "Pilotage de la consigne": "Setpoint pilot",
  "Veille : {v} °C après {m} min sans demande de chaleur.": "Standby: {v} °C after {m} min without heat demand.",
  "Prévisions : {v} °C au plus bas sur 4 h.": "Forecast: {v} °C at lowest over 4 h.",
  "Planning de la semaine": "Weekly schedule",
  "Clique ou glisse sur la grille : bleu = confort, vide = réduit (pas de 30 min).":
    "Click or drag on the grid: blue = comfort, empty = reduced (30 min steps).",
  "Consigne confort": "Comfort setpoint",
  "Consigne réduite": "Reduced setpoint",
  "Importer depuis les têtes thermostatiques": "Import from thermostatic radiator valves",
  "Copier le lundi sur les jours ouvrés": "Copy Monday to weekdays",
  "Décisions des dernières 48 h": "Decisions over the last 48 h",
  "Consignes des pièces": "Room setpoints",
  "Les pièces cochées suivent le planning de la maison : consigne confort pendant les périodes bleues, réduite sinon.":
    "Checked rooms follow the house schedule: comfort setpoint during blue periods, reduced otherwise.",
  "Désactive les autres plannings de ces pièces (têtes, Scheduler) pour éviter qu'ils se contredisent.":
    "Disable the other schedules for these rooms (valve heads, Scheduler) so they don't conflict.",
  "Suit le planning": "Follows the schedule",
  "Consigne prévue": "Planned setpoint",
  "(simulé)": "(simulated)",
  "Frise des décisions du pilote": "Pilot decision timeline",
  // Onglet Diagnostic
  "Analyse en cours…": "Analysing…",
  "Saison de chauffe": "Heating season",
  "Déperditions": "Heat loss",
  "Talon": "Base load",
  "Fiabilité (R²)": "Reliability (R²)",
  "Jours": "Days",
  "Seuil de chauffe": "Heating threshold",
  "{v} kWh/j": "{v} kWh/day",
  "Utiliser": "Use",
  "pas assez de jours de chauffe ({n})": "not enough heating days ({n})",
  "Pas encore de statistiques de gaz.": "No gas statistics yet.",
  "Puissance de chauffe relative": "Relative heating power",
  "Conseil": "Advice",
  "{v} % de la médiane": "{v} % of the median",
  "Apports internes": "Internal gains",
  "apports internes": "internal gains",
  "aucun": "none",
  "Cliquer pour indiquer une pièce chauffée aussi par la cuisson, un poêle…": "Click to mark a room also heated by cooking, a stove…",
  "Cochez « apports internes » pour une pièce chauffée aussi par autre chose que son radiateur (cuisine, poêle, cheminée) : elle est alors exclue de la médiane et un écart vers le haut n'est qu'à confirmer.":
    "Mark « internal gains » for a room also heated by something other than its radiator (kitchen, stove, fireplace): it is then left out of the median and a high value only needs confirming.",
  "Il faut au moins deux pièces suivies avec Better Thermostat (onglet Pièces).":
    "At least two rooms monitored with Better Thermostat are needed (Rooms tab).",
  "Bilan thermique de la maison": "House heat balance",
  "Déperditions estimées à partir du gaz consommé et de l'écart intérieur / extérieur, jour par jour (rendement supposé 95 %).":
    "Heat loss estimated from the gas consumed and the indoor / outdoor difference, day by day (assumed efficiency 95 %).",
  "Moins de W/K = maison mieux isolée : compare les saisons avant et après des travaux.":
    "Fewer W/K = better insulated house: compare seasons before and after renovation work.",
  "Le seuil de chauffe est la température extérieure au-dessus de laquelle les apports gratuits (soleil, occupants, appareils) suffisent.":
    "The heating threshold is the outdoor temperature above which free gains (sun, occupants, appliances) are enough.",
  "Jours de surconsommation": "Overconsumption days",
  "Jour": "Day",
  "Consommé": "Consumed",
  "Attendu pour la météo": "Expected for the weather",
  "Équilibrage des radiateurs": "Radiator balancing",
  "Vitesse de chauffe apprise par Better Thermostat pour chaque pièce, comparée à la médiane. Un radiateur qui chauffe beaucoup plus vite que les autres « vole » l'eau chaude aux pièces lentes.":
    "Heating rate learned by Better Thermostat for each room, compared with the median. A radiator that heats much faster than the others “steals” hot water from the slow rooms.",
  "Bilan hebdomadaire": "Weekly report",
  "Envoyé chaque {day} à {time}": "Sent every {day} at {time}",
  "Envoi désactivé": "Sending disabled",
  "sur {target} et": "to {target} and",
  "dans les notifications de Home Assistant.": "in Home Assistant notifications.",
  "Envoyer maintenant": "Send now",
};
const t = (s, vars) => {
  let out = (LANG === "en" && EN[s]) || s;
  if (vars) out = out.replace(/\{(\w+)\}/g, (_, k) => (vars[k] ?? ""));
  return out;
};
const setLang = (hass) => {
  if (!hass?.language) return;
  LANG = hass.language.toLowerCase().startsWith("fr") ? "fr" : "en";
  LOCALE = LANG === "fr" ? "fr-FR" : "en-GB";
};
// 0 = lundi ; 2024-01-01 était un lundi
const weekdayName = (i) => new Date(Date.UTC(2024, 0, 1 + i)).toLocaleDateString(LOCALE, { weekday: "long", timeZone: "UTC" });

// --- Modèle Viessmann (identique à heating_curve.py) -------------------------
const curveTerm = (d) => d * (1.4347 + 0.021 * d + 247.9e-6 * d * d);
const supplyAt = (ot, rt, slope, shift) => rt + shift - slope * curveTerm(ot - rt);

// --- Utilitaires --------------------------------------------------------------
const num = (v) => {
  const n = parseFloat(v);
  return Number.isFinite(n) ? n : null;
};
const fmt = (v, d = 1, signed = false) => {
  if (v == null) return "—";
  const s = v.toLocaleString(LOCALE, { minimumFractionDigits: d, maximumFractionDigits: d });
  return signed && v > 0 ? `+${s}` : s;
};
const esc = (s) =>
  String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const median = (arr) => {
  const a = [...arr].sort((x, y) => x - y);
  const m = a.length >> 1;
  return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
};
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const dateFr = (t) =>
  new Date(t * 1000).toLocaleString(LOCALE, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

// Écart retenu pour une mesure : pièce limitante en multi-pièces, sinon sonde chaudière
const sampleErr = (s) => (s.eff != null ? s.eff : s.room - s.target);
const DAY = 86400000;
const dayLabel = (ms) => new Date(ms).toLocaleDateString(LOCALE, { day: "numeric", month: "short" });
const CONDENSING_MAX = 55; // °C de départ sous lesquels la condensation est assurée
const DJU_BASE = 18;
const capitalize = (txt) => (txt ? String(txt).charAt(0).toUpperCase() + String(txt).slice(1) : txt);
// Noms lisibles des programmes ViCare
const PROGRAMS = {
  comfort: "Confort", comfortenergysaving: "Confort (éco)", normal: "Normal", normalenergysaving: "Normal (éco)",
  reduced: "Réduit", reducedenergysaving: "Réduit (éco)", standby: "Veille", forcedlastfromschedule: "Forcé (planning)",
  eco: "Éco", holiday: "Vacances", holidayathome: "Vacances à la maison", fixed: "Fixe",
};
const programLabel = (p) => (p ? t(PROGRAMS[String(p).toLowerCase()] || p) : "—");
// Explication repliable : une phrase visible, le détail sur demande
const info = (...paragraphs) => `<details class="info"><summary>${t("En savoir plus")}</summary>${paragraphs.map((x) => `<p>${x}</p>`).join("")}</details>`;
const toMin = (hhmm) => { const [h, m] = String(hhmm).split(":"); return +h * 60 + +m; };
const fromMin = (m) => (m >= 1440 ? "24:00" : `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`);

function niceTicks(min, max, count = 5) {
  const raw = (max - min) / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw);
  const ticks = [];
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) ticks.push(+v.toFixed(6));
  return ticks;
}

function binSamples(samples, deadClip = 3) {
  const groups = new Map();
  for (const s of samples) {
    const k = Math.floor(s.outside);
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(s);
  }
  return [...groups.entries()]
    .filter(([, g]) => g.length >= 3)
    .sort((a, b) => a[0] - b[0])
    .map(([, g]) => ({
      outside: median(g.map((s) => s.outside)),
      error: median(g.map((s) => clamp(sampleErr(s), -deadClip, deadClip))),
      count: g.length,
    }));
}

const STYLE = `
:host { display:block; min-height:100vh; background:var(--primary-background-color); color:var(--primary-text-color);
  font-family:var(--paper-font-body1_-_font-family, Roboto, system-ui, sans-serif); --gap:16px; }
* { box-sizing:border-box; }
.toolbar { display:flex; align-items:center; gap:8px; height:56px; padding:0 16px; background:var(--app-header-background-color, var(--primary-color));
  color:var(--app-header-text-color, #fff); font-size:20px; font-weight:400; }
.toolbar .title { flex:1; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.content { max-width:1280px; margin:0 auto; padding:var(--gap); display:grid; grid-template-columns:minmax(0, 1fr); gap:var(--gap); }
.content > *, .card { min-width:0; }
@media (max-width: 600px) { :host { --gap:10px; } .card { padding:14px; } }
button:focus-visible, select:focus-visible, input:focus-visible, .cell:focus-visible, summary:focus-visible {
  outline:2px solid var(--primary-color); outline-offset:2px; }
.card { background:var(--card-background-color, #fff); border-radius:var(--ha-card-border-radius, 12px);
  border:1px solid var(--divider-color); padding:16px; min-width:0; }
.card h2 { margin:0 0 4px; font-size:16px; font-weight:500; }
.card .sub { margin:0 0 12px; color:var(--secondary-text-color); font-size:13px; }
.status { display:flex; flex-wrap:wrap; align-items:center; gap:12px 20px; }
.status .state b { font-size:16px; }
.status .facts { display:flex; flex-wrap:wrap; gap:4px 14px; margin-top:4px; font-size:13px; color:var(--secondary-text-color); }
.status .facts span { white-space:nowrap; }
.status .facts b { font-size:13px; color:var(--primary-text-color); }
@media (max-width: 600px) { .status .btn { flex:1; justify-content:center; } }
details.info { margin-top:8px; font-size:13px; color:var(--secondary-text-color); }
details.info summary { cursor:pointer; color:var(--primary-color); width:fit-content; list-style:none; }
details.info summary::-webkit-details-marker { display:none; }
details.info summary::before { content:"ⓘ "; }
details.info[open] summary { margin-bottom:6px; }
details.info p { margin:0 0 6px; line-height:1.5; }
.status .state { display:flex; align-items:center; gap:10px; flex:1; min-width:220px; }
.status .state ha-icon { color:var(--secondary-text-color); }
.status .state b { font-weight:500; }
.status .state small { display:block; color:var(--secondary-text-color); font-size:13px; }
.mode { display:flex; align-items:center; gap:10px; font-size:14px; }
.mode small { display:block; color:var(--secondary-text-color); font-size:12px; }
.toggle { position:relative; width:40px; height:22px; border-radius:11px; border:none; padding:0; cursor:pointer;
  background:var(--disabled-color, #bdbdbd); transition:background .15s; flex:none; }
.toggle::after { content:""; position:absolute; top:3px; left:3px; width:16px; height:16px; border-radius:50%; background:#fff; transition:transform .15s; }
.toggle[aria-checked="true"] { background:var(--primary-color); }
.toggle[aria-checked="true"]::after { transform:translateX(18px); }
button.btn { font:inherit; font-size:14px; font-weight:500; border-radius:8px; padding:8px 14px; cursor:pointer;
  border:1px solid var(--divider-color); background:transparent; color:var(--primary-color); display:inline-flex; align-items:center; gap:6px; }
button.btn.primary { background:var(--primary-color); color:var(--text-primary-color, #fff); border-color:var(--primary-color); }
button.btn:disabled { opacity:.45; cursor:default; }
.tiles { display:grid; grid-template-columns:repeat(auto-fit, minmax(150px, 1fr)); gap:var(--gap); }
@media (max-width: 600px) { .tiles { grid-template-columns:repeat(2, minmax(0, 1fr)); } .tile .value { font-size:22px; } }
.tile { display:flex; flex-direction:column; gap:2px; }
.tile .label { display:flex; align-items:center; gap:6px; color:var(--secondary-text-color); font-size:13px; }
.tile .label ha-icon { --mdc-icon-size:18px; }
.tile .value { font-size:26px; font-weight:500; font-variant-numeric:tabular-nums; }
.tile .value small { font-size:15px; font-weight:400; color:var(--secondary-text-color); }
.tile .hint { font-size:12px; color:var(--secondary-text-color); }
.main { display:grid; grid-template-columns:minmax(0, 2fr) minmax(280px, 1fr); gap:var(--gap); }
@media (max-width: 900px) { .main { grid-template-columns:1fr; } }
.legend { display:flex; flex-wrap:wrap; gap:4px 16px; font-size:13px; color:var(--secondary-text-color); margin-bottom:8px; }
.legend span { display:inline-flex; align-items:center; gap:6px; }
.key-line { width:18px; height:0; border-top:2px solid; }
.key-line.dashed { border-top-style:dashed; }
.key-dot { width:10px; height:10px; border-radius:50%; }
.chart { position:relative; width:100%; }
.chart svg { display:block; overflow:visible; }
.chart text { font-size:11px; fill:var(--secondary-text-color); font-variant-numeric:tabular-nums; }
.chart .grid { stroke:var(--divider-color); stroke-width:1; }
.chart .zero { stroke:var(--secondary-text-color); stroke-width:1; opacity:.6; }
.tooltip { position:absolute; pointer-events:none; background:var(--card-background-color, #fff); color:var(--primary-text-color);
  border:1px solid var(--divider-color); border-radius:8px; padding:8px 10px; font-size:12px; line-height:1.5;
  box-shadow:0 4px 12px rgba(0,0,0,.15); white-space:nowrap; display:none; z-index:2; }
.tooltip b { font-weight:500; }
.tooltip .row { display:flex; align-items:center; gap:6px; }
.tooltip .row i { width:10px; height:2px; display:inline-block; }
.empty { display:flex; align-items:center; justify-content:center; text-align:center; height:${CHART_H}px; padding:24px;
  color:var(--secondary-text-color); font-size:14px; border:1px dashed var(--divider-color); border-radius:8px; }
.ctrl { display:grid; gap:14px; }
.stepper { display:flex; align-items:center; justify-content:space-between; gap:8px; }
.stepper .name { font-size:14px; }
.stepper .name small { display:block; color:var(--secondary-text-color); font-size:12px; }
.stepper .box { display:flex; align-items:center; border:1px solid var(--divider-color); border-radius:8px; overflow:hidden; }
.stepper button { width:36px; height:36px; border:none; background:transparent; color:var(--primary-color); font-size:20px; cursor:pointer; }
.stepper button:disabled { opacity:.35; cursor:default; }
.stepper output { min-width:56px; text-align:center; font-size:16px; font-weight:500; font-variant-numeric:tabular-nums; }
.stepper output.changed { color:var(--primary-color); }
.effect { font-size:13px; color:var(--secondary-text-color); background:var(--secondary-background-color); border-radius:8px; padding:10px 12px; line-height:1.6; }
.effect b { color:var(--primary-text-color); font-weight:500; font-variant-numeric:tabular-nums; }
.actions { display:flex; flex-wrap:wrap; gap:8px; }
.note { font-size:12px; color:var(--secondary-text-color); margin:0; }
.proposal { border-top:1px solid var(--divider-color); padding-top:14px; display:grid; gap:10px; }
.proposal p { margin:0; font-size:14px; }
.proposal small { color:var(--secondary-text-color); }
.meter { height:8px; border-radius:4px; overflow:hidden; margin:8px 0 4px; }
.meter > div { height:100%; border-radius:4px; }
.meta { display:flex; justify-content:space-between; font-size:12px; color:var(--secondary-text-color); }
table { width:100%; border-collapse:collapse; font-size:13px; }
th { text-align:left; font-weight:500; color:var(--secondary-text-color); padding:6px 8px; border-bottom:1px solid var(--divider-color); }
td { padding:8px; border-bottom:1px solid var(--divider-color); font-variant-numeric:tabular-nums; white-space:nowrap; }
td:first-child { white-space:normal; }
tr:last-child td { border-bottom:none; }
.table-wrap { overflow-x:auto; }
.msg { position:fixed; bottom:24px; left:50%; transform:translateX(-50%); background:var(--primary-text-color); color:var(--card-background-color, #fff);
  padding:10px 16px; border-radius:8px; font-size:14px; z-index:10; box-shadow:0 4px 12px rgba(0,0,0,.25); }
.err { color:var(--error-color, #db4437); }
.mode.clickable { cursor:pointer; border-radius:8px; padding:4px 8px; margin:-4px -8px; }
.mode.clickable:hover { background:var(--secondary-background-color); }
.modal-backdrop { position:fixed; inset:0; background:rgba(0,0,0,.45); display:flex; align-items:center; justify-content:center; z-index:20; padding:16px; }
.modal { background:var(--card-background-color, #fff); color:var(--primary-text-color); border-radius:12px; padding:20px; max-width:440px; width:100%;
  box-shadow:0 8px 32px rgba(0,0,0,.3); }
.modal p { margin:0 0 16px; font-size:14px; line-height:1.5; }
.modal .actions { justify-content:flex-end; }
.fields { display:grid; grid-template-columns:repeat(auto-fill, minmax(260px, 1fr)); gap:14px 20px; }
.field { display:flex; flex-direction:column; gap:6px; min-width:0; }
.field.wide { grid-column:1 / -1; }
.field > label { font-size:13px; color:var(--secondary-text-color); }
.field input[type="number"], .field input[type="time"], .field input[type="date"], .field input[type="text"], .field select {
  font:inherit; font-size:14px; padding:7px 9px; border-radius:8px; border:1px solid var(--divider-color);
  background:var(--card-background-color); color:var(--primary-text-color); max-width:100%; }
.field .num { display:flex; align-items:center; gap:6px; }
.field .num input { width:120px; }
.field .num small { color:var(--secondary-text-color); }
.checks { display:flex; flex-wrap:wrap; gap:6px 16px; }
.check { display:inline-flex; align-items:center; gap:6px; font-size:14px; cursor:pointer; }
.savebar { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; position:sticky; top:8px; z-index:3; }
.savebar > span { font-size:14px; color:var(--secondary-text-color); }
.tabs { display:flex; gap:4px; overflow-x:auto; border-bottom:1px solid var(--divider-color); scrollbar-width:none; }
.tabs button { font:inherit; font-size:14px; font-weight:500; background:none; border:none; border-bottom:2px solid transparent; color:var(--secondary-text-color);
  padding:10px 14px; cursor:pointer; white-space:nowrap; display:inline-flex; align-items:center; gap:6px; }
.tabs button ha-icon { --mdc-icon-size:18px; }
.tabs button[aria-selected="true"] { color:var(--primary-color); border-bottom-color:var(--primary-color); }
@media (max-width: 600px) {
  .tabs { gap:0; }
  .tabs button { flex:1 1 0; min-width:0; flex-direction:column; gap:2px; padding:8px 2px; font-size:11px; }
  .tabs button ha-icon { --mdc-icon-size:20px; }
  .tabs button span { max-width:100%; overflow:hidden; text-overflow:ellipsis; }
}
.alert { display:flex; gap:12px; align-items:flex-start; border-radius:12px; padding:12px 16px; font-size:14px;
  background:color-mix(in srgb, var(--error-color, #db4437) 12%, var(--card-background-color, #fff)); border:1px solid color-mix(in srgb, var(--error-color, #db4437) 40%, transparent); }
.alert ha-icon { color:var(--error-color, #db4437); flex:none; }
.alert ul { margin:4px 0 0; padding-left:18px; }
.chip { display:inline-flex; align-items:center; gap:4px; font-size:12px; border-radius:10px; padding:2px 8px;
  background:var(--secondary-background-color); color:var(--secondary-text-color); white-space:nowrap; }
.chip.on { background:color-mix(in srgb, var(--warning-color, #ff9800) 18%, transparent); color:var(--primary-text-color); }
button.chip { border:0; font:inherit; font-size:12px; cursor:pointer; }
.chip.lim { background:color-mix(in srgb, var(--primary-color) 18%, transparent); color:var(--primary-text-color); }
.kpis { display:grid; grid-template-columns:repeat(auto-fit, minmax(140px, 1fr)); gap:12px; margin-bottom:12px; }
.kpi .v { font-size:22px; font-weight:500; font-variant-numeric:tabular-nums; }
.kpi .v small { font-size:13px; color:var(--secondary-text-color); font-weight:400; }
.kpi .l { font-size:12px; color:var(--secondary-text-color); }
.advice { display:flex; gap:10px; align-items:flex-start; font-size:14px; background:var(--secondary-background-color); border-radius:8px; padding:10px 12px; margin-top:12px; }
.advice ha-icon { --mdc-icon-size:20px; color:var(--primary-color); flex:none; }
.seg { display:inline-flex; border:1px solid var(--divider-color); border-radius:8px; overflow:hidden; }
.seg button { font:inherit; font-size:14px; padding:8px 16px; border:none; background:transparent; color:var(--primary-text-color); cursor:pointer; }
.seg button + button { border-left:1px solid var(--divider-color); }
.seg button[aria-checked="true"] { background:var(--primary-color); color:var(--text-primary-color, #fff); }
.sched { display:grid; gap:3px; user-select:none; touch-action:none; overflow-x:auto; }
.sched-hours, .sched-row { display:grid; grid-template-columns:36px 1fr; align-items:center; min-width:330px; }
.sched-hours { grid-template-columns:36px repeat(8, 1fr); font-size:11px; color:var(--secondary-text-color); }
.sched-day { font-size:12px; color:var(--secondary-text-color); }
.sched-cells { display:grid; grid-template-columns:repeat(48, 1fr); gap:1px; }
.sched-cells .cell { height:26px; background:var(--secondary-background-color); cursor:pointer; }
.sched-cells .cell:nth-child(6n+1) { margin-left:1px; }
.sched-cells .cell.on { background:var(--primary-color); }
table.rooms td.cellstep { padding:4px 8px; }
table.rooms .box { display:inline-flex; align-items:center; border:1px solid var(--divider-color); border-radius:8px; overflow:hidden; }
table.rooms .box button { width:30px; height:30px; border:none; background:transparent; color:var(--primary-color); font-size:18px; cursor:pointer; }
table.rooms output { min-width:56px; text-align:center; }
@media (max-width: 600px) {
  table.rooms td.cellstep { padding:4px 2px; }
  table.rooms .box button { width:26px; height:28px; font-size:16px; }
  table.rooms output { min-width:38px; font-size:13px; }
  table.rooms th, table.rooms td { padding-left:4px; padding-right:4px; }
  table.rooms th:nth-child(5), table.rooms td:nth-child(5) { display:none; } /* consigne prévue : secondaire sur téléphone */
}
input[type="date"] { font:inherit; padding:6px 8px; border-radius:8px; border:1px solid var(--divider-color);
  background:var(--card-background-color); color:var(--primary-text-color); }
.sched-cells .cell:hover { outline:1px solid var(--primary-text-color); outline-offset:-1px; }
.bar { display:inline-block; width:120px; height:8px; border-radius:4px; background:var(--secondary-background-color); margin-right:8px; vertical-align:middle; overflow:hidden; }
.bar > div { height:100%; border-radius:4px; }
pre.report { white-space:pre-wrap; font-family:inherit; font-size:14px; background:var(--secondary-background-color); border-radius:8px; padding:12px; margin:0 0 12px; }
`;

class HeatingCurvePanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._data = null;
    this._error = null;
    this._edit = null; // { slope, shift } en cours d'édition
    this._widths = {};
    this._charts = {};
    this._stats = null;
    this._recov = null;
    try {
      this._tab = { rooms: "planning", dhw: "boiler" }[localStorage.getItem("hco-tab")] || localStorage.getItem("hco-tab") || "curve";
    } catch {
      this._tab = "curve";
    }
    this.shadowRoot.addEventListener("click", (e) => this._onClick(e));
    this.shadowRoot.addEventListener("pointerdown", () => { this._pointerDown = true; });
    const release = () => {
      this._pointerDown = false;
      if (this._renderPending) {
        this._renderPending = false;
        setTimeout(() => this._render(), 50); // après l'événement click qui suit le relâchement
      }
    };
    this.shadowRoot.addEventListener("pointerup", release);
    this.shadowRoot.addEventListener("pointercancel", release);
    this.shadowRoot.addEventListener("keydown", (e) => {
      if (this._modal && e.key === "Escape") this._closeModal(false);
    });
  }

  // ------------------------------------------------------------------ cycle de vie
  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    setLang(hass);
    if (first) {
      this._fetch();
      this._timer = setInterval(() => this._fetch(), 60000);
      return;
    }
    const statusId = this._data?.own?.status;
    const statusStamp = statusId && hass.states[statusId]?.last_updated;
    if (statusStamp && statusStamp !== this._statusStamp) {
      this._statusStamp = statusStamp;
      this._fetch();
      return;
    }
    const key = this._liveKey();
    if (key !== this._lastKey || LANG !== this._lang) this._render();
  }
  set narrow(v) {
    this._narrow = v;
    this._render();
  }
  set panel(_v) {}

  connectedCallback() {
    this._ro = new ResizeObserver((entries) => {
      let changed = false;
      for (const e of entries) {
        const id = e.target.dataset.chart;
        const w = Math.round(e.contentRect.width);
        if (id && Math.abs((this._widths[id] || 0) - w) > 2) {
          this._widths[id] = w;
          changed = true;
        }
      }
      if (changed) this._render();
    });
    this._render();
  }
  disconnectedCallback() {
    clearInterval(this._timer);
    this._ro?.disconnect();
  }

  async _fetch() {
    if (!this._hass) return;
    try {
      this._data = await this._hass.callWS({ type: `${DOMAIN}/get` });
      this._error = null;
    } catch (err) {
      this._error = err?.message || t("Impossible de charger les données");
    }
    this._render();
  }

  // ------------------------------------------------------------------ état courant
  _state(id) {
    return id ? this._hass?.states[id] : undefined;
  }
  _liveKey() {
    const e = this._data?.entities || {};
    return [...Object.values(e), ...(this._data?.rooms || [])]
      .map((id) => this._state(id)?.last_updated)
      .join("|");
  }
  _live() {
    const e = this._data.entities;
    const climate = this._state(e.climate);
    const attrs = climate?.attributes || {};
    const program = attrs.active_vicare_program || "";
    let target = num(attrs.temperature);
    if (target == null) {
      // même repli que l'intégration : consigne du programme actif
      const base = program.replace(/EnergySaving$/, "").toLowerCase();
      target = num(this._state(this._data.program_targets?.[base])?.state);
    }
    return {
      program,
      target,
      room: e.room ? num(this._state(e.room)?.state) : num(attrs.room_temperature),
      outside: num(this._state(e.outside)?.state),
      supply: num(this._state(e.supply)?.state),
      burner: this._state(e.burner)?.state,
      slope: num(this._state(e.slope)?.state),
      shift: num(this._state(e.shift)?.state),
    };
  }
  _pendingProposal(live) {
    const p = this._data.last_proposal;
    if (!p || p.t <= (this._data.last_change || 0)) return null;
    if (p.new_slope === live.slope && p.new_shift === live.shift) return null;
    if (p.new_slope === p.slope && p.new_shift === p.shift) return null;
    return p;
  }
  _palette() {
    return SERIES[this._hass?.themes?.darkMode ? "dark" : "light"];
  }

  // ------------------------------------------------------------------ actions
  _closeModal(ok) {
    const modal = this._modal;
    this._modal = null;
    this._render();
    modal?.resolve(ok);
  }

  async _onClick(e) {
    const el = e.target.closest("[data-action]");
    if (!el || el.disabled) return;
    if (el.dataset.action === "modal-ok" || el.dataset.action === "modal-cancel") {
      this._closeModal(el.dataset.action === "modal-ok");
      return;
    }
    if (this._modal) return;
    const live = this._live();
    const a = el.dataset.action;
    const s = this._data.settings;
    if (a === "toggle-auto") {
      const on = !this._data.auto;
      if (on && !await this._confirm(t(
        "Activer l'ajustement automatique ?\n\nChaque nuit, l'optimiseur modifiera lui-même la courbe " +
        "de la chaudière (au plus ±{slope} de pente et ±{shift} K de décalage).",
        { slope: fmt(s.max_slope_step), shift: fmt(s.max_shift_step, 0) },
      ))) return;
      await this._hass.callService("switch", on ? "turn_on" : "turn_off", { entity_id: this._data.own.auto });
      this._toast(on ? t("Ajustement automatique activé") : t("Mode simulation : plus aucune modification automatique"));
      this._fetch();
    } else if (a === "evaluate") {
      await this._hass.callService("button", "press", { entity_id: this._data.own.evaluate });
      this._toast(t("Évaluation lancée"));
      setTimeout(() => this._fetch(), 1500);
    } else if (a === "step") {
      const cur = this._edit || { slope: live.slope, shift: live.shift };
      const field = el.dataset.field;
      const delta = parseFloat(el.dataset.delta);
      const next = { ...cur };
      if (field === "slope") next.slope = +clamp(cur.slope + delta, 0.2, 3.5).toFixed(1);
      else next.shift = clamp(Math.round(cur.shift + delta), -13, 40);
      this._edit = next.slope === live.slope && next.shift === live.shift ? null : next;
      this._render();
    } else if (a === "reset") {
      this._edit = null;
      this._render();
    } else if (a === "apply-edit" && this._edit) {
      await this._setCurve(this._edit.slope, this._edit.shift, "réglage manuel", live);
    } else if (a === "apply-proposal") {
      const p = this._pendingProposal(live);
      if (p) await this._setCurve(p.new_slope, p.new_shift, "proposition validée manuellement", live);
    } else if (a === "tab") {
      this._tab = el.dataset.tab;
      try {
        localStorage.setItem("hco-tab", this._tab);
      } catch {}
      this._render();
    } else if (a === "toggle-legionella") {
      const on = !this._data.legionella.enabled;
      await this._hass.callService("switch", on ? "turn_on" : "turn_off", { entity_id: this._data.own.legionella });
      this._toast(on ? t("Montée anti-légionelle hebdomadaire activée") : t("Montée anti-légionelle désactivée"));
      this._fetch();
    } else if (a === "set-dhw") {
      const v = parseFloat(el.dataset.value);
      if (!await this._confirm(t("Régler la consigne d'eau chaude sur {v} °C ?", { v }))) return;
      await this._hass.callService("number", "set_value", { entity_id: this._data.entities.dhw_target, value: v });
      this._toast(t("Consigne d'eau chaude envoyée : {v} °C", { v }));
    } else if (a === "pilot-mode") {
      const mode = el.dataset.mode;
      if (mode === "active" && !await this._confirm(t(
        "Activer le pilotage ?\n\nLe pilote écrira la consigne du programme actif de la chaudière (planning, veille sans demande, " +
        "relance anticipée). Les consignes d'origine sont mémorisées et remises si tu repasses en Désactivé ou Simulation."))) return;
      try {
        this._data = await this._hass.callWS({ type: `${DOMAIN}/set_control_mode`, mode });
        this._toast({ off: t("Pilotage désactivé"), simulation: t("Pilotage en simulation"), active: t("Pilotage actif") }[mode]);
      } catch (err) {
        this._toast(t("Échec : {msg}", { msg: err?.message || err }));
      }
      this._render();
    } else if (a === "draft-temp") {
      const k = el.dataset.key;
      this._draftTemps[k] = clamp(this._draftTemps[k] + +el.dataset.delta, k === "comfort" ? 10 : 5, k === "comfort" ? 26 : 24);
      this._draftDirty = true;
      this._render();
    } else if (a === "save-schedule") {
      try {
        this._data = await this._hass.callWS({
          type: `${DOMAIN}/set_schedule`, schedule: this._scheduleFromDraft(this._draft),
          comfort: this._draftTemps.comfort, reduced: this._draftTemps.reduced,
        });
        this._draft = null;
        this._toast(t("Planning enregistré"));
      } catch (err) {
        this._toast(t("Échec : {msg}", { msg: err?.message || err }));
      }
      this._render();
    } else if (a === "reset-schedule") {
      this._draft = null;
      this._render();
    } else if (a === "import-trv") {
      this._draft = this._draftFromSchedule(this._data.pilot.trv_suggestion);
      this._draftDirty = true;
      this._toast(t("Planning des têtes importé : vérifie puis enregistre"));
      this._render();
    } else if (a === "copy-monday") {
      for (let d = 1; d < 5; d++) this._draft[d] = [...this._draft[0]];
      this._draftDirty = true;
      this._render();
    } else if (a === "room-enable") {
      const r = this._roomDraft[el.dataset.room];
      r.enabled = !r.enabled;
      this._roomDirty = true;
      this._render();
    } else if (a === "room-temp") {
      const r = this._roomDraft[el.dataset.room];
      r[el.dataset.key] = clamp(r[el.dataset.key] + +el.dataset.delta, 5, 28);
      this._roomDirty = true;
      this._render();
    } else if (a === "save-rooms") {
      try {
        this._data = await this._hass.callWS({ type: `${DOMAIN}/set_room_targets`, targets: this._roomDraft });
        this._roomDraft = null;
        this._roomDirty = false;
        this._toast(t("Consignes des pièces enregistrées"));
      } catch (err) {
        this._toast(t("Échec : {msg}", { msg: err?.message || err }));
      }
      this._render();
    } else if (a === "reset-rooms") {
      this._roomDraft = null;
      this._roomDirty = false;
      this._render();
    } else if (a === "load-computed") {
      const c = this._data.computed_curve;
      if (c) this._edit = { slope: c.slope, shift: c.shift };
      this._render();
    } else if (a === "maintenance-done") {
      const input = this.shadowRoot.querySelector("#maint-date");
      const date = input?.value || undefined;
      if (!await this._confirm(date ? t("Enregistrer un entretien au {date} ?", { date }) : t("Enregistrer un entretien aujourd'hui ?"))) return;
      this._data = await this._hass.callWS({ type: `${DOMAIN}/set_maintenance`, ...(date ? { date } : {}) });
      this._toast(t("Entretien enregistré"));
      this._render();
    } else if (a === "use-limit") {
      const v = parseFloat(el.dataset.value);
      if (!await this._confirm(t("Ne plus collecter de mesures au-dessus de {v} °C extérieur ?", { v: fmt(v, 1) }))) return;
      await this._hass.callWS({ type: `${DOMAIN}/set_heating_limit`, value: v });
      this._toast(t("Seuil enregistré (l'intégration se recharge)"));
      setTimeout(() => this._fetch(), 3000);
    } else if (a === "settings-toggle") {
      const k = el.dataset.key;
      this._settingsDraft[k] = !this._settingsDraft[k];
      this._settingsDirty = true;
      this._render();
    } else if (a === "settings-reset") {
      this._settingsDraft = JSON.parse(JSON.stringify(this._settingsDef.values));
      this._settingsDirty = false;
      this._render();
    } else if (a === "settings-save") {
      const changed = {};
      for (const [k, val] of Object.entries(this._settingsDraft)) {
        if (JSON.stringify(val) !== JSON.stringify(this._settingsDef.values[k])) changed[k] = val;
      }
      try {
        await this._hass.callWS({ type: `${DOMAIN}/set_settings`, values: changed });
        this._toast(t("Réglages enregistrés : l'optimiseur redémarre avec les nouvelles valeurs"));
        this._settingsDef = null;
        this._bill = null;
        this._stats = null;
        setTimeout(() => this._fetch(), 4000);
      } catch (err) {
        this._toast(t("Échec : {e}", { e: err?.message || err }));
      }
      this._render();
    } else if (a === "send-report") {
      try {
        await this._hass.callWS({ type: `${DOMAIN}/weekly_report`, send: true });
        this._toast(t("Bilan envoyé"));
      } catch (err) {
        this._toast(t("Échec : {msg}", { msg: err?.message || err }));
      }
    } else if (a === "toggle-gains") {
      try {
        const diag = await this._hass.callWS({
          type: `${DOMAIN}/set_internal_gains`, entity_id: el.dataset.entity, enabled: el.dataset.value === "1",
        });
        this._diag = { ...diag, report: this._diag?.report };
      } catch (err) {
        this._toast(t("Échec : {msg}", { msg: err?.message || err }));
      }
      this._render();
    } else if (a === "reload-diag") {
      this._diag = null;
      this._render();
    } else if (a === "reload-stats") {
      this._stats = null;
      this._recov = null;
      this._render();
    } else if (a === "load-proposal") {
      const p = this._pendingProposal(live);
      if (p) this._edit = { slope: p.new_slope, shift: p.new_shift };
      this._render();
    }
  }

  async _setCurve(slope, shift, reason, live) {
    const twoSteps = slope !== live.slope && shift !== live.shift;
    const msg =
      t("Appliquer sur la chaudière ?\n\nPente {s0} → {s1}\nDécalage {h0} → {h1}", {
        s0: fmt(live.slope), s1: fmt(slope), h0: fmt(live.shift, 0, true), h1: fmt(shift, 0, true),
      }) +
      (twoSteps ? t("\n\nLa pente est écrite tout de suite, le décalage environ 5 min après (contrainte ViCare).") : "");
    if (!await this._confirm(msg)) return;
    try {
      this._data = await this._hass.callWS({ type: `${DOMAIN}/set_curve`, slope, shift, reason });
      this._edit = null;
      this._toast(twoSteps ? t("Pente envoyée, décalage dans ~5 min") : t("Courbe envoyée à la chaudière"));
    } catch (err) {
      this._toast(t("Échec : {msg}", { msg: err?.message || err }));
    }
    this._render();
  }

  _toast(text) {
    this._msgText = text;
    this._render();
    clearTimeout(this._msgTimer);
    this._msgTimer = setTimeout(() => {
      this._msgText = null;
      this._render();
    }, 4000);
  }

  // ------------------------------------------------------------------ rendu
  _confirm(message) {
    return new Promise((resolve) => {
      this._modal = { message, resolve };
      this._render();
    });
  }

  _render() {
    if (!this.shadowRoot || !this._hass) return;
    const focused = this.shadowRoot.activeElement;
    if (focused && ["INPUT", "SELECT", "TEXTAREA"].includes(focused.tagName) && !this._forceRender) {
      // Saisie en cours : redessiner ferait perdre le champ actif ; on redessinera à la sortie du champ
      this._renderPending = true;
      if (!this._focusHooked) {
        this._focusHooked = true;
        this.shadowRoot.addEventListener("focusout", () => setTimeout(() => {
          if (this._renderPending && !this.shadowRoot.activeElement) { this._renderPending = false; this._render(); }
        }, 0));
      }
      return;
    }
    if (this._pointerDown) {
      // Un clic est en cours : redessiner maintenant remplacerait le bouton visé et perdrait le clic
      this._renderPending = true;
      return;
    }
    this._lastKey = this._data ? this._liveKey() : null;
    this._lang = LANG;
    const root = this.shadowRoot;
    let body;
    if (this._error) body = `<div class="card err">${esc(this._error)}</div>`;
    else if (!this._data) body = `<div class="card">${t("Chargement…")}</div>`;
    else body = this._body();
    root.innerHTML = `<style>${STYLE}</style>
      <div class="toolbar"><span class="menu"></span><span class="title">${t("Courbe de chauffe")}</span></div>
      <div class="content">${body}</div>
      ${this._msgText ? `<div class="msg" role="status">${esc(this._msgText)}</div>` : ""}
      ${this._modal ? `<div class="modal-backdrop"><div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-text">
        <p id="modal-text">${esc(this._modal.message).replace(/\n/g, "<br>")}</p>
        <div class="actions"><button class="btn" data-action="modal-cancel">${t("Annuler")}</button>
          <button class="btn primary" data-action="modal-ok">${t("Confirmer")}</button></div></div></div>` : ""}`;
    root.querySelector('[data-action="modal-ok"]')?.focus();

    if (this._narrow) {
      const mb = document.createElement("ha-menu-button");
      mb.hass = this._hass;
      mb.narrow = this._narrow;
      root.querySelector(".menu").appendChild(mb);
    }
    this._ro?.disconnect();
    root.querySelectorAll("[data-chart]").forEach((el) => this._ro?.observe(el));
    this._bindHover();
    this._bindSchedule();
    this._bindSettings();
  }

  _body() {
    const d = this._data;
    const live = this._live();
    const pal = this._palette();
    const proposal = this._pendingProposal(live);
    const s = d.settings;
    const mean = d.samples.length
      ? d.samples.reduce((acc, x) => acc + sampleErr(x), 0) / d.samples.length
      : null;
    const curveNow =
      live.outside != null && live.target != null && live.slope != null
        ? supplyAt(live.outside, live.target, live.slope, live.shift)
        : null;

    const status = `
      <div class="card status">
        <div class="state">
          <ha-icon icon="mdi:information-outline"></ha-icon>
          <div><b>${esc(capitalize(d.status))}</b>
            <div class="facts">
              <span>${t("Chaudière")} : <b>${esc(programLabel(live.program))}</b></span>
              <span>${t("Pilote")} : <b>${d.pilot.mode === "off" ? t("désactivé")
                : `${d.pilot.mode === "active" ? t("actif") : t("simulé")}${d.pilot.state ? ` · ${esc(t(d.pilot.state.mode))}${d.pilot.state.setpoint != null ? ` ${fmt(d.pilot.state.setpoint, 0)} °C` : ""}` : ""}`}</b></span>
              <span>${t("Évaluation de la courbe")} : <b>${esc(String(s.evaluate_at).slice(0, 5))}</b></span>
            </div></div>
        </div>
        <div class="mode clickable" data-action="toggle-auto">
          <button class="toggle" role="switch" aria-checked="${d.auto}" aria-label="${t("Ajustement automatique")}" data-action="toggle-auto"></button>
          <div>${d.auto ? t("Ajustement automatique") : t("Simulation")}
            <small>${d.auto ? t("la courbe est modifiée chaque nuit") : t("propose sans rien modifier")}</small></div>
        </div>
        <button class="btn" data-action="evaluate"><ha-icon icon="mdi:calculator-variant" style="--mdc-icon-size:18px"></ha-icon>${t("Évaluer maintenant")}</button>
      </div>`;

    const tile = (icon, label, value, unit, hint) => `
      <div class="card tile">
        <span class="label"><ha-icon icon="${icon}"></ha-icon>${label}</span>
        <span class="value">${value}${unit ? ` <small>${unit}</small>` : ""}</span>
        <span class="hint">${hint}</span>
      </div>`;
    const tiles = `<div class="tiles">
      ${tile("mdi:home-thermometer-outline", t("Ambiance"), fmt(live.room), "°C", t("consigne {v} °C", { v: fmt(live.target, 0) }))}
      ${tile("mdi:thermometer-lines", t("Écart moyen mesuré"), fmt(mean, 2, true), "K", d.samples.length > 1 ? t("{n} mesures en cours", { n: d.samples.length }) : t("{n} mesure en cours", { n: d.samples.length }))}
      ${tile("mdi:sun-thermometer-outline", t("Extérieur"), fmt(live.outside), "°C", t("chauffe surveillée sous {v} °C", { v: fmt(s.heating_limit, 0) }))}
      ${tile("mdi:water-thermometer-outline", t("Départ chaudière"), fmt(live.supply), "°C", t("courbe à cette T° ext. : {v} °C", { v: fmt(curveNow) }))}
      ${tile("mdi:chart-bell-curve-cumulative", t("Courbe actuelle"), `${fmt(live.slope)} <small>·</small> ${fmt(live.shift, 0, true)}`, "", t("pente · décalage (K)"))}
      ${tile("mdi:fire", t("Brûleur"), live.burner === "on" ? t("Allumé") : live.burner === "off" ? t("Éteint") : "—", "", t("état en direct"))}
    </div>`;

    // Courbe alternative affichée : édition en cours, sinon proposition
    const alt = this._edit
      ? { label: t("Réglage en cours"), ...this._edit }
      : proposal
        ? { label: t("Proposition"), slope: proposal.new_slope, shift: proposal.new_shift }
        : null;

    const curveCard = `
      <div class="card">
        <h2>${t("Courbe de chauffe")}</h2>
        <p class="sub">${t("Température de départ calculée selon la température extérieure (consigne {v} °C)", { v: fmt(live.target, 0) })}</p>
        <div class="legend">
          <span><i class="key-line" style="border-color:${pal.s1}"></i>${t("Actuelle (pente {s}, décalage {h})", { s: fmt(live.slope), h: fmt(live.shift, 0, true) })}</span>
          ${alt ? `<span><i class="key-line dashed" style="border-color:${pal.s2}"></i>${t("{label} (pente {s}, décalage {h})", { label: alt.label, s: fmt(alt.slope), h: fmt(alt.shift, 0, true) })}</span>`
            : `<span style="visibility:hidden" aria-hidden="true"><i class="key-line dashed"></i>${t("{label} (pente {s}, décalage {h})", { label: t("Réglage en cours"), s: fmt(0), h: "+00" })}</span>`}
          ${live.supply != null && live.outside != null ? `<span><i class="key-dot" style="background:var(--primary-text-color)"></i>${t("Départ mesuré maintenant")}</span>` : ""}
        </div>
        ${this._curveChart(live, alt, pal)}
      </div>`;

    const control = this._controlCard(live, proposal);

    const errorCard = `
      <div class="card">
        <h2>${t("Écart ambiance − consigne")}</h2>
        <p class="sub">${t("Mesures collectées depuis le dernier ajustement, selon la température extérieure")}</p>
        ${d.samples.length ? `<div class="legend">
          <span><i class="key-dot" style="background:${pal.s1};opacity:.5"></i>${t("Mesure (toutes les 10 min)")}</span>
          <span><i class="key-dot" style="background:${pal.s2}"></i>${t("Médiane par tranche de 1 °C")}</span>
          <span><i class="key-dot" style="background:var(--secondary-text-color);opacity:.25"></i>${t("Tolérance ±{v} K", { v: fmt(s.deadband) })}</span>
        </div>` : ""}
        ${this._errorChart(d.samples, s, pal)}
        ${this._progress(d, s, pal)}
      </div>`;

    const history = d.history.length
      ? `<div class="table-wrap"><table>
          <thead><tr><th>${t("Date")}</th><th>${t("Pente")}</th><th>${t("Décalage")}</th><th>${t("Écart moyen")}</th><th>${t("Origine")}</th></tr></thead>
          <tbody>${[...d.history].reverse().map((h) => `<tr>
            <td>${dateFr(h.t)}</td>
            <td>${fmt(h.slope)} → ${fmt(h.new_slope)}</td>
            <td>${fmt(h.shift, 0, true)} → ${fmt(h.new_shift, 0, true)}</td>
            <td>${fmt(h.mean_error, 2, true)} K</td>
            <td>${esc(h.reason)}</td></tr>`).join("")}</tbody></table></div>`
      : `<p class="sub" style="margin:0">${t("Aucun ajustement pour l'instant.")}</p>`;

    const alerts = Object.values(d.alerts || {});
    const alertBanner = alerts.length
      ? `<div class="alert" role="alert"><ha-icon icon="mdi:alert-circle"></ha-icon>
          <div><b>${t("Alerte chaudière")}</b><ul>${alerts.map((m) => `<li>${esc(m)}</li>`).join("")}</ul></div></div>`
      : "";
    const tabs = [
      ["curve", "mdi:chart-bell-curve-cumulative", t("Courbe")],
      ["planning", "mdi:calendar-clock", t("Planning")],
      ["savings", "mdi:piggy-bank-outline", t("Économies")],
      ["boiler", "mdi:fire", t("Chaudière")],
      ["diag", "mdi:stethoscope", t("Diagnostic")],
      ["settings", "mdi:cog-outline", t("Réglages")],
    ];
    const nav = `<nav class="tabs" role="tablist">${tabs
      .map(([k, icon, label]) =>
        `<button role="tab" aria-selected="${this._tab === k}" data-action="tab" data-tab="${k}" title="${label}"><ha-icon icon="${icon}"></ha-icon><span>${label}</span></button>`)
      .join("")}</nav>`;

    let content;
    if (this._tab === "settings") content = this._settingsTab();
    else if (this._tab === "planning") content = `${this._planningTab(pal)}${this._roomsTab(live)}`;
    else if (this._tab === "diag") content = this._diagnosticTab(pal);
    else if (this._tab === "savings") content = this._savingsTab(pal);
    else if (this._tab === "boiler") content = `${this._boilerTab(pal)}${this._dhwTab()}`;
    else content = `${tiles}
      <div class="main">${curveCard}${control}</div>
      ${errorCard}
      <div class="card"><h2>${t("Historique des ajustements")}</h2>${history}</div>`;
    return `${status}${alertBanner}${nav}${content}`;
  }

  // ------------------------------------------------------------------ données long terme
  _ensureStats() {
    if (this._stats || this._statsLoading) return;
    this._statsLoading = true;
    const e = this._data.entities;
    const now = Date.now();
    const iso = (ms) => new Date(ms).toISOString();
    const daily = [this._data.gas_source?.entity || e.gas_heating_day, e.gas_dhw_day, e.outside, e.burner_starts, e.burner_hours].filter(Boolean);
    const hourly = [e.supply, e.modulation, e.gas_dhw_day].filter(Boolean);
    const startDay = new Date(now - 60 * DAY);
    startDay.setHours(0, 0, 0, 0);
    Promise.all([
      this._hass.callWS({
        type: "recorder/statistics_during_period", start_time: iso(startDay.getTime()), end_time: iso(now),
        statistic_ids: daily, period: "day", types: ["change", "mean"],
      }),
      this._hass.callWS({
        type: "recorder/statistics_during_period", start_time: iso(now - 7 * DAY), end_time: iso(now),
        statistic_ids: hourly, period: "hour", types: ["mean", "change"],
      }),
    ])
      .then(([day, hour]) => {
        this._stats = { day, hour, at: now };
      })
      .catch((err) => {
        this._stats = { error: err?.message || String(err) };
      })
      .finally(() => {
        this._statsLoading = false;
        this._render();
      });
  }

  _ensureRecoveries() {
    if (this._recov || this._recovLoading) return;
    this._recovLoading = true;
    this._hass
      .callWS({ type: `${DOMAIN}/recoveries`, days: 7 })
      .then((r) => {
        this._recov = r;
      })
      .catch((err) => {
        this._recov = { error: err?.message || String(err) };
      })
      .finally(() => {
        this._recovLoading = false;
        this._render();
      });
  }

  _dailySeries(id, type) {
    const rows = (id && this._stats?.day?.[id]) || [];
    return rows.map((r) => ({ t: r.start, v: r[type] })).filter((r) => r.v != null);
  }

  // ------------------------------------------------------------------ onglet Pièces
  _roomsTab(live) {
    const d = this._data;
    const counts = {};
    for (const smp of d.samples) if (smp.lim) counts[smp.lim] = (counts[smp.lim] || 0) + 1;
    const withLim = Object.values(counts).reduce((a, b) => a + b, 0);
    const name = (id) => this._state(id)?.attributes.friendly_name || id;
    const rows = [{
      id: d.entities.climate,
      label: t("{name} (sonde chaudière)", { name: name(d.entities.climate) }),
      cur: live.room,
      tgt: live.target,
      demand: live.room != null && live.target != null && live.room < live.target,
      window: false,
    }];
    for (const id of d.rooms) {
      const st = this._state(id);
      const a = st?.attributes || {};
      rows.push({
        id, label: name(id), cur: num(a.current_temperature), tgt: num(a.temperature),
        demand: a.hvac_action === "heating", window: !!(a.window_open || a.window_state === "on"),
        off: !st || st.state === "off",
      });
    }
    const table = `<div class="table-wrap"><table>
      <thead><tr><th>${t("Pièce")}</th><th>${t("Ambiance")}</th><th>${t("Consigne")}</th><th>${t("Écart")}</th><th>${t("État")}</th><th>${t("Limitante")}</th></tr></thead>
      <tbody>${rows.map((r) => {
        const err = r.cur != null && r.tgt != null ? r.cur - r.tgt : null;
        const share = withLim ? Math.round(((counts[r.id] || 0) / withLim) * 100) : null;
        const chips = [
          r.off ? `<span class="chip">${t("arrêt")}</span>`
            : r.demand ? `<span class="chip on">${t("demande de chaleur")}</span>` : `<span class="chip">${t("satisfaite")}</span>`,
          r.window ? `<span class="chip">${t("fenêtre ouverte")}</span>` : "",
        ].join(" ");
        return `<tr><td>${esc(r.label)}</td><td>${fmt(r.cur)} °C</td><td>${fmt(r.tgt)} °C</td>
          <td>${fmt(err, 1, true)} K</td><td>${chips}</td>
          <td>${share != null ? `<span class="chip ${share >= 40 ? "lim" : ""}">${t("{v} % du temps", { v: share })}</span>` : "—"}</td></tr>`;
      }).join("")}</tbody></table></div>`;
    const explain = d.rooms.length
      ? `<p class="sub">${t("La courbe est réglée pour la pièce la plus difficile à chauffer.")}</p>`
      : `<p class="sub">${t("Mode multi-pièces inactif : seule la sonde de la chaudière est utilisée. Ajoute tes thermostats dans l'onglet Réglages › Pièces et météo.")}</p>`;
    const more = d.rooms.length
      ? info(t("Parmi les pièces qui demandent de la chaleur, c'est la plus froide qui décide. Quand plus aucune ne demande, la marge de la moins chaude permet de baisser la courbe."))
      : "";
    return `<div class="card"><h2>${t("Pièces suivies")}</h2>${explain}${table}${more}
      ${withLim ? `<p class="note" style="margin-top:10px">${t("« Limitante » : part des {n} mesures en cours où la pièce a fixé l'écart retenu.", { n: withLim })}</p>` : ""}
      ${d.settings.solar_filter && d.entities.weather ? `<p class="note" style="margin-top:6px">${t("Filtre solaire actif : les mesures prises par grand soleil sont ignorées ({name}).", { name: esc(name(d.entities.weather)) })}</p>` : ""}</div>`;
  }

  // ------------------------------------------------------------------ onglet Économies
  _savingsTab(pal) {
    this._ensureStats();
    this._ensureRecoveries();
    const d = this._data;
    let body;
    if (!this._stats) body = `<div class="empty">${t("Chargement des statistiques…")}</div>`;
    else if (this._stats.error) body = `<div class="empty err">${esc(this._stats.error)}</div>`;
    else {
      const src = d.gas_source || { entity: d.entities.gas_heating_day, to_m3: 1 };
      const gas = new Map(this._dailySeries(src.entity, "change").map((r) => [r.t, r.v * src.to_m3]));
      const days = this._dailySeries(d.entities.outside, "mean").map((r) => {
        const dju = Math.max(0, DJU_BASE - r.v);
        const g = gas.get(r.t);
        return { t: r.t, dju, gas: g ?? null, ratio: g != null && dju >= 2 ? g / dju : null, ext: r.v };
      });
      const changes = d.history.map((h) => h.t * 1000);
      const last = changes.length ? changes[changes.length - 1] : null;
      const ratioOf = (list) => {
        const ok = list.filter((x) => x.gas != null && x.dju >= 2);
        const dju = ok.reduce((a, x) => a + x.dju, 0);
        return dju >= 20 ? ok.reduce((a, x) => a + x.gas, 0) / dju : null;
      };
      const before = last ? ratioOf(days.filter((x) => x.t < last && x.t >= last - 21 * DAY)) : null;
      const after = last ? ratioOf(days.filter((x) => x.t >= last)) : null;
      const ref = ratioOf(days.slice(-30));
      const delta = before && after ? ((after - before) / before) * 100 : null;
      const totalGas = days.slice(-30).reduce((a, x) => a + (x.gas || 0), 0);
      const c = d.costs;
      const eur = (m3) => m3 * c.kwh_per_m3 * c.gas_price;
      const dju30 = days.slice(-30).reduce((a, x) => a + x.dju, 0);
      const saving = before && after && after < before ? eur((before - after) * dju30) : null;
      body = `<div class="kpis">
          <div class="kpi"><div class="v">${fmt(ref > 0 ? ref : null, 3)}</div><div class="l">${t("m³ par degré-jour (30 j)")}</div></div>
          <div class="kpi"><div class="v">${fmt(totalGas, 0)} m³ <small>${t("≈ {v} €", { v: fmt(eur(totalGas), 0) })}</small></div><div class="l">${t("gaz chauffage sur 30 j ({p} €/kWh)", { p: fmt(c.gas_price, 3) })}</div></div>
          <div class="kpi"><div class="v">${saving != null ? t("{v} €", { v: fmt(saving, 0) }) : "—"}</div><div class="l">${t("économie estimée sur 30 j depuis le dernier ajustement")}</div></div>
          <div class="kpi"><div class="v">${fmt(before, 3)}</div><div class="l">${t("m³/DJU avant le dernier ajustement")}</div></div>
          <div class="kpi"><div class="v">${fmt(after, 3)}${delta != null ? ` <small>(${fmt(delta, 0, true)} %)</small>` : ""}</div><div class="l">${t("m³/DJU depuis")}</div></div>
        </div>
        <div class="legend"><span><i class="key-dot" style="background:${pal.s1}"></i>${t("m³ de gaz par degré-jour (base {b} °C)", { b: DJU_BASE })}</span>
          ${changes.length ? `<span><i class="key-line" style="border-color:${pal.s2}"></i>${t("Ajustement de la courbe")}</span>` : ""}</div>
        ${!days.some((x) => x.gas > 0)
          ? `<div class="empty">${t("Aucune consommation de gaz de chauffage sur la période : la saison de chauffe n'a pas encore commencé.")}</div>`
          : this._columnChart("dju", days.filter((x) => x.ratio != null && x.ratio > 0), (x) => x.ratio, pal.s1, {
          fmtY: (v) => fmt(v, 2),
          markers: changes,
          tip: (x) => `<b>${dayLabel(x.t)}</b><div>${t("{gas} m³ · {dju} DJU (ext. {ext} °C)", { gas: fmt(x.gas, 1), dju: fmt(x.dju, 1), ext: fmt(x.ext) })}</div><div><b>${fmt(x.ratio, 3)}</b> m³/DJU</div>`,
          empty: t("Pas encore assez de jours de chauffe (au moins 2 degrés-jours par jour)."),
        })}
        ${info(
          `${t("Un degré-jour (DJU) mesure le besoin de chauffage : {b} °C moins la température extérieure moyenne du jour.", { b: DJU_BASE })}
          ${t("Diviser le gaz par les DJU compare des périodes de météo différente : si le ratio baisse après un ajustement, l'économie est réelle.")}`,
          t("Tableau Énergie de Home Assistant : source gaz = compteur Gazpar (ou consommations ViCare), prix = entité « Prix du gaz (kWh) » de l'optimiseur, qui suit les Réglages."),
        )}`;
    }
    return `<div class="card"><h2>${t("Consommation corrigée de la météo")}</h2>
        <p class="sub">${t("Gaz de chauffage par degré-jour sur 60 jours")}
          <button class="btn" style="padding:2px 8px;margin-left:6px" data-action="reload-stats">${t("Actualiser")}</button></p>${body}</div>
      ${this._data.calibration ? `<div class="card"><div class="advice" style="margin-top:0"><ha-icon icon="mdi:meter-gas-outline"></ha-icon><div>${t(
        "Relevés ViCare corrigés de {p} % d'après le compteur Gazpar ({n} mois comparés). La prévision de facture utilise directement les relevés du compteur.",
        { p: fmt((this._data.calibration.ratio - 1) * 100, 0, true), n: this._data.calibration.months })}</div></div></div>` : ""}
      ${this._billCard()}
      ${this._recoveryCard()}`;
  }

  _recoveryCard() {
    const r = this._recov;
    let body;
    if (!r) body = `<p class="sub">${t("Analyse de l'historique…")}</p>`;
    else if (r.error) body = `<p class="sub err">${esc(r.error)}</p>`;
    else {
      const rows = r.recoveries.slice(-7).reverse();
      body = rows.length
        ? `<div class="table-wrap"><table>
          <thead><tr><th>${t("Relance")}</th><th>${t("Baisse la nuit")}</th><th>${t("Ambiance → consigne")}</th><th>${t("Consigne atteinte en")}</th></tr></thead>
          <tbody>${rows.map((x) => `<tr><td>${dateFr(x.start)}</td><td>${fmt(x.night_drop, 1)} K</td>
            <td>${fmt(x.room_start)} °C → ${fmt(x.target, 0)} °C</td>
            <td>${x.minutes == null ? t("non atteinte") : `${fmt(x.minutes, 0)} min`}</td></tr>`).join("")}</tbody></table></div>`
        : "";
      body += `<div class="advice"><ha-icon icon="mdi:lightbulb-on-outline"></ha-icon><div>${esc(r.advice)}</div></div>`;
    }
    return `<div class="card"><h2>${t("Réduit de nuit")}</h2><p class="sub">${t("Relances du matin sur les 7 derniers jours (sonde de la chaudière)")}</p>${body}</div>`;
  }

  // ------------------------------------------------------------------ onglet Chaudière
  _boilerTab(pal) {
    this._ensureStats();
    const d = this._data;
    const e = d.entities;
    const b = d.burner_24h;
    const pressure = num(this._state(e.pressure)?.state);
    let cond = null;
    let daily = `<div class="empty">${t("Chargement des statistiques…")}</div>`;
    if (this._stats?.error) daily = `<div class="empty err">${esc(this._stats.error)}</div>`;
    else if (this._stats) {
      const sup = this._stats.hour?.[e.supply] || [];
      const mod = new Map((this._stats.hour?.[e.modulation] || []).map((r) => [r.start, r.mean]));
      // heures d'eau chaude écartées : le ballon se charge à 55-75 °C de départ, quelle que soit la courbe
      const dhw = new Map((this._stats.hour?.[e.gas_dhw_day] || []).map((r) => [r.start, r.change]));
      const running = sup.filter((r) => (mod.get(r.start) ?? 0) > 0 && r.mean != null && !((dhw.get(r.start) ?? 0) > 0));
      cond = running.length ? (running.filter((r) => r.mean < CONDENSING_MAX).length / running.length) * 100 : null;
      const hours = new Map(this._dailySeries(e.burner_hours, "change").map((r) => [r.t, r.v]));
      const days = this._dailySeries(e.burner_starts, "change").slice(-30)
        .map((r) => ({ t: r.t, starts: r.v, hours: hours.get(r.t) ?? null }));
      daily = this._columnChart("starts", days, (x) => x.starts, pal.s1, {
        fmtY: (v) => fmt(v, 0),
        tip: (x) => `<b>${dayLabel(x.t)}</b><div>${t("{n} démarrages", { n: fmt(x.starts, 0) })}</div>` +
          (x.hours ? `<div>${t("{h} h de flamme · {m} min par cycle", { h: fmt(x.hours, 0), m: fmt((x.hours * 60) / Math.max(1, x.starts), 0) })}</div>` : ""),
        empty: t("Pas encore de statistiques de démarrage."),
      });
    }
    const cycleWarn = b?.cycle_minutes != null && b.cycle_minutes < d.settings.short_cycle_minutes;
    const advice = cycleWarn
      ? t("Cycles courts : la chaudière s'allume et s'éteint souvent. Un départ moins chaud (courbe plus basse) allonge les cycles et améliore le rendement.")
      : cond != null && cond < 50
        ? t("Moins de la moitié du temps de chauffe se fait avec un départ sous {v} °C : baisser la courbe améliorerait la condensation, donc le rendement.", { v: CONDENSING_MAX })
        : b || cond != null ? t("Fonctionnement correct.") : t("Les indicateurs se remplissent au fil des heures de chauffe.");
    return `<div class="card"><h2>${t("Brûleur et rendement")}</h2>
        <p class="sub">${t("Une chaudière à condensation récupère la chaleur des fumées quand l'eau revient froide : un départ sous {v} °C la garantit.", { v: CONDENSING_MAX })}</p>
        <div class="kpis">
          <div class="kpi"><div class="v">${b ? fmt(b.starts, 0) : "—"}</div><div class="l">${t("démarrages sur {h} h", { h: b ? fmt(b.span_hours, 0) : 24 })}</div></div>
          <div class="kpi"><div class="v">${b?.cycle_minutes != null ? `${fmt(b.cycle_minutes, 0)} min` : "—"}</div>
            <div class="l">${t("de flamme par démarrage")}${cycleWarn ? ` · <b>${t("cycles courts")}</b>` : ""}</div></div>
          <div class="kpi"><div class="v">${cond != null ? `${fmt(cond, 0)} %` : "—"}</div><div class="l">${t("du temps de chauffe en condensation (7 j)")}</div></div>
          <div class="kpi"><div class="v">${fmt(pressure, 1)} bar</div><div class="l">${t("pression d'eau (alerte sous {v} bar)", { v: fmt(d.settings.min_pressure, 1) })}</div></div>
        </div>
        <div class="legend"><span><i class="key-dot" style="background:${pal.s1}"></i>${t("Démarrages du brûleur par jour (30 j)")}</span></div>
        ${daily}
        <div class="advice"><ha-icon icon="mdi:lightbulb-on-outline"></ha-icon><div>${advice}</div></div>
      </div>
      ${this._pressureCard(pal)}
      ${this._maintenanceCard()}`;
  }

  _pressureCard(pal) {
    const d = this._data;
    const days = Object.entries(d.pressure_days || {}).map(([day, v]) => ({ t: new Date(`${day}T12:00:00`).getTime(), v }));
    const trend = d.pressure_trend;
    return `<div class="card"><h2>${t("Pression d'eau")}</h2>
      <p class="sub">${t("Pression minimale de chaque jour. Une baisse lente sur plusieurs semaines signale une petite fuite ou un vase d'expansion à regonfler.")}</p>
      <div class="kpis"><div class="kpi"><div class="v">${trend != null ? `${fmt(trend, 2, true)} bar` : "—"}</div><div class="l">${t("par semaine (tendance sur 4 semaines)")}</div></div></div>
      <div class="legend"><span><i class="key-dot" style="background:${pal.s1}"></i>${t("Pression minimale du jour (bar)")}</span></div>
      ${this._columnChart("pressure", days.slice(-30), (x) => x.v, pal.s1, {
        fmtY: (v) => fmt(v, 1),
        tip: (x) => `<b>${dayLabel(x.t)}</b><div>${t("{v} bar au plus bas", { v: fmt(x.v, 2) })}</div>`,
        empty: t("La pression est relevée chaque jour à partir de maintenant."),
      })}</div>`;
  }

  _maintenanceCard() {
    const m = this._data.maintenance || {};
    const due = m.due ? new Date(`${m.due}T12:00:00`).toLocaleDateString(LOCALE) : null;
    const last = m.last ? new Date(`${m.last}T12:00:00`).toLocaleDateString(LOCALE) : null;
    return `<div class="card"><h2>${t("Entretien annuel")}</h2>
      <p class="sub">${t("Obligatoire chaque année en France pour une chaudière gaz. Un rappel arrive 30 jours avant l'échéance.")}</p>
      <div class="kpis">
        <div class="kpi"><div class="v">${last || "—"}</div><div class="l">${t("dernier entretien")}</div></div>
        <div class="kpi"><div class="v">${due || "—"}</div><div class="l">${m.days_left != null ? (m.days_left < 0 ? t("dépassé de {n} j", { n: -m.days_left }) : t("dans {n} j", { n: m.days_left })) : t("prochaine échéance")}</div></div>
        <div class="kpi"><div class="v">${m.burner_hours_since != null ? `${fmt(m.burner_hours_since, 0)} h` : "—"}</div><div class="l">${t("de brûleur depuis")}</div></div>
      </div>
      <div class="actions"><input type="date" id="maint-date" aria-label="${t("Date de l'entretien")}">
        <button class="btn" data-action="maintenance-done">${t("Enregistrer l'entretien")}</button></div></div>`;
  }

  // ------------------------------------------------------------------ onglet Eau chaude
  _dhwTab() {
    this._ensureStats();
    const d = this._data;
    const e = d.entities;
    const target = num(this._state(e.dhw_target)?.state);
    const storage = num(this._state(e.dhw_storage)?.state);
    const lg = d.legionella;
    let share = "";
    if (this._stats && !this._stats.error) {
      const sum = (id) => this._dailySeries(id, "change").slice(-30).reduce((a, r) => a + r.v, 0);
      const dhw = sum(e.gas_dhw_day);
      const heat = sum(e.gas_heating_day);
      share = `<div class="kpi"><div class="v">${fmt(dhw, 1)} m³</div><div class="l">${t("gaz eau chaude sur 30 j")}${heat + dhw > 0 ? ` ${t("({v} % du total)", { v: fmt((dhw / (heat + dhw)) * 100, 0) })}` : ""}</div></div>`;
    }
    const reco = target != null && target > 50
      ? `<div class="advice"><ha-icon icon="mdi:lightbulb-on-outline"></ha-icon><div>
          ${t("Consigne à {v} °C : 50 °C suffisent au quotidien et réduisent les pertes du ballon, à condition d'activer " +
            "la montée hebdomadaire à {lt} °C contre la légionelle (ci-dessous).", { v: fmt(target, 0), lt: fmt(lg.temp, 0) })}
          <div class="actions" style="margin-top:8px"><button class="btn primary" data-action="set-dhw" data-value="50">${t("Passer à 50 °C")}</button></div></div></div>`
      : "";
    return `<div class="card"><h2>${t("Eau chaude sanitaire")}</h2>
        <div class="kpis">
          <div class="kpi"><div class="v">${fmt(target, 0)} °C</div><div class="l">${t("consigne")}</div></div>
          <div class="kpi"><div class="v">${fmt(storage)} °C</div><div class="l">${t("ballon actuellement")}</div></div>
          ${share}
        </div>${reco}</div>
      <div class="card status">
        <div class="state"><ha-icon icon="mdi:bacteria-outline"></ha-icon><div><b>${t("Montée anti-légionelle hebdomadaire")}</b>
          <small>${t("Chaque {day} à {time} : {temp} °C pendant {min} min, puis retour à la consigne", {
            day: weekdayName(lg.weekday), time: esc(String(lg.time).slice(0, 5)), temp: fmt(lg.temp, 0), min: fmt(lg.minutes, 0),
          })}${lg.running ? ` · <b>${t("en cours")}</b>` : lg.last ? ` · ${t("dernière le {d}", { d: dateFr(lg.last) })}` : ""}</small></div></div>
        <div class="mode clickable" data-action="toggle-legionella"><button class="toggle" role="switch" aria-checked="${lg.enabled}" aria-label="${t("Montée anti-légionelle")}" data-action="toggle-legionella"></button>
          <div>${lg.enabled ? t("Activée") : t("Désactivée")}</div></div>
      </div>`;
  }

  // ------------------------------------------------------------------ onglet Planning
  _draftFromSchedule(schedule) {
    const draft = {};
    for (let d = 0; d < 7; d++) {
      const cells = new Array(48).fill(false);
      for (const [s, e] of schedule[d] || schedule[String(d)] || []) {
        const a = Math.round(toMin(s) / 30);
        const b = Math.round(toMin(e) / 30);
        for (let i = a; i < b && i < 48; i++) cells[i] = true;
      }
      draft[d] = cells;
    }
    return draft;
  }

  _scheduleFromDraft(draft) {
    const out = {};
    for (let d = 0; d < 7; d++) {
      const periods = [];
      let start = null;
      draft[d].forEach((on, i) => {
        if (on && start === null) start = i;
        if (!on && start !== null) { periods.push([fromMin(start * 30), fromMin(i * 30)]); start = null; }
      });
      if (start !== null) periods.push([fromMin(start * 30), "24:00"]);
      out[d] = periods;
    }
    return out;
  }

  _planningTab(pal) {
    const p = this._data.pilot;
    if (!this._draft) {
      this._draft = this._draftFromSchedule(p.schedule);
      this._draftTemps = { ...p.temps };
      this._draftDirty = false;
    }
    const st = p.state;
    const modes = [["off", t("Désactivé")], ["simulation", t("Simulation")], ["active", t("Actif")]];
    const modeColors = { confort: pal.s1, veille: pal.s2, relance: pal.s3, soleil: pal.s4, "réduit": "var(--disabled-color, #9e9e9e)" };
    const modeLabels = { confort: t("Confort"), veille: t("Veille (pas de demande)"), relance: t("Relance anticipée"), soleil: t("Soleil attendu"), "réduit": t("Réduit"), pause: t("En pause") };
    const seg = `<div class="seg" role="radiogroup" aria-label="${t("Pilotage")}">${modes.map(([k, l]) =>
      `<button role="radio" aria-checked="${p.mode === k}" data-action="pilot-mode" data-mode="${k}">${l}</button>`).join("")}</div>`;
    const explain = {
      off: t("Le planning et les consignes de la chaudière s'appliquent comme d'habitude."),
      simulation: t("Le pilote calcule la consigne qu'il appliquerait, sans rien écrire sur la chaudière : regarde la frise ci-dessous pendant quelques jours."),
      active: t("Le pilote écrit la consigne du programme actif de la chaudière. Les consignes d'origine seront remises si tu le désactives."),
    }[p.mode];
    const decision = st
      ? `<div class="kpis" style="margin-top:12px">
          <div class="kpi"><div class="v">${fmt(st.setpoint, 0)} °C</div><div class="l">${p.mode === "active" ? t("consigne appliquée") : t("consigne calculée")}</div></div>
          <div class="kpi"><div class="v"><span class="chip" style="font-size:14px"><i class="key-dot" style="background:${modeColors[st.mode]}"></i>${esc(modeLabels[st.mode] || st.mode)}</span></div>
            <div class="l">${esc(st.reason)}</div></div>
          <div class="kpi"><div class="v">${p.preheat_rate ? `${fmt(p.preheat_rate, 1)} K/h` : "—"}</div><div class="l">${t("vitesse de relance apprise")}</div></div>
          <div class="kpi"><div class="v">${this._data.writes.used} / ${this._data.writes.budget}</div><div class="l">${t("écritures ViCare sur 24 h (quota Viessmann)")}</div></div>
          <div class="kpi"><div class="v">${fmt(p.standby_hours_7d, 0)} h</div><div class="l">${t("de veille sur 7 jours")}${p.mode === "simulation" ? ` ${t("(simulées)")}` : ""}</div></div>
        </div>` : "";

    const days = [t("Lun"), t("Mar"), t("Mer"), t("Jeu"), t("Ven"), t("Sam"), t("Dim")];
    const grid = `<div class="sched" role="grid" aria-label="${t("Planning hebdomadaire")}">
      <div class="sched-hours"><span></span>${Array.from({ length: 8 }, (_, i) => `<span>${String(i * 3).padStart(2, "0")}h</span>`).join("")}</div>
      ${days.map((label, d) => `<div class="sched-row"><span class="sched-day">${label}</span><div class="sched-cells">${this._draft[d]
        .map((on, i) => `<div class="cell ${on ? "on" : ""}" data-day="${d}" data-cell="${i}" title="${label} ${fromMin(i * 30)}–${fromMin((i + 1) * 30)}"></div>`).join("")}</div></div>`).join("")}
    </div>`;
    const dt = this._draftTemps;
    const stepper = (key, label) => `
      <div class="stepper"><span class="name">${label}</span><span class="box">
        <button data-action="draft-temp" data-key="${key}" data-delta="-1" aria-label="${t("Diminuer")}">−</button>
        <output>${fmt(dt[key], 0)} °C</output>
        <button data-action="draft-temp" data-key="${key}" data-delta="1" aria-label="${t("Augmenter")}">+</button></span></div>`;
    const log = (p.decision_log || []);
    const timeline = log.length ? this._timeline(log, modeColors, modeLabels) : `<p class="sub">${t("Aucune décision enregistrée pour l'instant.")}</p>`;
    return `<div class="card"><h2>${t("Pilotage de la consigne")}</h2>
        <p class="sub">${explain}</p>${seg}${decision}
        <p class="note" style="margin-top:8px">${t("Veille : {v} °C après {m} min sans demande de chaleur.", { v: fmt(p.standby_temp, 0), m: fmt(p.demand_delay, 0) })}
          ${p.forecast?.temps?.length ? t("Prévisions : {v} °C au plus bas sur 4 h.", { v: fmt(Math.min(...p.forecast.temps.slice(0, 4)), 0) }) : ""}</p></div>
      <div class="card"><h2>${t("Planning de la semaine")}</h2>
        <p class="sub">${t("Clique ou glisse sur la grille : bleu = confort, vide = réduit (pas de 30 min).")}</p>
        <div class="grid2" style="margin-bottom:12px">${stepper("comfort", t("Consigne confort"))}${stepper("reduced", t("Consigne réduite"))}</div>
        ${grid}
        <div class="actions" style="margin-top:12px">
          <button class="btn primary" data-action="save-schedule" ${this._draftDirty ? "" : "disabled"}>${t("Enregistrer")}</button>
          <button class="btn" data-action="reset-schedule" ${this._draftDirty ? "" : "disabled"}>${t("Annuler")}</button>
          <button class="btn" data-action="import-trv" ${p.trv_suggestion ? "" : "disabled"}>${t("Importer depuis les têtes thermostatiques")}</button>
          <button class="btn" data-action="copy-monday">${t("Copier le lundi sur les jours ouvrés")}</button>
        </div></div>
      ${this._roomTargetsCard()}
      <div class="card"><h2>${t("Décisions des dernières 48 h")}</h2>${timeline}</div>`;
  }

  _roomTargetsCard() {
    const p = this._data.pilot;
    const rooms = Object.keys(p.room_targets || {});
    if (!rooms.length) return "";
    if (!this._roomDraft) this._roomDraft = JSON.parse(JSON.stringify(p.room_targets));
    const name = (id) => this._state(id)?.attributes.friendly_name || id;
    const planned = p.state?.rooms || {};
    const step = (id, key) => `<span class="box">
        <button data-action="room-temp" data-room="${id}" data-key="${key}" data-delta="-0.5" aria-label="${t("Diminuer")}">−</button>
        <output>${fmt(this._roomDraft[id][key], 1)} °C</output>
        <button data-action="room-temp" data-room="${id}" data-key="${key}" data-delta="0.5" aria-label="${t("Augmenter")}">+</button></span>`;
    return `<div class="card"><h2>${t("Consignes des pièces")}</h2>
      <p class="sub">${t("Les pièces cochées suivent le planning de la maison : consigne confort pendant les périodes bleues, réduite sinon.")}
        ${t("Désactive les autres plannings de ces pièces (têtes, Scheduler) pour éviter qu'ils se contredisent.")}</p>
      <div class="table-wrap"><table class="rooms"><thead><tr><th>${t("Pièce")}</th><th>${t("Suit le planning")}</th><th>${t("Confort")}</th><th>${t("Réduit")}</th><th>${t("Consigne prévue")}</th></tr></thead>
      <tbody>${rooms.map((id) => {
        const rt = this._roomDraft[id];
        return `<tr><td>${esc(name(id))}</td>
          <td><button class="toggle" role="switch" aria-checked="${rt.enabled}" aria-label="${t("Suit le planning")}" data-action="room-enable" data-room="${id}"></button></td>
          <td class="cellstep">${step(id, "comfort")}</td><td class="cellstep">${step(id, "reduced")}</td>
          <td>${planned[id] != null ? `${fmt(planned[id], 1)} °C${p.mode === "active" ? "" : ` ${t("(simulé)")}`}` : "—"}</td></tr>`;
      }).join("")}</tbody></table></div>
      <div class="actions" style="margin-top:12px"><button class="btn primary" data-action="save-rooms" ${this._roomDirty ? "" : "disabled"}>${t("Enregistrer")}</button>
        <button class="btn" data-action="reset-rooms" ${this._roomDirty ? "" : "disabled"}>${t("Annuler")}</button></div></div>`;
  }

  _timeline(log, colors, labels) {
    const w = this._widths.timeline || 600;
    const now = Date.now() / 1000;
    const t0 = now - 48 * 3600;
    const x = (t) => 40 + ((Math.max(t, t0) - t0) / (now - t0)) * (w - 52);
    const segs = log.map((e, i) => ({ t: e[0], mode: e[1], sp: e[2], end: i + 1 < log.length ? log[i + 1][0] : now }))
      .filter((s) => s.end > t0);
    const ticks = [];
    for (let k = 0; k <= 4; k++) ticks.push(t0 + (k * 12) * 3600);
    const used = [...new Set(segs.map((s) => s.mode))];
    this._charts.timeline = {
      f: { w, iw: w - 52 },
      generic: (px) => {
        const t = t0 + ((px - 40) / (w - 52)) * (now - t0);
        const s = segs.find((z) => z.t <= t && t < z.end) || segs[segs.length - 1];
        return { x: px, y: 22, html: `<b>${esc(labels[s.mode] || s.mode)}</b><div>${fmt(s.sp, 0)} °C · ${dateFr(s.t)} → ${dateFr(s.end)}</div>` };
      },
    };
    return `<div class="legend">${used.map((m) => `<span><i class="key-dot" style="background:${colors[m]}"></i>${esc(labels[m] || m)}</span>`).join("")}</div>
      <div class="chart" data-chart="timeline"><svg width="${w}" height="64" role="img" aria-label="${t("Frise des décisions du pilote")}">
        ${segs.map((s) => `<rect x="${x(s.t)}" y="8" width="${Math.max(1, x(s.end) - x(s.t) - 1)}" height="28" rx="3" fill="${colors[s.mode] || "gray"}"/>`).join("")}
        ${ticks.map((t) => `<text x="${x(t)}" y="56" text-anchor="middle">${new Date(t * 1000).toLocaleString(LOCALE, { weekday: "short", hour: "2-digit", minute: "2-digit" })}</text>`).join("")}
        <g class="hover" style="display:none"><circle r="4" fill="var(--primary-text-color)"/></g>
        <rect class="hit" x="40" y="4" width="${w - 52}" height="36" fill="transparent"/>
      </svg><div class="tooltip"></div></div>`;
  }

  _bindSchedule() {
    const grid = this.shadowRoot.querySelector(".sched");
    if (!grid) return;
    const paint = (cell) => {
      const d = +cell.dataset.day;
      const i = +cell.dataset.cell;
      if (this._draft[d][i] === this._paintValue) return;
      this._draft[d][i] = this._paintValue;
      cell.classList.toggle("on", this._paintValue);
      this._draftDirty = true;
      this.shadowRoot.querySelectorAll('[data-action="save-schedule"],[data-action="reset-schedule"]').forEach((b) => { b.disabled = false; });
    };
    grid.addEventListener("pointerdown", (e) => {
      const cell = e.target.closest(".cell");
      if (!cell) return;
      e.preventDefault();
      this._painting = true;
      this._paintValue = !this._draft[+cell.dataset.day][+cell.dataset.cell];
      paint(cell);
    });
    grid.addEventListener("pointerover", (e) => {
      const cell = e.target.closest(".cell");
      if (cell && this._painting) paint(cell);
    });
    const stop = () => { this._painting = false; };
    grid.addEventListener("pointerup", stop);
    grid.addEventListener("pointerleave", stop);
  }

  // ------------------------------------------------------------------ onglet Diagnostic
  _ensureDiagnostics() {
    if (this._diag || this._diagLoading) return;
    this._diagLoading = true;
    Promise.all([
      this._hass.callWS({ type: `${DOMAIN}/diagnostics` }),
      this._hass.callWS({ type: `${DOMAIN}/weekly_report` }),
    ])
      .then(([diag, report]) => { this._diag = { ...diag, report: report.text }; })
      .catch((err) => { this._diag = { error: err?.message || String(err) }; })
      .finally(() => { this._diagLoading = false; this._render(); });
  }

  _diagnosticTab(pal) {
    this._ensureDiagnostics();
    const g = this._diag;
    if (!g) return `<div class="card"><div class="empty">${t("Analyse en cours…")}</div></div>`;
    if (g.error) return `<div class="card"><div class="empty err">${esc(g.error)}</div></div>`;
    const name = (id) => this._state(id)?.attributes.friendly_name || id;
    const seasons = Object.entries(g.thermal || {});
    const thermal = seasons.length
      ? `<div class="table-wrap"><table><thead><tr><th>${t("Saison de chauffe")}</th><th>${t("Déperditions")}</th><th>${t("Talon")}</th><th>${t("Fiabilité (R²)")}</th><th>${t("Jours")}</th><th>${t("Seuil de chauffe")}</th></tr></thead>
        <tbody>${seasons.map(([season, th]) => th.loss_w_per_k != null
          ? `<tr><td>${esc(season)}</td><td><b>${fmt(th.loss_w_per_k, 0)} W/K</b></td><td>${t("{v} kWh/j", { v: fmt(th.base_kwh_per_day, 1) })}</td><td>${fmt(th.r2, 2)}</td><td>${th.days}</td>
            <td>${th.heating_limit != null ? `${fmt(th.heating_limit, 1)} °C <button class="btn" style="padding:2px 8px" data-action="use-limit" data-value="${th.heating_limit}">${t("Utiliser")}</button>` : "—"}</td></tr>`
          : `<tr><td>${esc(season)}</td><td colspan="5">${t("pas assez de jours de chauffe ({n})", { n: th.days })}</td></tr>`).join("")}</tbody></table></div>`
      : `<div class="empty">${t("Pas encore de statistiques de gaz.")}</div>`;
    const rooms = g.rooms || [];
    const maxRel = Math.max(1.8, ...rooms.map((r) => r.relative));
    const balance = rooms.length
      ? `<div class="table-wrap"><table><thead><tr><th>${t("Pièce")}</th><th>${t("Puissance de chauffe relative")}</th><th>${t("Apports internes")}</th><th>${t("Conseil")}</th></tr></thead>
        <tbody>${rooms.map((r) => `<tr><td>${esc(name(r.entity_id))}</td>
          <td><div class="bar"><div style="width:${(r.relative / maxRel) * 100}%;background:${pal.s1}"></div></div>${t("{v} % de la médiane", { v: fmt(r.relative * 100, 0) })}</td>
          <td><button class="chip${r.internal_gains ? " on" : ""}" data-action="toggle-gains" data-entity="${esc(r.entity_id)}" data-value="${r.internal_gains ? "0" : "1"}"
            title="${esc(t("Cliquer pour indiquer une pièce chauffée aussi par la cuisson, un poêle…"))}" aria-pressed="${r.internal_gains ? "true" : "false"}">${r.internal_gains ? t("apports internes") : t("aucun")}</button></td>
          <td style="white-space:normal">${esc(r.advice)}</td></tr>`).join("")}</tbody></table></div>`
      : `<div class="empty">${t("Il faut au moins deux pièces suivies avec Better Thermostat (onglet Pièces).")}</div>`;
    const rep = this._data.report;
    return `<div class="card"><h2>${t("Bilan thermique de la maison")}</h2>
        <p class="sub">${t("Moins de W/K = maison mieux isolée : compare les saisons avant et après des travaux.")}</p>${thermal}
        ${info(
          t("Déperditions estimées à partir du gaz consommé et de l'écart intérieur / extérieur, jour par jour (rendement supposé 95 %)."),
          t("Le seuil de chauffe est la température extérieure au-dessus de laquelle les apports gratuits (soleil, occupants, appareils) suffisent."),
        )}
        ${(this._data.overconsumption_log || []).length ? `<h2 style="margin-top:16px">${t("Jours de surconsommation")}</h2>
          <div class="table-wrap"><table><thead><tr><th>${t("Jour")}</th><th>${t("Consommé")}</th><th>${t("Attendu pour la météo")}</th></tr></thead>
          <tbody>${[...this._data.overconsumption_log].reverse().map((o) => `<tr><td>${dayLabel(o.t * 1000)}</td><td>${fmt(o.kwh, 0)} kWh</td><td>${fmt(o.expected, 0)} kWh</td></tr>`).join("")}</tbody></table></div>` : ""}</div>
      <div class="card"><h2>${t("Équilibrage des radiateurs")}</h2>
        <p class="sub">${t("Vitesse de chauffe apprise par Better Thermostat pour chaque pièce, comparée à la médiane.")}</p>${balance}
        ${info(
          t("Un radiateur qui chauffe beaucoup plus vite que les autres « vole » l'eau chaude aux pièces lentes."),
          t("Cochez « apports internes » pour une pièce chauffée aussi par autre chose que son radiateur (cuisine, poêle, cheminée) : elle est alors exclue de la médiane et un écart vers le haut n'est qu'à confirmer."),
        )}</div>
      <div class="card"><h2>${t("Bilan hebdomadaire")}</h2>
        <p class="sub">${rep.enabled ? t("Envoyé chaque {day} à {time}", { day: weekdayName(rep.weekday), time: esc(String(rep.time).slice(0, 5)) }) : t("Envoi désactivé")}
          ${rep.notify ? t("sur {target} et", { target: esc(rep.notify) }) : ""} ${t("dans les notifications de Home Assistant.")}</p>
        <pre class="report">${esc(g.report || "")}</pre>
        <div class="actions"><button class="btn" data-action="send-report">${t("Envoyer maintenant")}</button>
          <button class="btn" data-action="reload-diag">${t("Actualiser")}</button></div></div>`;
  }

  // ------------------------------------------------------------------ onglet Réglages
  _ensureSettings() {
    if (this._settingsDef || this._settingsLoading) return;
    this._settingsLoading = true;
    this._hass.callWS({ type: `${DOMAIN}/get_settings` })
      .then((def) => {
        this._settingsDef = def;
        this._settingsDraft = JSON.parse(JSON.stringify(def.values));
        this._settingsDirty = false;
      })
      .catch((err) => { this._settingsDef = { error: err?.message || String(err) }; })
      .finally(() => { this._settingsLoading = false; this._render(); });
  }

  _settingsTab() {
    this._ensureSettings();
    const def = this._settingsDef;
    if (!def) return `<div class="card"><div class="empty">${t("Chargement…")}</div></div>`;
    if (def.error) return `<div class="card"><div class="empty err">${esc(def.error)}</div></div>`;
    const v = this._settingsDraft;
    const ch = def.choices;
    const opt = (list, current, empty) => (empty ? `<option value="">${t("— aucun —")}</option>` : "") +
      list.map((c) => `<option value="${esc(c.value)}" ${String(current) === String(c.value) ? "selected" : ""}>${esc(c.label)}</option>`).join("");
    const checks = (key, list) => `<div class="checks">${list.map((c) => {
      const value = typeof c === "string" ? c : c.value;
      const label = typeof c === "string" ? c : c.label;
      return `<label class="check"><input type="checkbox" data-key="${key}" data-list-value="${esc(value)}" ${(v[key] || []).includes(value) ? "checked" : ""}> ${esc(label)}</label>`;
    }).join("")}</div>`;
    const input = (f) => {
      const val = v[f.key];
      switch (f.kind) {
        case "number":
          return `<span class="num"><input type="number" data-key="${f.key}" min="${f.min}" max="${f.max}" step="${f.step}" value="${val ?? ""}">${f.unit ? `<small>${esc(f.unit)}</small>` : ""}</span>`;
        case "bool":
          return `<button class="toggle" role="switch" aria-checked="${!!val}" aria-label="${esc(f.label)}" data-action="settings-toggle" data-key="${f.key}"></button>`;
        case "time":
          return `<input type="time" step="60" data-key="${f.key}" value="${esc(String(val || "").slice(0, 5))}">`;
        case "date":
          return `<input type="date" data-key="${f.key}" value="${esc(val || "")}">`;
        case "weekday":
          return `<select data-key="${f.key}">${opt(ch.weekday, val)}</select>`;
        case "programs":
          return checks(f.key, ch.programs.map((code) => ({ value: code, label: programLabel(code) })));
        case "entities":
          return checks(f.key, ch.climate);
        case "entity":
          return `<select data-key="${f.key}">${opt(f.domain === "weather" ? ch.weather : ch.sensor, val, true)}</select>`;
        case "notify":
          return `<select data-key="${f.key}">${opt(ch.notify.map((s) => ({ value: s, label: s })), val, true)}</select>`;
        default:
          return `<input type="text" data-key="${f.key}" value="${esc(val || "")}">`;
      }
    };
    const block = (fields) => fields.map((f) => `<div class="field ${["programs", "entities"].includes(f.kind) ? "wide" : ""}">
        <label>${esc(f.label)}</label>${input(f)}</div>`).join("");
    const general = def.fields.filter((f) => f.section === null);
    const cards = def.sections.map((s) => {
      const fields = def.fields.filter((f) => f.section === s.key);
      return `<div class="card"><h2>${esc(s.name)}</h2>${s.description ? `<p class="sub">${esc(s.description)}</p>` : ""}
        <div class="fields">${block(fields)}</div></div>`;
    }).join("");
    const bar = `<div class="card savebar"><span>${this._settingsDirty ? t("Modifications non enregistrées") : t("Tous les réglages de l'optimiseur, au même endroit.")}</span>
      <div class="actions"><button class="btn" data-action="settings-reset" ${this._settingsDirty ? "" : "disabled"}>${t("Annuler")}</button>
      <button class="btn primary" data-action="settings-save" ${this._settingsDirty ? "" : "disabled"}>${t("Enregistrer")}</button></div></div>`;
    return `${bar}<div class="card"><h2>${t("Général")}</h2><div class="fields">${block(general)}</div></div>${cards}`;
  }

  _bindSettings() {
    const root = this.shadowRoot;
    root.querySelectorAll("[data-key]").forEach((el) => {
      if (el.tagName !== "INPUT" && el.tagName !== "SELECT") return;
      el.addEventListener("change", () => {
        const key = el.dataset.key;
        const v = this._settingsDraft;
        if (el.type === "checkbox") {
          const set = new Set(v[key] || []);
          if (el.checked) set.add(el.dataset.listValue); else set.delete(el.dataset.listValue);
          v[key] = [...set];
        } else if (el.type === "number") {
          v[key] = el.value === "" ? v[key] : parseFloat(el.value);
        } else if (el.type === "time") {
          v[key] = el.value ? `${el.value}:00` : v[key];
        } else {
          v[key] = el.value;
        }
        this._settingsDirty = true;
        root.querySelectorAll('[data-action="settings-save"],[data-action="settings-reset"]').forEach((b) => { b.disabled = false; });
        const msg = root.querySelector(".savebar > span");
        if (msg) msg.textContent = t("Modifications non enregistrées");
      });
    });
  }

  // ------------------------------------------------------------------ prévision de facture
  _ensureBill() {
    if (this._bill || this._billLoading) return;
    this._billLoading = true;
    this._hass.callWS({ type: `${DOMAIN}/bill_forecast` })
      .then((r) => { this._bill = r; })
      .catch((err) => { this._bill = { error: err?.message || String(err) }; })
      .finally(() => { this._billLoading = false; this._render(); });
  }

  _billCard() {
    this._ensureBill();
    const b = this._bill;
    let body;
    if (!b) body = `<p class="sub">${t("Calcul en cours…")}</p>`;
    else if (b.error) body = `<p class="sub err">${esc(b.error)}</p>`;
    else if (!b.forecast) body = `<div class="advice"><ha-icon icon="mdi:information-outline"></ha-icon><div>${t("Renseigne ta facture dans l'onglet Réglages (section « Facture et mensualités ») : début de période, mensualité, abonnement et consommation de référence.")}</div></div>`;
    else {
      const f = b.forecast;
      const d = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString(LOCALE, { day: "numeric", month: "long", year: "numeric" });
      const money = (x) => t("{v} €", { v: fmt(x, 0) });
      const balance = f.balance >= 0
        ? t("≈ {v} à payer à la régularisation", { v: money(f.balance) })
        : t("≈ {v} remboursés à la régularisation", { v: money(-f.balance) });
      body = `<div class="kpis">
          <div class="kpi"><div class="v">${fmt(f.consumed_kwh, 0)} kWh</div><div class="l">${t("consommés depuis le {d}", { d: d(f.period_start) })}</div></div>
          <div class="kpi"><div class="v">${fmt(f.total_kwh, 0)} kWh</div><div class="l">${t("estimés sur l'année (reste selon un profil mensuel type)")}</div></div>
          <div class="kpi"><div class="v">${money(f.total_cost)}</div><div class="l">${t("facture annuelle estimée TTC")}</div></div>
          <div class="kpi"><div class="v">${money(f.payments)}</div><div class="l">${t("mensualités prévues")}</div></div>
        </div>
        <div class="advice"><ha-icon icon="mdi:cash-check"></ha-icon><div><b>${balance}</b> ${t("(fin de période le {d})", { d: d(f.period_end) })}.
          ${t("Estimation : elle s'affine au fil de l'hiver, et dépend surtout de la météo à venir.")}</div></div>`;
    }
    return `<div class="card"><h2>${t("Prévision de la facture")}</h2>${body}</div>`;
  }

  // ------------------------------------------------------------------ graphique en colonnes (une série, par jour)
  _columnChart(id, rows, value, color, opts = {}) {
    if (!rows.length) return `<div class="chart" data-chart="${id}"><div class="empty">${esc(opts.empty || t("Pas de données"))}</div></div>`;
    const w = this._widths[id] || 600;
    const h = 220;
    const m = { l: 44, r: 12, t: 10, b: 28 };
    const iw = w - m.l - m.r;
    const ih = h - m.t - m.b;
    const t0 = rows[0].t;
    const t1 = rows[rows.length - 1].t;
    const span = Math.max(1, Math.round((t1 - t0) / DAY) + 1);
    const slot = iw / span;
    const bw = Math.max(2, Math.min(24, slot - 2));
    const x = (t) => m.l + ((t - t0) / DAY + 0.5) * slot;
    const max = Math.max(...rows.map(value)) || 1;
    const ticks = niceTicks(0, max * 1.1, 4);
    // la dernière graduation doit couvrir la plus grande valeur, sinon les barres débordent
    const tickStep = ticks.length > 1 ? ticks[1] - ticks[0] : max;
    while (ticks[ticks.length - 1] < max) ticks.push(+(ticks[ticks.length - 1] + tickStep).toFixed(6));
    const yMax = ticks[ticks.length - 1] || max;
    const y = (v) => m.t + (1 - v / yMax) * ih;
    const every = Math.max(1, Math.ceil(span / Math.max(2, Math.floor(iw / 70))));
    const labels = [];
    for (let i = 0; i < span; i += every) labels.push(t0 + i * DAY);
    const bar = (r) => {
      const top = y(value(r));
      const hh = Math.max(0, m.t + ih - top);
      const rr = Math.min(4, bw / 2, hh);
      const x0 = x(r.t) - bw / 2;
      return `<path d="M${x0},${m.t + ih}V${top + rr}Q${x0},${top} ${x0 + rr},${top}H${x0 + bw - rr}Q${x0 + bw},${top} ${x0 + bw},${top + rr}V${m.t + ih}Z" fill="${color}"/>`;
    };
    const markers = (opts.markers || []).filter((t) => t >= t0 - DAY / 2 && t <= t1 + DAY);
    this._charts[id] = {
      f: { w, iw },
      generic: (px) => {
        const t = t0 + Math.floor((px - m.l) / slot) * DAY;
        const r = rows.reduce((best, z) => (Math.abs(z.t - t) < Math.abs(best.t - t) ? z : best));
        return { x: x(r.t), y: y(value(r)), html: opts.tip ? opts.tip(r) : fmt(value(r)) };
      },
    };
    return `<div class="chart" data-chart="${id}">
      <svg width="${w}" height="${h}" role="img">
        ${ticks.map((v) => `<line class="grid" x1="${m.l}" x2="${w - m.r}" y1="${y(v)}" y2="${y(v)}"/>
          <text x="${m.l - 8}" y="${y(v) + 4}" text-anchor="end">${opts.fmtY ? opts.fmtY(v) : v}</text>`).join("")}
        ${labels.map((t) => `<text x="${x(t)}" y="${h - 8}" text-anchor="middle">${dayLabel(t)}</text>`).join("")}
        ${rows.map(bar).join("")}
        ${markers.map((t) => `<line x1="${x(t)}" x2="${x(t)}" y1="${m.t}" y2="${m.t + ih}" stroke="${this._palette().s2}" stroke-width="2"/>`).join("")}
        <g class="hover" style="display:none"><circle r="5" fill="var(--primary-text-color)" stroke="var(--card-background-color)" stroke-width="2"/></g>
        <rect class="hit" x="${m.l}" y="${m.t}" width="${iw}" height="${ih}" fill="transparent"/>
      </svg><div class="tooltip"></div></div>`;
  }


  _controlCard(live, proposal) {
    const cur = this._edit || { slope: live.slope, shift: live.shift };
    const changed = !!this._edit;
    const tgt = live.target ?? 20;
    const effect = [-10, 0, 10]
      .map((ot) => {
        const a = live.slope != null ? supplyAt(ot, tgt, live.slope, live.shift) : null;
        const b = supplyAt(ot, tgt, cur.slope, cur.shift);
        return `${t("à {ot} °C :", { ot })} <b>${fmt(a, 0)}${changed ? ` → ${fmt(b, 0)}` : ""} °C</b>`;
      })
      .join("<br>");
    const stepper = (field, label, hint, value, step, min, max, signed) => `
      <div class="stepper">
        <span class="name">${label}<small>${hint}</small></span>
        <span class="box">
          <button data-action="step" data-field="${field}" data-delta="${-step}" ${value <= min ? "disabled" : ""} aria-label="${t("Diminuer")}">−</button>
          <output class="${changed && value !== live[field] ? "changed" : ""}">${fmt(value, field === "slope" ? 1 : 0, signed)}</output>
          <button data-action="step" data-field="${field}" data-delta="${step}" ${value >= max ? "disabled" : ""} aria-label="${t("Augmenter")}">+</button>
        </span>
      </div>`;
    const proposalBlock = proposal
      ? `<div class="proposal">
          <p><b>${t("Proposition")}</b> <small>· ${dateFr(proposal.t)}</small></p>
          <p>${t("Pente {s0} → <b>{s1}</b>, décalage {h0} → <b>{h1}</b>", {
            s0: fmt(proposal.slope), s1: fmt(proposal.new_slope), h0: fmt(proposal.shift, 0, true), h1: fmt(proposal.new_shift, 0, true),
          })}<br>
            <small>${esc(proposal.reason)} · ${t("écart moyen {v} K", { v: fmt(proposal.mean_error, 2, true) })}</small></p>
          <div class="actions">
            <button class="btn primary" data-action="apply-proposal">${t("Appliquer la proposition")}</button>
            <button class="btn" data-action="load-proposal">${t("Ajuster avant")}</button>
          </div>
        </div>`
      : "";
    return `
      <div class="card ctrl">
        <div><h2>${t("Réglage manuel")}</h2><p class="sub" style="margin:0">${t("Modifie la courbe et visualise l'effet avant d'appliquer")}</p></div>
        ${stepper("slope", t("Pente"), t("inclinaison de la courbe"), cur.slope, 0.1, 0.2, 3.5, false)}
        ${stepper("shift", t("Décalage"), t("translation verticale (K)"), cur.shift, 1, -13, 40, true)}
        <div class="effect">${t("Température de départ")}<br>${effect}</div>
        <div class="actions">
          <button class="btn primary" data-action="apply-edit" ${changed ? "" : "disabled"}>${t("Appliquer à la chaudière")}</button>
          <button class="btn" data-action="reset" ${changed ? "" : "disabled"}>${t("Annuler")}</button>
        </div>
        <p class="note">${t("Un réglage appliqué remet à zéro les mesures en cours : elles décrivaient l'ancienne courbe.")}</p>
        ${proposalBlock}
        ${this._data.computed_curve ? `<div class="proposal">
          <p><b>${t("Courbe calculée")}</b> <small>· ${t("modèle physique des radiateurs")}</small></p>
          <p>${t("Pente <b>{s}</b>, décalage <b>{h}</b>", { s: fmt(this._data.computed_curve.slope), h: fmt(this._data.computed_curve.shift, 0, true) })}<br>
            <small>${t("Calculée d'un coup à partir des mesures en cours, extrapolée aux grands froids " +
            "(écart au modèle {v} K). À vérifier avant d'appliquer.", { v: fmt(this._data.computed_curve.rms, 1) })}</small></p>
          <div class="actions"><button class="btn" data-action="load-computed">${t("Voir sur le graphique")}</button></div>
        </div>` : ""}
      </div>`;
  }

  _progress(d, s, pal) {
    const pct = Math.min(100, (d.samples.length / s.min_samples) * 100);
    return `
      <div class="meter" style="background:${pal.s1}26"><div style="width:${pct}%;background:${pal.s1}"></div></div>
      <div class="meta"><span>${pct >= 100 ? t("{n} mesures, minimum de {min} atteint : évaluation possible", { n: d.samples.length, min: s.min_samples }) : t("{n} / {min} mesures avant la prochaine évaluation", { n: d.samples.length, min: s.min_samples })}</span>
        <span>${pct >= 100 ? t("prêt") : `${Math.round(pct)} %`}</span></div>`;
  }

  // ------------------------------------------------------------------ graphiques
  _frame(id) {
    const w = this._widths[id] || 600;
    const iw = w - MARGIN.l - MARGIN.r;
    const ih = CHART_H - MARGIN.t - MARGIN.b;
    const x = (v) => MARGIN.l + ((v - X_MIN) / (X_MAX - X_MIN)) * iw;
    return { w, iw, ih, x };
  }

  _axes(f, y, yTicks, yFmt) {
    const xTicks = niceTicks(X_MIN, X_MAX, 7);
    return `
      ${yTicks.map((v) => `<line class="grid" x1="${MARGIN.l}" x2="${f.w - MARGIN.r}" y1="${y(v)}" y2="${y(v)}"/>
        <text x="${MARGIN.l - 8}" y="${y(v) + 4}" text-anchor="end">${yFmt(v)}</text>`).join("")}
      ${xTicks.map((v) => `<text x="${f.x(v)}" y="${CHART_H - 8}" text-anchor="middle">${v} °C</text>`).join("")}`;
  }

  _curveChart(live, alt, pal) {
    const id = "curve";
    if (live.slope == null || live.target == null) {
      return `<div class="chart" data-chart="${id}"><div class="empty">${t("Pente, décalage ou consigne indisponibles pour l'instant.")}</div></div>`;
    }
    const f = this._frame(id);
    const tgt = live.target;
    const xs = [];
    for (let v = X_MIN; v <= X_MAX + 1e-9; v += 0.5) xs.push(v);
    const curves = [{ key: "cur", label: t("Actuelle"), slope: live.slope, shift: live.shift, color: pal.s1, dash: "" }];
    if (alt) curves.push({ key: "alt", label: alt.label, slope: alt.slope, shift: alt.shift, color: pal.s2, dash: "6 4" });
    const all = curves.flatMap((c) => xs.map((v) => supplyAt(v, tgt, c.slope, c.shift)));
    if (live.supply != null) all.push(live.supply);
    const yMin = Math.floor((Math.min(...all) - 3) / 5) * 5;
    const yMax = Math.ceil((Math.max(...all) + 3) / 5) * 5;
    const y = (v) => MARGIN.t + (1 - (v - yMin) / (yMax - yMin)) * f.ih;
    const limit = this._data.settings.heating_limit;
    const path = (c) => xs.map((v, i) => `${i ? "L" : "M"}${f.x(v).toFixed(1)},${y(supplyAt(v, tgt, c.slope, c.shift)).toFixed(1)}`).join("");
    const op = live.outside != null && live.supply != null && live.outside >= X_MIN && live.outside <= X_MAX;

    this._charts[id] = {
      f,
      tip: (ot) => `<b>${t("{v} °C extérieur", { v: fmt(ot) })}</b>` +
        curves.map((c) => `<div class="row"><i style="background:${c.color}"></i>${t("{label} : {v} °C", { label: esc(c.label), v: fmt(supplyAt(ot, tgt, c.slope, c.shift)) })}</div>`).join(""),
      dots: (ot) => curves.map((c) => ({ x: f.x(ot), y: y(supplyAt(ot, tgt, c.slope, c.shift)), color: c.color })),
    };
    return `<div class="chart" data-chart="${id}">
      <svg width="${f.w}" height="${CHART_H}" role="img" aria-label="${t("Courbe de chauffe : température de départ selon la température extérieure")}">
        ${limit < X_MAX ? `<rect x="${f.x(limit)}" y="${MARGIN.t}" width="${f.x(X_MAX) - f.x(limit)}" height="${f.ih}" fill="var(--divider-color)" opacity=".35"/>
          <text x="${f.x(X_MAX) - 6}" y="${MARGIN.t + 14}" text-anchor="end">${t("hors chauffe")}</text>` : ""}
        ${CONDENSING_MAX > yMin ? `<rect x="${MARGIN.l}" y="${y(Math.min(CONDENSING_MAX, yMax))}" width="${f.iw}" height="${y(yMin) - y(Math.min(CONDENSING_MAX, yMax))}" fill="${pal.s1}" opacity=".07"/>
          <text x="${MARGIN.l + 6}" y="${y(yMin) - 8}">${t("condensation assurée (départ &lt; {v} °C)", { v: CONDENSING_MAX })}</text>` : ""}
        ${this._axes(f, y, niceTicks(yMin, yMax, 5), (v) => `${v}°`)}
        ${curves.map((c) => `<path d="${path(c)}" fill="none" stroke="${c.color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" ${c.dash ? `stroke-dasharray="${c.dash}"` : ""}/>`).join("")}
        ${op ? `<circle cx="${f.x(live.outside)}" cy="${y(live.supply)}" r="5" fill="var(--primary-text-color)" stroke="var(--card-background-color)" stroke-width="2"/>` : ""}
        <g class="hover" style="display:none">
          <line class="cross" y1="${MARGIN.t}" y2="${MARGIN.t + f.ih}" stroke="var(--secondary-text-color)" stroke-width="1" opacity=".5"/>
          ${curves.map(() => `<circle r="4.5" stroke="var(--card-background-color)" stroke-width="2"/>`).join("")}
        </g>
        <rect class="hit" x="${MARGIN.l}" y="${MARGIN.t}" width="${f.iw}" height="${f.ih}" fill="transparent"/>
      </svg><div class="tooltip"></div></div>`;
  }

  _errorChart(samples, s, pal) {
    const id = "error";
    if (!samples.length) {
      return `<div class="chart" data-chart="${id}"><div class="empty">
        ${t("Pas encore de mesures. La collecte démarre quand il fait moins de {v} °C dehors " +
        "et que la chaudière est en programme {p} depuis au moins 2 h.", { v: fmt(s.heating_limit, 0), p: esc(s.programs.join(", ")) })}</div></div>`;
    }
    const f = this._frame(id);
    const pts = samples.map((p) => ({ outside: p.outside, error: clamp(sampleErr(p), -3, 3) }));
    const bins = binSamples(samples);
    const lim = Math.max(1, Math.ceil(Math.max(...pts.map((p) => Math.abs(p.error)), s.deadband)));
    const y = (v) => MARGIN.t + (1 - (v + lim) / (2 * lim)) * f.ih;
    const inX = (v) => v >= X_MIN && v <= X_MAX;

    this._charts[id] = {
      f,
      nearest: (ot) => {
        const pool = bins.length ? bins : pts.map((p) => ({ ...p, count: 1 }));
        return pool.reduce((best, b) => (Math.abs(b.outside - ot) < Math.abs(best.outside - ot) ? b : best));
      },
      tipFor: (b) => `<b>≈ ${t("{v} °C extérieur", { v: fmt(b.outside) })}</b>
        <div class="row"><i style="background:${pal.s2}"></i>${bins.length ? t("Écart médian : {v} K", { v: fmt(b.error, 2, true) }) : t("Écart : {v} K", { v: fmt(b.error, 2, true) })}</div>
        <div>${b.count > 1 ? t("{n} mesures", { n: b.count }) : t("{n} mesure", { n: b.count })}</div>
        <div style="color:var(--secondary-text-color)">${b.error > s.deadband ? t("trop chaud") : b.error < -s.deadband ? t("trop froid") : t("dans la tolérance")}</div>`,
      pos: (b) => ({ x: f.x(b.outside), y: y(b.error) }),
    };
    return `<div class="chart" data-chart="${id}">
      <svg width="${f.w}" height="${CHART_H}" role="img" aria-label="${t("Écart entre température ambiante et consigne selon la température extérieure")}">
        <rect x="${MARGIN.l}" y="${y(s.deadband)}" width="${f.iw}" height="${y(-s.deadband) - y(s.deadband)}" fill="var(--secondary-text-color)" opacity=".12"/>
        ${this._axes(f, y, niceTicks(-lim, lim, 4), (v) => `${v > 0 ? "+" : ""}${v} K`)}
        <line class="zero" x1="${MARGIN.l}" x2="${f.w - MARGIN.r}" y1="${y(0)}" y2="${y(0)}"/>
        <text x="${f.w - MARGIN.r}" y="${y(lim) + 12}" text-anchor="end">${t("trop chaud")} ↑</text>
        <text x="${f.w - MARGIN.r}" y="${y(-lim) - 6}" text-anchor="end">${t("trop froid")} ↓</text>
        ${pts.filter((p) => inX(p.outside)).map((p) => `<circle cx="${f.x(p.outside).toFixed(1)}" cy="${y(p.error).toFixed(1)}" r="4" fill="${pal.s1}" opacity=".35"/>`).join("")}
        ${bins.length > 1 ? `<path d="${bins.map((b, i) => `${i ? "L" : "M"}${f.x(b.outside).toFixed(1)},${y(b.error).toFixed(1)}`).join("")}" fill="none" stroke="${pal.s2}" stroke-width="2" stroke-linejoin="round"/>` : ""}
        ${bins.map((b) => `<circle cx="${f.x(b.outside)}" cy="${y(b.error)}" r="5" fill="${pal.s2}" stroke="var(--card-background-color)" stroke-width="2"/>`).join("")}
        <g class="hover" style="display:none"><circle r="7" fill="none" stroke="var(--primary-text-color)" stroke-width="2"/></g>
        <rect class="hit" x="${MARGIN.l}" y="${MARGIN.t}" width="${f.iw}" height="${f.ih}" fill="transparent"/>
      </svg><div class="tooltip"></div></div>`;
  }

  _bindHover() {
    this.shadowRoot.querySelectorAll("[data-chart]").forEach((el) => {
      const id = el.dataset.chart;
      const chart = this._charts[id];
      const hit = el.querySelector(".hit");
      if (!chart || !hit) return;
      const g = el.querySelector(".hover");
      const tip = el.querySelector(".tooltip");
      const place = (px, py, html) => {
        tip.innerHTML = html;
        tip.style.display = "block";
        const tw = tip.offsetWidth;
        const left = px + 14 + tw > chart.f.w ? px - 14 - tw : px + 14;
        tip.style.left = `${Math.max(0, left)}px`;
        tip.style.top = `${Math.max(0, py - tip.offsetHeight / 2)}px`;
      };
      hit.addEventListener("pointermove", (e) => {
        const rect = hit.ownerSVGElement.getBoundingClientRect();
        const px = e.clientX - rect.left;
        const ot = clamp(X_MIN + ((px - MARGIN.l) / chart.f.iw) * (X_MAX - X_MIN), X_MIN, X_MAX);
        g.style.display = "";
        if (chart.generic) {
          const hit2 = chart.generic(px);
          const c = g.querySelector("circle");
          c.setAttribute("cx", hit2.x);
          c.setAttribute("cy", hit2.y);
          place(hit2.x, hit2.y, hit2.html);
        } else if (id === "curve") {
          const r = Math.round(ot * 2) / 2;
          const dots = chart.dots(r);
          const line = g.querySelector(".cross");
          line.setAttribute("x1", dots[0].x);
          line.setAttribute("x2", dots[0].x);
          g.querySelectorAll("circle").forEach((c, i) => {
            c.setAttribute("cx", dots[i].x);
            c.setAttribute("cy", dots[i].y);
            c.setAttribute("fill", dots[i].color);
          });
          place(dots[0].x, Math.min(...dots.map((d) => d.y)), chart.tip(r));
        } else {
          const b = chart.nearest(ot);
          const p = chart.pos(b);
          const c = g.querySelector("circle");
          c.setAttribute("cx", p.x);
          c.setAttribute("cy", p.y);
          place(p.x, p.y, chart.tipFor(b));
        }
      });
      hit.addEventListener("pointerleave", () => {
        g.style.display = "none";
        tip.style.display = "none";
      });
    });
  }
}

if (!customElements.get("heating-curve-panel")) customElements.define("heating-curve-panel", HeatingCurvePanel);
