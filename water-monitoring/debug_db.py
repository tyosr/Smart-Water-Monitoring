#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de debug pour vérifier la base de données
"""

import sqlite3
from datetime import datetime, timedelta

DATABASE = 'water_monitoring.db'

def debug_database():
    """Inspecte la base de données"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    print("=" * 70)
    print("DEBUG BASE DE DONNÉES")
    print("=" * 70)
    
    # 1. Vérifier le schéma de la table alerts
    print("\n📋 [SCHÉMA] Table alerts:")
    cursor.execute("PRAGMA table_info('alerts')")
    cols = cursor.fetchall()
    for col in cols:
        print(f"  - {col[1]}: {col[2]}")
    
    # 2. Compter les alertes
    print("\n📊 [COUNT] Nombre d'alertes:")
    cursor.execute("SELECT COUNT(*) FROM alerts")
    count = cursor.fetchone()[0]
    print(f"  Total: {count}")
    
    # 3. Afficher les dernières alertes (dernières 24h)
    print("\n📝 [ALERTES] Dernières 24h:")
    since = datetime.now() - timedelta(hours=24)
    cursor.execute('''
        SELECT id, type, severity, message, value, percentage, timestamp
        FROM alerts
        WHERE timestamp > ?
        ORDER BY timestamp DESC
        LIMIT 20
    ''', (since,))
    
    rows = cursor.fetchall()
    if rows:
        for row in rows:
            print(f"  ID {row[0]}: [{row[2]}] {row[1]} - {row[3]}")
            print(f"           Timestamp: {row[6]}")
    else:
        print("  ❌ Aucune alerte dans les dernières 24h")
    
    # 4. Afficher les dernières mesures
    print("\n📈 [MESURES] Dernières mesures:")
    cursor.execute('''
        SELECT id, value, percentage, state, timestamp
        FROM water_levels
        ORDER BY timestamp DESC
        LIMIT 5
    ''')
    
    rows = cursor.fetchall()
    if rows:
        for row in rows:
            print(f"  ID {row[0]}: {row[1]} ({row[2]}% - {row[3]}) @ {row[4]}")
    else:
        print("  ❌ Aucune mesure")
    
    # 5. Tester save_alert manuellement
    print("\n🧪 [TEST] Essai de sauvegarde d'une alerte directement:")
    try:
        cursor.execute('''
            INSERT INTO alerts (type, severity, message, value, percentage)
            VALUES (?, ?, ?, ?, ?)
        ''', ('test_alert', 'critique', 'Test d\'alerte', 900, 88.0))
        conn.commit()
        print("  ✓ Alerte TEST créée avec succès!")
        
        # Vérifier qu'elle est là
        cursor.execute("SELECT COUNT(*) FROM alerts WHERE type = 'test_alert'")
        test_count = cursor.fetchone()[0]
        print(f"  ✓ Total alertes test: {test_count}")
    except Exception as e:
        print(f"  ✗ Erreur: {e}")
    
    conn.close()
    print("\n" + "=" * 70)

if __name__ == '__main__':
    debug_database()
