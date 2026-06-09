/*
 * AquaMonitor - Système de Surveillance du Niveau d'Eau
 * Code Arduino Corrigé et Optimisé
 * 
 * Matériel:
 * - Arduino UNO
 * - Capteur de niveau d'eau (analogique)
 * - 3 LEDs (Vert, Jaune, Rouge)
 * - Buzzer (optionnel)
 * 
 * Connexions:
 * - Capteur: Pin A0
 * - LED Verte: Pin 2
 * - LED Jaune: Pin 3
 * - LED Rouge: Pin 4
 * - Buzzer: Pin 5
 */

// ==================== CONFIGURATION DES PINS ====================
const int SENSOR_PIN = A0;
const int GREEN_LED  = 2;
const int YELLOW_LED = 3;
const int RED_LED    = 4;
const int BUZZER     = 5;

// ==================== PARAMÈTRES DE FILTRAGE ====================
const int NB_SAMPLES = 20;        // Nombre de lectures pour la moyenne (augmenté pour plus de stabilité)
const int DELAY_BETWEEN_SAMPLES = 10; // Délai entre chaque lecture (ms)
const int LOOP_DELAY = 1000;      // Délai entre chaque cycle complet (ms)

// ==================== SEUILS CALIBRÉS ====================
// Ces valeurs sont basées sur des tests réels avec le capteur
const int AIR_VALUE_MIN = 0;      // Valeur minimum (air sec)
const int AIR_VALUE_MAX = 50;     // Valeur maximum considérée comme "hors eau"

// Seuils pour les LEDs (ajustés pour plus de fiabilité)
const int THRESHOLD_LOW_MIN = 0;      // Début niveau bas
const int THRESHOLD_LOW_MAX = 300;    // Fin niveau bas (LED verte)

const int THRESHOLD_MEDIUM_MIN = 301; // Début niveau moyen
const int THRESHOLD_MEDIUM_MAX = 650; // Fin niveau moyen (LED jaune)

const int THRESHOLD_HIGH_MIN = 651;   // Début niveau élevé (LED rouge)
const int THRESHOLD_HIGH_MAX = 1023;  // Maximum Arduino

// ==================== VARIABLES GLOBALES ====================
int currentLevel = 0;           // Niveau actuel filtré
int previousLevel = -1;         // Niveau précédent (pour détecter changements)
String currentState = "AIR";    // État actuel: AIR, LOW, MEDIUM, HIGH
unsigned long lastSendTime = 0; // Dernier envoi série
const int SEND_INTERVAL = 1000; // Intervalle d'envoi (ms)

// ==================== SETUP ====================
void setup() {
  // Configuration des pins
  pinMode(GREEN_LED, OUTPUT);
  pinMode(YELLOW_LED, OUTPUT);
  pinMode(RED_LED, OUTPUT);
  pinMode(BUZZER, OUTPUT);
  
  // Éteindre toutes les sorties au démarrage
  turnOffAllOutputs();
  
  // Démarrer la communication série
  Serial.begin(9600);
  
  // Attendre que la connexion série soit établie
  while (!Serial) {
    ; // Attendre (pour Leonardo/Micro)
  }
  
  delay(500); // Stabilité au démarrage
  
  // Message de démarrage
  Serial.println("================================");
  Serial.println("AquaMonitor - Arduino Started");
  Serial.println("================================");
  Serial.println("Format: Water level: XXX");
  Serial.println("States: AIR(0), LOW(1-300), MEDIUM(301-650), HIGH(651+)");
  Serial.println("================================");
}

// ==================== LOOP PRINCIPAL ====================
void loop() {
  // 1. LIRE ET FILTRER LE CAPTEUR
  int rawValue = readSensorFiltered();
  
  // 2. CALIBRER LA VALEUR (détection hors eau)
  currentLevel = calibrateValue(rawValue);
  
  // 3. DÉTERMINER L'ÉTAT
  String newState = determineState(currentLevel);
  
  // 4. METTRE À JOUR LES LEDS (uniquement si changement d'état ou toutes les 5 secondes)
  static unsigned long lastLedUpdate = 0;
  if (newState != currentState || millis() - lastLedUpdate > 5000) {
    currentState = newState;
    updateLEDs(currentState);
    lastLedUpdate = millis();
  }
  
  // 5. ENVOYER LES DONNÉES EN SÉRIE (intervalle régulier)
  if (millis() - lastSendTime >= SEND_INTERVAL) {
    sendSerialData(currentLevel, currentState);
    lastSendTime = millis();
  }
  
  // 6. DÉBUG (optionnel - commenter en production)
  // debugInfo(rawValue, currentLevel, currentState);
  
  // Délai pour stabilité
  delay(LOOP_DELAY);
}

// ==================== FONCTIONS ====================

/*
 * Lit le capteur avec filtrage par moyenne glissante
 * Retourne la valeur moyenne
 */
int readSensorFiltered() {
  long sum = 0;
  int minVal = 1023;
  int maxVal = 0;
  
  // Lire plusieurs échantillons
  for (int i = 0; i < NB_SAMPLES; i++) {
    int reading = analogRead(SENSOR_PIN);
    sum += reading;
    
    // Tracker min/max pour détection d'erreur
    if (reading < minVal) minVal = reading;
    if (reading > maxVal) maxVal = reading;
    
    delay(DELAY_BETWEEN_SAMPLES);
  }
  
  // Vérifier si les lectures sont stables (écart < 100)
  if (maxVal - minVal > 200) {
    // Lectures instables - utiliser la médiane au lieu de la moyenne
    return getMedianValue();
  }
  
  return (int)(sum / NB_SAMPLES);
}

/*
 * Obtient la valeur médiane (plus robuste aux pics)
 */
int getMedianValue() {
  int readings[10];
  
  for (int i = 0; i < 10; i++) {
    readings[i] = analogRead(SENSOR_PIN);
    delay(10);
  }
  
  // Trier le tableau (bubble sort simple)
  for (int i = 0; i < 9; i++) {
    for (int j = 0; j < 9 - i; j++) {
      if (readings[j] > readings[j + 1]) {
        int temp = readings[j];
        readings[j] = readings[j + 1];
        readings[j + 1] = temp;
      }
    }
  }
  
  // Retourner la médiane (moyenne des 2 valeurs centrales)
  return (readings[4] + readings[5]) / 2;
}

/*
 * Calibre la valeur brute du capteur
 * Retourne 0 si le capteur est hors de l'eau
 */
int calibrateValue(int rawValue) {
  // Si la valeur est très basse, considérer comme "hors eau"
  if (rawValue <= AIR_VALUE_MAX) {
    return 0;
  }
  
  // Sinon, retourner la valeur brute
  return rawValue;
}

/*
 * Détermine l'état actuel basé sur le niveau
 */
String determineState(int level) {
  if (level <= AIR_VALUE_MAX) {
    return "AIR";
  } else if (level >= THRESHOLD_LOW_MIN && level <= THRESHOLD_LOW_MAX) {
    return "LOW";
  } else if (level >= THRESHOLD_MEDIUM_MIN && level <= THRESHOLD_MEDIUM_MAX) {
    return "MEDIUM";
  } else {
    return "HIGH";
  }
}

/*
 * Met à jour les LEDs selon l'état
 */
void updateLEDs(String state) {
  // Éteindre toutes les LEDs d'abord
  turnOffAllOutputs();
  
  // Allumer la LED correspondante
  if (state == "LOW") {
    digitalWrite(GREEN_LED, HIGH);
  } else if (state == "MEDIUM") {
    digitalWrite(YELLOW_LED, HIGH);
  } else if (state == "HIGH") {
    digitalWrite(RED_LED, HIGH);
    digitalWrite(BUZZER, HIGH); // Buzzer pour alerte haute
    delay(200); // Bip court
    digitalWrite(BUZZER, LOW);
  }
  // Si AIR: tout reste éteint
}

/*
 * Éteint toutes les sorties
 */
void turnOffAllOutputs() {
  digitalWrite(GREEN_LED, LOW);
  digitalWrite(YELLOW_LED, LOW);
  digitalWrite(RED_LED, LOW);
  digitalWrite(BUZZER, LOW);
}

/*
 * Envoie les données en format série standardisé
 */
void sendSerialData(int level, String state) {
  // Format: "Water level: XXX [STATE]"
  Serial.print("Water level: ");
  Serial.print(level);
  Serial.print(" [");
  Serial.print(state);
  Serial.println("]");
}

/*
 * Affiche des informations de débogage
 */
void debugInfo(int raw, int calibrated, String state) {
  Serial.print("RAW: ");
  Serial.print(raw);
  Serial.print(" | CAL: ");
  Serial.print(calibrated);
  Serial.print(" | STATE: ");
  Serial.println(state);
}
