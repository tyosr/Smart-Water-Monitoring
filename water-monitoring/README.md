# 💧 Système de Surveillance du Niveau d'Eau

Système de monitoring de niveau d'eaux avec Arduino, Python Flask et Dashboard web moderne.

---

## 📋 Table des matières

- [Vue d'ensemble](#vue-densemble)
- [Architecture](#architecture)
- [Installation](#installation)
- [Utilisation](#utilisation)
- [API REST](#api-rest)
- [Fonctionnalités IA](#fonctionnalités-ia)
- [Dépannage](#dépannage)

---

## 🎯 Vue d'ensemble

Ce système permet de :
- 📊 **Surveiller** en temps réel le niveau d'eau 
- 📈 **Visualiser** l'évolution sur des graphiques interactifs
- 🤖 **Analyser** les tendances avec l'intelligence artificielle
- 🚨 **Détecter** les anomalies et recevoir des alertes
- 🔮 **Prédire** le niveau futur pour anticiper les risques

### Capture d'écran

Le dashboard présente :
- Jauge circulaire animée du niveau actuel
- Graphique temps réel (mise à jour toutes les 2s)
- 4 analyses IA (tendance, classification, prédiction, anomalies)
- Recommandations intelligentes
- Historique détaillé (1h, 24h, 7j)

---

## 🏗️ Architecture

```
┌─────────────┐     USB/Série     ┌─────────────────┐     HTTP      ┌─────────────┐
│   Arduino   │ ═══════════════► │  arduino_reader │ ═══════════► │  Flask API  │
│  (Capteur)  │   "Water: 536"   │    (Python)     │   JSON       │   (SQLite)  │
└─────────────┘                  └─────────────────┘              └──────┬──────┘
                                                                         │
                                    ┌────────────────────────────────────┘
                                    │ HTTP
                                    ▼
                            ┌───────────────┐
                            │   Dashboard   │
                            │  (HTML/CSS/JS)│
                            │  Tailwind +   │
                            │   Chart.js    │
                            └───────────────┘
```

### Fichiers du projet

```
water-monitoring/
├── app.py                 # Serveur Flask + API REST + IA
├── arduino_reader.py      # Lecture port série + envoi API
├── requirements.txt       # Dépendances Python
├── README.md             # Ce fichier
├── water_monitoring.db   # Base SQLite (créée auto)
├── arduino_reader.log    # Logs (créé auto)
├── templates/
│   └── dashboard.html    # Interface web complète
└── static/
    ├── css/              # (optionnel)
    └── js/               # (optionnel)
```

---

## 🚀 Installation

### Prérequis

- Python 3.8 ou supérieur
- Arduino UNO avec capteur de niveau d'eau
- Port USB disponible

### Étape 1: acceder au dossier de projet

```bash
cd water-monitoring
```

### Étape 2: Créer un environnement virtuel (recommandé)

```bash
# Windows
python -m venv venv
venv\Scripts\activate


### Étape 3: Installer les dépendances

```bash
pip install -r requirements.txt
```

### Étape 4: Vérifier le port Arduino

**Windows:**
```bash
python -c "import serial.tools.list_ports; [print(p) for p in serial.tools.list_ports.comports()]"
```

Le port sera quelque chose comme `COM3`, `COM4`, etc.



---

## ▶️ Utilisation

### Mode 1: Avec Arduino connecté

#### Terminal 1 - Démarrer le serveur Flask :

```bash
python app.py
```

Le serveur démarre sur `http://0.0.0.0:5000`

#### Terminal 2 - Démarrer le lecteur Arduino :

```bash
# Détection automatique du port
python arduino_reader.py

# Ou spécifier un port
python arduino_reader.py --port COM3
```

#### Accéder au dashboard :

Ouvrez votre navigateur à l'adresse :
```
http://127.0.0.1:5000
```

---

### Mode 2: Test sans Arduino (simulation)

Pour tester l'interface sans matériel Arduino :

```bash
# Terminal 1
python app.py

# Terminal 2 - Mode test
cd water-monitoring
python arduino_reader.py --test
```

Ce mode génère des données simulées avec une courbe sinusoïdale.

---

## 🔌 API REST

### Endpoints disponibles

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/` | Dashboard web |
| POST | `/api/data` | Recevoir données Arduino |
| GET | `/api/current` | Valeur actuelle |
| GET | `/api/recent` | 50 dernières valeurs |
| GET | `/api/history/1h` | Historique 1 heure |
| GET | `/api/history/24h` | Historique 24 heures |
| GET | `/api/history/7d` | Historique 7 jours |
| GET | `/api/analysis` | Analyses IA complètes |
| GET | `/api/alerts` | Alertes récentes |
| GET | `/api/health` | Vérification santé |

### Exemple d'envoi de données

```bash
curl -X POST http://127.0.0.1:5000/api/data \
  -H "Content-Type: application/json" \
  -d '{"value": 536}'
```

### Réponse d'analyse IA

```json
{
  "timestamp": "2024-01-15T10:30:00",
  "current": {
    "value": 536,
    "percentage": 52.4
  },
  "trend": {
    "direction": "augmentation",
    "speed": 2.5,
    "change": 25,
    "alert": false
  },
  "classification": {
    "percentage": 52.4,
    "state": "normal",
    "color": "#F59E0B"
  },
  "prediction": {
    "predicted_value": 686,
    "predicted_percentage": 67.0,
    "risk_level": "normal",
    "message": "Niveau estimé dans 1h: 67%"
  },
  "anomalies": [],
  "recommendation": {
    "level": "normal",
    "title": "Situation stable",
    "message": "Niveau d'eau dans la plage normale",
    "action": "Aucune action requise"
  }
}
```

---

## 🤖 Fonctionnalités IA

### IA 1 - Analyse de Tendance
- Calcule la vitesse de variation sur les 10 dernières minutes
- Détecte : ↗️ Augmentation | ➡️ Stable | ↘️ Diminution
- Alerte si variation > 50 unités en 10 minutes

### IA 2 - Classification Intelligente
- Convertit 0-1023 → 0-100%
- États : 🟢 < 30% (Faible) | 🟡 30-70% (Normal) | 🔴 > 70% (Critique)

### IA 3 - Prédiction à Court Terme
- Formule : `niveau_futur = niveau_actuel + (vitesse × temps)`
- Prédiction à 1 heure
- Estimation du temps avant saturation

### IA 4 - Détection d'Anomalies
- Montée rapide > 100 en 5 min
- Chute anormale < -100 en 5 min
- Détection de stagnation capteur

### Recommandations Intelligentes
- 🟢 Situation stable → Aucune action
- 🟡 Surveillance → Vérifier dans 2h
- 🔴 Alerte → Intervention nécessaire

---

## 🔧 Configuration Arduino

### Code Arduino attendu

```cpp
const int waterSensorPin = A0;
const int ledGreen = 2;
const int ledYellow = 3;
const int ledRed = 4;

void setup() {
  Serial.begin(9600);
  pinMode(ledGreen, OUTPUT);
  pinMode(ledYellow, OUTPUT);
  pinMode(ledRed, OUTPUT);
}

void loop() {
  int value = analogRead(waterSensorPin);
  
  Serial.print("Water level: ");
  Serial.println(value);
  
  // Contrôle LEDs
  if (value < 300) {
    digitalWrite(ledGreen, HIGH);
    digitalWrite(ledYellow, LOW);
    digitalWrite(ledRed, LOW);
  } else if (value < 700) {
    digitalWrite(ledGreen, LOW);
    digitalWrite(ledYellow, HIGH);
    digitalWrite(ledRed, LOW);
  } else {
    digitalWrite(ledGreen, LOW);
    digitalWrite(ledYellow, LOW);
    digitalWrite(ledRed, HIGH);
  }
  
  delay(1000);
}
```

---

## 🐛 Dépannage

### Problème: "Aucun port Arduino trouvé"

**Solutions :**
1. Vérifier la connexion USB
2. Installer les drivers CH340/CP2102
3. Spécifier le port manuellement :
   ```bash
   python arduino_reader.py --port COM3
   ```

### Problème: "Impossible de connecter au serveur Flask"

**Solutions :**
1. Vérifier que Flask est démarré : `python app.py`
2. Vérifier le pare-feu (port 5000)
3. Tester avec : `curl http://127.0.0.1:5000/api/health`

### Problème: Erreur de permission port série (Linux)

```bash
# Ajouter l'utilisateur au groupe dialout
sudo usermod -a -G dialout $USER
# Redémarrer la session
```

### Problème: Données incorrectes

Vérifier le format envoyé par Arduino :
- ✅ Correct : `Water level: 536`
- ✅ Accepté : `536` (nombre seul)
- ❌ Incorrect : `Level=536` (format non supporté)

---

## 📊 Spécifications Techniques

| Paramètre | Valeur |
|-----------|--------|
| Fréquence mise à jour | Toutes les 2 secondes |
| Plage capteur | 0 - 1023 (10 bits Arduino) |
| Base de données | SQLite |
| Rétention données | 30 jours |
| Points temps réel | 50 derniers |
| API | REST/JSON |

---

**Développé avec 💙 pour la gestion intelligente de l'eau**
