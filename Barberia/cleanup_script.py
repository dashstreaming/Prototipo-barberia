# clean_duplicates.py - Ejecutar UNA VEZ para limpiar duplicados

import sqlite3

def clean_duplicate_services():
    """Eliminar servicios duplicados manteniendo solo uno de cada tipo"""
    conn = sqlite3.connect('montana_barber.db')
    
    # Obtener todos los servicios ordenados por id (el más antiguo primero)
    cursor = conn.execute('''
        SELECT id, name, price, duration, description
        FROM services 
        ORDER BY name, id
    ''')
    services = cursor.fetchall()
    
    seen_names = set()
    ids_to_delete = []
    
    for service_id, name, price, duration, description in services:
        if name in seen_names:
            # Este es un duplicado, marcarlo para eliminación
            ids_to_delete.append(service_id)
            print(f"Marcando para eliminar duplicado: {name} (ID: {service_id})")
        else:
            # Primera vez que vemos este nombre, mantenerlo
            seen_names.add(name)
            print(f"Manteniendo: {name} (ID: {service_id})")
    
    # Eliminar los duplicados
    for service_id in ids_to_delete:
        conn.execute('DELETE FROM services WHERE id = ?', (service_id,))
        print(f"Eliminado servicio ID: {service_id}")
    
    conn.commit()
    
    # Mostrar servicios restantes
    print("\n=== SERVICIOS FINALES ===")
    cursor = conn.execute('SELECT id, name, price, duration FROM services ORDER BY name')
    for service in cursor.fetchall():
        print(f"ID: {service[0]}, Nombre: {service[1]}, Precio: ${service[2]}, Duración: {service[3]}min")
    
    conn.close()
    print(f"\n✅ Limpieza completada. Se eliminaron {len(ids_to_delete)} servicios duplicados.")

if __name__ == "__main__":
    print("🧹 Limpiando servicios duplicados...")
    clean_duplicate_services()
