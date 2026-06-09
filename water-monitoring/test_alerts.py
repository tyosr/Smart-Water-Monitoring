
"""
Script de test pour générer des données et des alertes
"""

import requests
import time
import json

API_URL = "http://127.0.0.1:5000"

def test_send_data(value):
    """Envoie une donnée à l'API"""
    try:
        response = requests.post(
            f"{API_URL}/api/data",
            json={'value': value},
            headers={'Content-Type': 'application/json'}
        )
        print(f"✓ Data sent: {value} - Status: {response.status_code}")
        print(f"  Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"✗ Error sending data: {e}")
        return False

def test_get_alerts():
    """Récupère et affiche les alertes"""
    try:
        response = requests.get(f"{API_URL}/api/alerts")
        if response.status_code == 200:
            data = response.json()
            print(f"\n📋 Alertes ({data['count']}):")
            if data['alerts']:
                for alert in data['alerts']:
                    print(f"  {alert.get('icon', 'ℹ️')} [{alert['severity'].upper()}] {alert['message']}")
            else:
                print("  ❌ Aucune alerte")
            return data['alerts']
        else:
            print(f"✗ Error getting alerts: {response.status_code}")
            return []
    except Exception as e:
        print(f"✗ Error: {e}")
        return []

def test_get_current():
    """Récupère la valeur actuelle"""
    try:
        response = requests.get(f"{API_URL}/api/current")
        if response.status_code == 200:
            data = response.json()
            print(f"\n📊 Current: {data['value']} ({data['percentage']}% - {data['state']})")
            return data
        elif response.status_code == 404:
            print("\n❌ Aucune donnée disponible")
            return None
        else:
            print(f"✗ Error: {response.status_code}")
            return None
    except Exception as e:
        print(f"✗ Error: {e}")
        return None

def test_get_recent():
    """Récupère les données récentes"""
    try:
        response = requests.get(f"{API_URL}/api/recent")
        if response.status_code == 200:
            data = response.json()
            print(f"\n📈 Recent data points: {data['count']}")
            return data
        else:
            print(f"✗ Error: {response.status_code}")
            return None
    except Exception as e:
        print(f"✗ Error: {e}")
        return None

if __name__ == '__main__':
    print("=" * 60)
    print("🧪 TEST SYSTÈME DE SURVEILLANCE D'EAU")
    print("=" * 60)
    
    # Test 1: Envoyer une valeur normale (500 = 48.9%)
    print("\n[TEST 1] Envoyer valeur normale (500)")
    test_send_data(500)
    time.sleep(0.5)
    test_get_current()
    
    # Test 2: Envoyer une valeur critique (850 = 83%)
    print("\n[TEST 2] Envoyer valeur CRITIQUE (850)")
    test_send_data(850)
    time.sleep(0.5)
    test_get_current()
    test_get_alerts()
    
    # Test 3: Envoyer une valeur très basse (100 = 9.8%)
    print("\n[TEST 3] Envoyer valeur TRÈS BASSE (100)")
    test_send_data(100)
    time.sleep(0.5)
    test_get_current()
    test_get_alerts()
    
    # Test 4: Afficher toutes les données récentes
    print("\n[TEST 4] Récupérer toutes les données")
    test_get_recent()
    test_get_alerts()
    
    print("\n" + "=" * 60)
    print("✅ Tests terminés")
    print("=" * 60)
