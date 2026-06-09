#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Arduino Reader - Système de Surveillance du Niveau d'Eau
Version Corrigée et Optimisée - Temps Réel
"""

import serial
import serial.tools.list_ports
import re
import time
import requests
import sys
import logging
from datetime import datetime
from threading import Thread, Event
import json

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('arduino_reader.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Configuration
FLASK_SERVER_URL = "http://127.0.0.1:5000/api/data"
BAUD_RATE = 9600
RECONNECT_DELAY = 3  # secondes
READ_TIMEOUT = 2
SEND_INTERVAL = 1.0  # Envoyer toutes les 1 seconde (plus réactif)

class ArduinoReader:
    def __init__(self):
        self.serial_port = None
        self.port_name = None
        self.is_running = False
        self.last_value = None
        self.last_state = None
        self.last_send_time = 0
        self.connection_attempts = 0
        self.stop_event = Event()
        
    def find_arduino_port(self):
        """Détecte automatiquement le port Arduino"""
        logger.info("Recherche du port Arduino...")
        
        ports = list(serial.tools.list_ports.comports())
        
        if not ports:
            logger.warning("Aucun port série trouvé")
            return None
            
        logger.info("Ports disponibles:")
        for port in ports:
            logger.info(f"  - {port.device}: {port.description}")
        
        # Cherche un port Arduino
        arduino_keywords = ['Arduino', 'CH340', 'CP2102', 'USB-SERIAL', 'ttyACM', 'ttyUSB', 'Serial']
        
        for port in ports:
            desc_upper = port.description.upper()
            device_upper = port.device.upper()
            
            if any(keyword.upper() in desc_upper or keyword.upper() in device_upper 
                   for keyword in arduino_keywords):
                logger.info(f"✅ Arduino détecté sur: {port.device}")
                return port.device
        
        # Si pas trouvé, prend le premier port disponible
        if ports:
            logger.info(f"⚠️ Arduino probable sur: {ports[0].device}")
            return ports[0].device
            
        return None
    
    def connect(self):
        """Établit la connexion série avec l'Arduino"""
        try:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
                
            self.port_name = self.find_arduino_port()
            
            if not self.port_name:
                logger.error("❌ Aucun port Arduino trouvé")
                return False
            
            logger.info(f"🔌 Connexion à {self.port_name} à {BAUD_RATE} bauds...")
            
            self.serial_port = serial.Serial(
                port=self.port_name,
                baudrate=BAUD_RATE,
                timeout=READ_TIMEOUT,
                write_timeout=READ_TIMEOUT,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            
            # Attendre que l'Arduino redémarre
            time.sleep(2.5)
            
            # Vider les buffers
            self.serial_port.reset_input_buffer()
            self.serial_port.reset_output_buffer()
            
            logger.info(f"✅ Connecté à Arduino sur {self.port_name}")
            self.connection_attempts = 0
            return True
            
        except serial.SerialException as e:
            logger.error(f"❌ Erreur de connexion série: {e}")
            self.connection_attempts += 1
            return False
        except Exception as e:
            logger.error(f"❌ Erreur inattendue: {e}")
            return False
    
    def parse_water_level(self, line):
        """
        Extrait la valeur numérique du format 'Water level: XXX [STATE]'
        Retourne: (value, state) ou (None, None) si invalide
        """
        try:
            line = line.strip()
            if not line:
                return None, None
            
            # Nouveau format: "Water level: 536 [MEDIUM]"
            match = re.search(r'Water level:\s*(\d+)\s*\[?(\w+)?\]?', line, re.IGNORECASE)
            
            if match:
                value = int(match.group(1))
                state = match.group(2) if match.group(2) else None
                
                # Validation: valeur entre 0 et 1023
                if 0 <= value <= 1023:
                    return value, state
                else:
                    logger.warning(f"⚠️ Valeur hors plage: {value}")
                    return None, None
            
            # Format ancien: "Water level: 536"
            match = re.search(r'Water level:\s*(\d+)', line, re.IGNORECASE)
            if match:
                value = int(match.group(1))
                if 0 <= value <= 1023:
                    return value, None
            
            # Format minimal: juste un nombre
            match = re.search(r'^\s*(\d+)\s*$', line)
            if match:
                value = int(match.group(1))
                if 0 <= value <= 1023:
                    return value, None
                    
            return None, None
            
        except Exception as e:
            logger.debug(f"Erreur parsing: {e}")
            return None, None
    
    def send_to_server(self, value, state=None):
        """Envoie la valeur au serveur Flask"""
        try:
            payload = {
                'value': value,
                'state': state,
                'timestamp': datetime.now().isoformat()
            }
            
            response = requests.post(
                FLASK_SERVER_URL,
                json=payload,
                timeout=3
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"💧 Envoyé: {value} ({data.get('percentage', '?')}% - {data.get('state', '?')})")
                return True
            else:
                logger.warning(f"⚠️ Serveur retourne {response.status_code}")
                return False
                
        except requests.exceptions.ConnectionError:
            logger.error("❌ Impossible de connecter au serveur Flask")
            return False
        except requests.exceptions.Timeout:
            logger.warning("⚠️ Timeout lors de l'envoi")
            return False
        except Exception as e:
            logger.error(f"❌ Erreur envoi: {e}")
            return False
    
    def read_loop(self):
        """Boucle principale de lecture - TEMPS RÉEL"""
        logger.info("🚀 Démarrage de la boucle de lecture temps réel...")
        
        while self.is_running and not self.stop_event.is_set():
            try:
                # Vérifier la connexion
                if not self.serial_port or not self.serial_port.is_open:
                    logger.info("🔄 Tentative de reconnexion...")
                    if not self.connect():
                        time.sleep(RECONNECT_DELAY)
                        continue
                
                # Lire une ligne depuis l'Arduino
                if self.serial_port.in_waiting > 0:
                    try:
                        line = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                    except UnicodeDecodeError:
                        continue
                    
                    if line and not line.startswith('===') and not line.startswith('RAW:'):
                        # Parser la valeur
                        value, state = self.parse_water_level(line)
                        
                        if value is not None:
                            self.last_value = value
                            self.last_state = state
                            
                            # Envoyer immédiatement pour temps réel
                            current_time = time.time()
                            if current_time - self.last_send_time >= SEND_INTERVAL:
                                self.send_to_server(value, state)
                                self.last_send_time = current_time
                        
                else:
                    # Pas de données - petite pause
                    time.sleep(0.05)
                    
            except serial.SerialException as e:
                logger.error(f"❌ Erreur série: {e}")
                self.serial_port = None
                time.sleep(RECONNECT_DELAY)
                
            except Exception as e:
                logger.error(f"❌ Erreur dans la boucle: {e}")
                time.sleep(1)
    
    def start(self):
        """Démarre le lecteur Arduino"""
        logger.info("=" * 50)
        logger.info("🌊 AquaMonitor - Arduino Reader (Temps Réel)")
        logger.info("=" * 50)
        
        self.is_running = True
        self.stop_event.clear()
        
        # Connexion initiale
        if not self.connect():
            logger.warning("⚠️ Connexion initiale échouée, tentative en arrière-plan...")
        
        # Démarrer la boucle de lecture dans un thread
        self.read_thread = Thread(target=self.read_loop, daemon=True)
        self.read_thread.start()
        
        logger.info("✅ Arduino Reader démarré en mode TEMPS RÉEL")
        logger.info("💡 Appuyez sur Ctrl+C pour arrêter")
        
        try:
            while self.is_running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        """Arrête proprement le lecteur"""
        logger.info("\n🛑 Arrêt du Arduino Reader...")
        self.is_running = False
        self.stop_event.set()
        
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            logger.info("✅ Port série fermé")
        
        logger.info("👋 Au revoir!")


def test_mode():
    """Mode test sans Arduino - génère des données simulées réalistes"""
    logger.info("🧪 MODE TEST - Génération de données simulées")
    
    import math
    import random
    
    base_value = 400
    trend = 0
    
    while True:
        try:
            # Simuler une variation réaliste avec tendance
            trend += random.uniform(-5, 5)
            trend = max(-20, min(20, trend))  # Limiter la tendance
            
            base_value += trend * 0.1
            base_value = max(50, min(950, base_value))  # Garder dans les limites
            
            # Ajouter du bruit réaliste
            noise = random.randint(-15, 15)
            value = int(base_value + noise)
            value = max(0, min(1023, value))
            
            # Déterminer l'état
            if value < 50:
                state = "AIR"
            elif value < 300:
                state = "LOW"
            elif value < 650:
                state = "MEDIUM"
            else:
                state = "HIGH"
            
            payload = {
                'value': value,
                'state': state,
                'timestamp': datetime.now().isoformat()
            }
            
            try:
                response = requests.post(FLASK_SERVER_URL, json=payload, timeout=3)
                if response.status_code == 200:
                    logger.info(f"💧 [TEST] Niveau: {value} [{state}]")
                else:
                    logger.warning(f"⚠️ Serveur retourne {response.status_code}")
            except Exception as e:
                logger.error(f"❌ Erreur envoi: {e}")
            
            time.sleep(1)  # 1 seconde comme l'Arduino
            
        except KeyboardInterrupt:
            logger.info("\n🛑 Arrêt du mode test")
            break


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Arduino Reader pour surveillance eau')
    parser.add_argument('--test', action='store_true', 
                       help='Mode test sans Arduino (données simulées)')
    parser.add_argument('--port', type=str, 
                       help='Port série spécifique (ex: COM3, /dev/ttyUSB0)')
    
    args = parser.parse_args()
    
    if args.test:
        test_mode()
    else:
        reader = ArduinoReader()
        if args.port:
            reader.port_name = args.port
        reader.start()
