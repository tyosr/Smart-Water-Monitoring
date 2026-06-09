#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Serveur Flask - Système de Surveillance du Niveau d'Eau
Version Corrigée et Améliorée - Temps Réel + IA Complète
"""

from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from datetime import datetime, timedelta
import sqlite3
import os
import threading
import json
import statistics
from collections import deque
from typing import Dict, List, Optional, Tuple
import logging

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialisation Flask
app = Flask(__name__)
CORS(app)

# Configuration
DATABASE = 'water_monitoring.db'
MAX_HISTORY_POINTS = 1000
ANOMALY_THRESHOLD = 80      # Seuil pour détection anomalie (en 5 min)
TREND_WINDOW_MINUTES = 5    # Minutes pour calcul tendance
PREDICTION_WINDOW = 60      # Minutes pour prédiction

# Cache en mémoire pour performances
class DataCache:
    def __init__(self):
        self.recent_data = deque(maxlen=MAX_HISTORY_POINTS)
        self.current_value = None
        self.current_state = None
        self.last_update = None
        self.lock = threading.Lock()
        
    def add(self, value: int, timestamp: datetime, state: str):
        with self.lock:
            self.recent_data.append({
                'value': value,
                'timestamp': timestamp,
                'state': state
            })
            self.current_value = value
            self.current_state = state
            self.last_update = timestamp
    
    def get_recent(self, count: int = 50) -> List[Dict]:
        with self.lock:
            return list(self.recent_data)[-count:]
    
    def get_current(self) -> Optional[Dict]:
        with self.lock:
            if self.current_value is None:
                return None
            return {
                'value': self.current_value,
                'state': self.current_state,
                'timestamp': self.last_update.isoformat() if self.last_update else datetime.now().isoformat()
            }
    
    def get_data_since(self, minutes: int) -> List[Dict]:
        """Récupère les données depuis N minutes"""
        with self.lock:
            cutoff = datetime.now() - timedelta(minutes=minutes)
            return [d for d in self.recent_data if d['timestamp'] > cutoff]

cache = DataCache()

# ==================== BASE DE DONNÉES ====================

def init_database():
    """Initialise la base de données SQLite"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Table principale des mesures
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS water_levels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            value INTEGER NOT NULL,
            percentage REAL NOT NULL,
            state TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Table des alertes/anomalies
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            severity TEXT NOT NULL,
            message TEXT NOT NULL,
            value INTEGER,
            percentage REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Index pour performances
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_timestamp ON water_levels(timestamp)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_alert_timestamp ON alerts(timestamp)
    ''')
    
    conn.commit()
    conn.close()
    logger.info("✅ Base de données initialisée")
    # Après initialisation, s'assurer que le schéma est à jour
    try:
        migrate_database()
    except Exception as e:
        logger.error(f"Erreur migration DB: {e}")


def save_measurement(value: int, percentage: float, state: str):
    """Sauvegarde une mesure dans la base"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO water_levels (value, percentage, state)
            VALUES (?, ?, ?)
        ''', (value, percentage, state))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Erreur sauvegarde DB: {e}")


def save_alert(alert_type: str, severity: str, message: str, value: int = None, percentage: float = None):
    """Sauvegarde une alerte"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO alerts (type, severity, message, value, percentage)
            VALUES (?, ?, ?, ?, ?)
        ''', (alert_type, severity, message, value, percentage))
        conn.commit()
        conn.close()
        logger.warning(f"🚨 Alerte enregistrée: {alert_type} - {message}")
        return True
    except Exception as e:
        logger.error(f"Erreur sauvegarde alerte: {e}")
        return False


def get_history(hours: int = 24) -> List[Dict]:
    """Récupère l'historique des mesures"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        since = datetime.now() - timedelta(hours=hours)
        cursor.execute('''
            SELECT value, percentage, state, timestamp
            FROM water_levels
            WHERE timestamp > ?
            ORDER BY timestamp ASC
        ''', (since,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            'value': row[0],
            'percentage': row[1],
            'state': row[2],
            'timestamp': row[3]
        } for row in rows]
        
    except Exception as e:
        logger.error(f"Erreur récupération historique: {e}")
        return []


def get_alert_icon(alert_type: str) -> str:
    """Retourne l'emoji/icône approprié pour un type d'alerte"""
    icons = {
        'niveau_critique': '🚨',
        'montee_rapide': '📈',
        'chute_anormale': '📉',
        'niveau_faible': '⚠️',
        'stagnation': '⏸️',
        'anomalie': '⚠️'
    }
    return icons.get(alert_type, 'ℹ️')


def get_recent_alerts(hours: int = 24) -> List[Dict]:
    """Récupère les alertes récentes"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        since = datetime.now() - timedelta(hours=hours)
        # Essayer la requête normale (avec colonne severity)
        try:
            cursor.execute('''
                SELECT type, severity, message, value, percentage, timestamp
                FROM alerts
                WHERE timestamp > ?
                ORDER BY timestamp DESC
                LIMIT 20
            ''', (since,))
            rows = cursor.fetchall()
            conn.close()

            return [{
                'type': row[0],
                'severity': row[1],
                'message': row[2],
                'value': row[3],
                'percentage': row[4],
                'timestamp': row[5],
                'icon': get_alert_icon(row[0])
            } for row in rows]

        except sqlite3.OperationalError as oe:
            # Si la colonne `severity` n'existe pas (ancienne base), lire sans elle
            logger.warning(f"Schéma alerts incomplet, tentative de lecture alternative: {oe}")
            cursor.execute('''
                SELECT type, message, value, percentage, timestamp
                FROM alerts
                WHERE timestamp > ?
                ORDER BY timestamp DESC
                LIMIT 20
            ''', (since,))
            rows = cursor.fetchall()
            conn.close()

            # Renvoyer les alertes en ajoutant une severity et icon par défaut
            return [{
                'type': row[0],
                'severity': 'info',
                'message': row[1],
                'value': row[2],
                'percentage': row[3],
                'timestamp': row[4],
                'icon': get_alert_icon(row[0])
            } for row in rows]

    except Exception as e:
        logger.error(f"Erreur récupération alertes: {e}")
        return []


def migrate_database():
    """Applique des migrations simples pour corriger le schéma SQLite existant.

    Actuellement: s'assure que la table `alerts` contient les colonnes manquantes (severity, percentage).
    """
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA table_info('alerts')")
        cols = cursor.fetchall()
        col_names = [c[1] for c in cols]

        # Ajouter la colonne severity si elle manque
        if 'severity' not in col_names:
            logger.info("Migration: ajout de la colonne 'severity' à la table alerts")
            try:
                cursor.execute("ALTER TABLE alerts ADD COLUMN severity TEXT DEFAULT 'info'")
                conn.commit()
                logger.info("✓ Migration terminée: colonne 'severity' ajoutée")
            except sqlite3.OperationalError as e:
                logger.warning(f"  (colonne severity peut déjà exister): {e}")
        
        # Ajouter la colonne percentage si elle manque
        if 'percentage' not in col_names:
            logger.info("Migration: ajout de la colonne 'percentage' à la table alerts")
            try:
                cursor.execute("ALTER TABLE alerts ADD COLUMN percentage REAL")
                conn.commit()
                logger.info("✓ Migration terminée: colonne 'percentage' ajoutée")
            except sqlite3.OperationalError as e:
                logger.warning(f"  (colonne percentage peut déjà exister): {e}")

    finally:
        conn.close()


def cleanup_old_data():
    """Nettoie les vieilles données (garde 30 jours)"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cutoff = datetime.now() - timedelta(days=30)
        cursor.execute('DELETE FROM water_levels WHERE timestamp < ?', (cutoff,))
        cursor.execute('DELETE FROM alerts WHERE timestamp < ?', (cutoff,))
        
        conn.commit()
        deleted = cursor.rowcount
        conn.close()
        
        if deleted > 0:
            logger.info(f"🧹 {deleted} vieilles entrées supprimées")
            
    except Exception as e:
        logger.error(f"Erreur nettoyage: {e}")


# ==================== INTELLIGENCE ARTIFICIELLE ====================

class WaterLevelAI:
    """Moteur d'analyse IA pour le niveau d'eau"""
    
    @staticmethod
    def value_to_percentage(value: int) -> float:
        """Convertit la valeur 0-1023 en pourcentage 0-100%"""
        return round((value / 1023) * 100, 1)
    
    @staticmethod
    def get_state(percentage: float) -> str:
        """Détermine l'état selon le pourcentage"""
        if percentage < 5:
            return 'air'
        elif percentage < 30:
            return 'faible'
        elif percentage < 70:
            return 'normal'
        else:
            return 'critique'
    
    @staticmethod
    def get_state_from_value(value: int) -> str:
        """Détermine l'état directement depuis la valeur brute"""
        if value < 50:
            return 'air'
        elif value < 300:
            return 'faible'
        elif value < 650:
            return 'normal'
        else:
            return 'critique'
    
    @staticmethod
    def get_state_color(state: str) -> str:
        """Retourne la couleur associée à l'état"""
        colors = {
            'air': '#94A3B8',      # Gris
            'faible': '#10B981',   # Vert
            'normal': '#F59E0B',   # Jaune/Orange
            'critique': '#EF4444'  # Rouge
        }
        return colors.get(state, '#6B7280')
    
    @staticmethod
    def calculate_trend(data: List[Dict], minutes: int = 5) -> Dict:
        """
        IA 1: Analyse de tendance - CORRIGÉE
        Calcule la vitesse de variation sur les N dernières minutes
        """
        if len(data) < 2:
            return {
                'direction': 'stable',
                'speed': 0.0,
                'change': 0,
                'icon': '➡️',
                'alert': False
            }
        
        cutoff = datetime.now() - timedelta(minutes=minutes)
        recent = [d for d in data if datetime.fromisoformat(d['timestamp']) > cutoff] if isinstance(data[0]['timestamp'], str) else [d for d in data if d['timestamp'] > cutoff]
        
        if len(recent) < 2:
            # Essayer avec plus de données
            recent = data[-10:] if len(data) >= 10 else data
        
        if len(recent) < 2:
            return {
                'direction': 'stable',
                'speed': 0.0,
                'change': 0,
                'icon': '➡️',
                'alert': False
            }
        
        first_value = recent[0]['value']
        last_value = recent[-1]['value']
        change = last_value - first_value
        
        # Calculer le temps écoulé en minutes
        if isinstance(recent[0]['timestamp'], str):
            first_time = datetime.fromisoformat(recent[0]['timestamp'])
            last_time = datetime.fromisoformat(recent[-1]['timestamp'])
        else:
            first_time = recent[0]['timestamp']
            last_time = recent[-1]['timestamp']
        
        time_span = (last_time - first_time).total_seconds() / 60
        
        if time_span > 0:
            speed = round(change / time_span, 2)
        else:
            speed = 0.0
        
        # Déterminer la direction
        if abs(change) < 10:  # Seuil de stabilité réduit
            direction = 'stable'
            icon = '➡️'
        elif change > 0:
            direction = 'augmentation'
            icon = '↗️'
        else:
            direction = 'diminution'
            icon = '↘️'
        
        # Alerte si variation > 50 en 5 minutes
        alert = abs(change) > 50 and time_span <= 5
        
        return {
            'direction': direction,
            'speed': speed,
            'change': change,
            'icon': icon,
            'alert': alert,
            'minutes_analyzed': max(1, int(time_span))
        }
    
    @staticmethod
    def predict_level(current_value: int, data: List[Dict], minutes: int = 60) -> Dict:
        """
        IA 3: Prédiction à court terme
        Estime le niveau futur basé sur la tendance actuelle
        """
        trend = WaterLevelAI.calculate_trend(data, minutes=5)
        
        if abs(trend['speed']) < 0.5:
            return {
                'predicted_value': current_value,
                'predicted_percentage': WaterLevelAI.value_to_percentage(current_value),
                'time_to_critical': None,
                'risk_level': 'stable',
                'message': 'Niveau stable - Aucune prédiction disponible',
                'trend_speed': trend['speed']
            }
        
        # Prédire dans X minutes
        predicted = current_value + (trend['speed'] * minutes)
        predicted = max(0, min(1023, predicted))
        
        predicted_pct = WaterLevelAI.value_to_percentage(predicted)
        
        # Calculer temps avant saturation (1023) ou vide (0)
        if trend['speed'] > 0:
            time_to_full = (1023 - current_value) / trend['speed'] if trend['speed'] > 0 else float('inf')
            time_to_critical = time_to_full
        else:
            time_to_empty = current_value / abs(trend['speed']) if trend['speed'] < 0 else float('inf')
            time_to_critical = time_to_empty
        
        # Déterminer le niveau de risque
        if predicted_pct >= 90:
            risk_level = 'critique'
            message = f'⚠️ Risque de saturation dans {int(time_to_critical)} minutes!'
        elif predicted_pct >= 70:
            risk_level = 'eleve'
            message = f'Niveau estimé dans 1h: {int(predicted_pct)}% - Surveillance recommandée'
        elif predicted_pct <= 10 and current_value > 100:
            risk_level = 'faible'
            message = f'⚠️ Risque de niveau très bas dans {int(time_to_critical)} minutes'
        else:
            risk_level = 'normal'
            message = f'Niveau estimé dans 1h: {int(predicted_pct)}% - Situation normale'
        
        return {
            'predicted_value': int(predicted),
            'predicted_percentage': round(predicted_pct, 1),
            'time_to_critical': int(time_to_critical) if time_to_critical < 1440 else None,
            'risk_level': risk_level,
            'message': message,
            'trend_speed': trend['speed']
        }
    
    @staticmethod
    def detect_anomalies(data: List[Dict], current_value: int) -> List[Dict]:
        """
        IA 4: Détection d'anomalies - CORRIGÉE
        Identifie les variations anormales
        """
        anomalies = []
        
        if len(data) < 3:
            return anomalies
        
        # Analyse sur 5 minutes
        cutoff_5min = datetime.now() - timedelta(minutes=5)
        recent_5min = []
        for d in data:
            ts = datetime.fromisoformat(d['timestamp']) if isinstance(d['timestamp'], str) else d['timestamp']
            if ts > cutoff_5min:
                recent_5min.append(d)
        
        if len(recent_5min) >= 2:
            first = recent_5min[0]['value']
            last = recent_5min[-1]['value']
            change_5min = last - first
            
            # Montée rapide > 80 en 5 min
            if change_5min > ANOMALY_THRESHOLD:
                anomalies.append({
                    'type': 'montee_rapide',
                    'severity': 'critique',
                    'message': f'⚠️ Montée rapide détectée: +{change_5min} unités en 5 minutes!',
                    'change': change_5min,
                    'icon': '📈'
                })
            
            # Chute anormale < -80 en 5 min
            elif change_5min < -ANOMALY_THRESHOLD:
                anomalies.append({
                    'type': 'chute_anormale',
                    'severity': 'critique',
                    'message': f'⚠️ Chute anormale détectée: {change_5min} unités en 5 minutes!',
                    'change': change_5min,
                    'icon': '📉'
                })
        
        # Détection de niveau critique
        current_pct = WaterLevelAI.value_to_percentage(current_value)
        if current_pct >= 80:
            anomalies.append({
                'type': 'niveau_critique',
                'severity': 'critique',
                'message': f'🚨 Niveau critique atteint: {current_pct}% - Intervention nécessaire!',
                'icon': '🔴'
            })
        elif current_pct <= 10 and current_value > 50:
            anomalies.append({
                'type': 'niveau_faible',
                'severity': 'attention',
                'message': f'⚠️ Niveau très faible: {current_pct}% - Vérifier le système',
                'icon': '🔵'
            })
        
        # Détection de stagnation (valeur identique pendant > 10 min)
        if len(data) >= 5:
            cutoff_10min = datetime.now() - timedelta(minutes=10)
            recent_10min = []
            for d in data:
                ts = datetime.fromisoformat(d['timestamp']) if isinstance(d['timestamp'], str) else d['timestamp']
                if ts > cutoff_10min:
                    recent_10min.append(d)
            
            if len(recent_10min) > 3:
                values = [d['value'] for d in recent_10min]
                if len(set(values)) == 1:
                    anomalies.append({
                        'type': 'stagnation',
                        'severity': 'info',
                        'message': f'ℹ️ Valeur inchangée ({values[0]}) depuis 10+ minutes - Vérifiez le capteur',
                        'icon': '⏸️'
                    })
        
        return anomalies
    
    @staticmethod
    def generate_recommendation(current_pct: float, trend: Dict, anomalies: List[Dict], current_value: int) -> Dict:
        """
        Génère une recommandation intelligente basée sur toutes les analyses
        """
        # Priorité aux anomalies critiques
        critical_anomalies = [a for a in anomalies if a['severity'] == 'critique']
        if critical_anomalies:
            anomaly = critical_anomalies[0]
            return {
                'level': 'critique',
                'color': '#EF4444',
                'icon': '🔴',
                'title': 'ALERTE CRITIQUE',
                'message': anomaly['message'],
                'action': 'Intervention immédiate requise'
            }
        
        # Anomalies d'attention
        warning_anomalies = [a for a in anomalies if a['severity'] == 'attention']
        if warning_anomalies:
            return {
                'level': 'attention',
                'color': '#F59E0B',
                'icon': '🟡',
                'title': 'Attention Requise',
                'message': warning_anomalies[0]['message'],
                'action': 'Surveillance renforcée'
            }
        
        # Niveau critique
        if current_pct >= 70:
            return {
                'level': 'critique',
                'color': '#EF4444',
                'icon': '🔴',
                'title': 'Niveau Élevé',
                'message': f'Niveau d\'eau à {current_pct}% - Surveillance accrue',
                'action': 'Vérifier dans 30 minutes'
            }
        
        # Augmentation rapide
        if trend['alert'] and trend['direction'] == 'augmentation':
            return {
                'level': 'attention',
                'color': '#F59E0B',
                'icon': '🟡',
                'title': 'Augmentation Rapide',
                'message': f'Augmentation de {trend["change"]:+d} unités en {trend["minutes_analyzed"]} min',
                'action': 'Surveillance continue'
            }
        
        # Capteur hors eau
        if current_value < 50:
            return {
                'level': 'info',
                'color': '#94A3B8',
                'icon': '⚪',
                'title': 'Capteur Hors Eau',
                'message': 'Le capteur n\'est pas dans l\'eau ou le niveau est très bas',
                'action': 'Vérifier l\'installation'
            }
        
        # Niveau normal
        if current_pct >= 30:
            return {
                'level': 'normal',
                'color': '#10B981',
                'icon': '🟢',
                'title': 'Situation Normale',
                'message': f'Niveau d\'eau stable à {current_pct}%',
                'action': 'Aucune action requise'
            }
        
        # Niveau faible
        return {
            'level': 'faible',
            'color': '#3B82F6',
            'icon': '🔵',
            'title': 'Niveau Faible',
            'message': f'Niveau d\'eau bas ({current_pct}%)',
            'action': 'Surveillance régulière'
        }
    
    @staticmethod
    def get_statistics(data: List[Dict]) -> Dict:
        """Calcule les statistiques sur les données"""
        if not data:
            return {
                'min': 0, 'max': 0, 'avg': 0,
                'min_percentage': 0, 'max_percentage': 0, 'avg_percentage': 0,
                'count': 0
            }
        
        values = [d['value'] for d in data]
        percentages = [d.get('percentage', WaterLevelAI.value_to_percentage(d['value'])) for d in data]
        
        return {
            'min': min(values),
            'max': max(values),
            'avg': round(statistics.mean(values), 1),
            'min_percentage': round(min(percentages), 1),
            'max_percentage': round(max(percentages), 1),
            'avg_percentage': round(statistics.mean(percentages), 1),
            'count': len(values)
        }


# ==================== ROUTES API ====================

@app.route('/')
def dashboard():
    """Page principale du dashboard"""
    return render_template('dashboard.html')


@app.route('/api/data', methods=['POST'])
def receive_data():
    """Reçoit les données de l'Arduino"""
    try:
        data = request.get_json()
        
        if not data or 'value' not in data:
            return jsonify({'error': 'Données invalides'}), 400
        
        value = int(data['value'])
        arduino_state = data.get('state', None)
        
        # Validation
        if not (0 <= value <= 1023):
            return jsonify({'error': 'Valeur hors plage (0-1023)'}), 400
        
        # Calculer le pourcentage et l'état
        percentage = WaterLevelAI.value_to_percentage(value)
        state = arduino_state if arduino_state else WaterLevelAI.get_state_from_value(value)
        
        # Sauvegarder dans la base
        save_measurement(value, percentage, state)
        
        # Mettre à jour le cache
        cache.add(value, datetime.now(), state)
        
        # Vérifier les alertes
        check_and_save_alerts(value, percentage, state)
        
        logger.info(f"💧 Donnée reçue: {value} ({percentage}% - {state})")
        
        return jsonify({
            'success': True,
            'value': value,
            'percentage': percentage,
            'state': state
        })
        
    except Exception as e:
        logger.error(f"Erreur réception données: {e}")
        return jsonify({'error': str(e)}), 500


def check_and_save_alerts(value: int, percentage: float, state: str):
    """Vérifie et sauvegarde les alertes si nécessaire"""
    logger.debug(f"[ALERT CHECK] value={value}, percentage={percentage}%, state={state}")
    
    # Alerte niveau critique
    if percentage >= 80:
        logger.info(f"✅ CREATING CRITICAL ALERT: {percentage}% >= 80%")
        result = save_alert(
            'niveau_critique',
            'critique',
            f'Niveau d\'eau critique atteint: {percentage}%',
            value,
            percentage
        )
        logger.info(f"   Save result: {result}")
    
    # Alerte niveau faible
    elif percentage <= 10 and value > 50:
        logger.info(f"✅ CREATING LOW ALERT: {percentage}% <= 10% AND value={value} > 50")
        result = save_alert(
            'niveau_faible',
            'attention',
            f'Niveau d\'eau très bas: {percentage}%',
            value,
            percentage
        )
        logger.info(f"   Save result: {result}")


@app.route('/api/current', methods=['GET'])
def get_current():
    """Retourne la valeur actuelle"""
    current = cache.get_current()
    
    if current is None:
        # Essayer de récupérer depuis la DB
        history = get_history(hours=1)
        if history:
            last = history[-1]
            current = {
                'value': last['value'],
                'state': last['state'],
                'timestamp': last['timestamp']
            }
            cache.current_value = last['value']
            cache.current_state = last['state']
    
    if current is None:
        return jsonify({'error': 'Aucune donnée disponible'}), 404
    
    percentage = WaterLevelAI.value_to_percentage(current['value'])
    
    return jsonify({
        'value': current['value'],
        'percentage': percentage,
        'state': current['state'],
        'color': WaterLevelAI.get_state_color(current['state']),
        'timestamp': current['timestamp']
    })


@app.route('/api/history/<period>', methods=['GET'])
def get_history_api(period):
    """
    Retourne l'historique selon la période
    period: '1h', '24h', '7d'
    """
    hours_map = {
        '1h': 1,
        '24h': 24,
        '7d': 24 * 7
    }
    
    hours = hours_map.get(period, 24)
    data = get_history(hours=hours)
    
    # Calculer statistiques
    stats = WaterLevelAI.get_statistics(data)
    
    return jsonify({
        'period': period,
        'data': data,
        'statistics': stats
    })


@app.route('/api/analysis', methods=['GET'])
def get_analysis():
    """Retourne toutes les analyses IA"""
    # Récupérer les données récentes (dernières 2h pour analyse complète)
    data = get_history(hours=2)
    
    if not data:
        return jsonify({'error': 'Pas assez de données pour l\'analyse'}), 404
    
    current_value = data[-1]['value'] if data else 0
    current_percentage = WaterLevelAI.value_to_percentage(current_value)
    
    # IA 1: Tendance (CORRIGÉ)
    trend = WaterLevelAI.calculate_trend(data, minutes=TREND_WINDOW_MINUTES)
    
    # IA 2: Classification
    classification = {
        'percentage': current_percentage,
        'state': WaterLevelAI.get_state_from_value(current_value),
        'color': WaterLevelAI.get_state_color(WaterLevelAI.get_state_from_value(current_value))
    }
    
    # IA 3: Prédiction
    prediction = WaterLevelAI.predict_level(current_value, data, minutes=PREDICTION_WINDOW)
    
    # IA 4: Anomalies (CORRIGÉ)
    anomalies = WaterLevelAI.detect_anomalies(data, current_value)
    
    # Recommandation
    recommendation = WaterLevelAI.generate_recommendation(
        current_percentage, trend, anomalies, current_value
    )
    
    # Statistiques globales
    stats = WaterLevelAI.get_statistics(data)
    
    return jsonify({
        'timestamp': datetime.now().isoformat(),
        'current': {
            'value': current_value,
            'percentage': current_percentage
        },
        'trend': trend,
        'classification': classification,
        'prediction': prediction,
        'anomalies': anomalies,
        'recommendation': recommendation,
        'statistics': stats
    })


@app.route('/api/recent', methods=['GET'])
def get_recent():
    """Retourne les 50 dernières valeurs pour le graphique temps réel"""
    data = cache.get_recent(50)
    
    if not data:
        # Fallback sur la DB
        data = get_history(hours=1)
        data = data[-50:] if len(data) > 50 else data
    
    # Convertir les timestamps en ISO format si nécessaire
    formatted_data = []
    for d in data:
        ts = d['timestamp']
        if isinstance(ts, datetime):
            ts = ts.isoformat()
        formatted_data.append({
            'value': d['value'],
            'state': d.get('state', 'normal'),
            'timestamp': ts
        })
    
    return jsonify({
        'count': len(formatted_data),
        'data': formatted_data
    })


@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """Retourne les alertes récentes"""
    alerts = get_recent_alerts(hours=24)
    return jsonify({
        'alerts': alerts,
        'count': len(alerts)
    })


@app.route('/api/health', methods=['GET'])
def health_check():
    """Vérification de santé du serveur"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'database': os.path.exists(DATABASE),
        'cache_size': len(cache.recent_data),
        'current_value': cache.current_value
    })


# ==================== DÉMARRAGE ====================

if __name__ == '__main__':
    logger.info("=" * 50)
    logger.info("🌊 Serveur Flask - AquaMonitor (Version Corrigée)")
    logger.info("=" * 50)
    
    # Initialiser la base de données
    init_database()
    
    # Nettoyer les vieilles données au démarrage
    cleanup_old_data()
    
    # Démarrer le serveur
    logger.info("🚀 Démarrage du serveur sur http://127.0.0.1:5000")
    logger.info("📊 Dashboard: http://127.0.0.1:5000")
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=False,
        threaded=True
    )
