import gtfs_kit as gk
import pandas as pd
import numpy as np
from collections import defaultdict
from typing import Dict, List, Any, Optional, Tuple

def load_gtfs_feed(gtfs_file: str):
    """Carga el archivo GTFS y prepara el feed para su uso"""
    feed = gk.read_feed(gtfs_file, dist_units="km")
    
    # Asegurar que stop_lat y stop_lon sean float
    feed.stops["stop_lat"] = feed.stops["stop_lat"].astype(float)
    feed.stops["stop_lon"] = feed.stops["stop_lon"].astype(float)
    
    return feed

def find_nearest_stop(feed, lat: float, lon: float) -> Dict[str, Any]:
    """Encuentra la parada más cercana a las coordenadas dadas"""
    # Calcular distancia a todas las paradas
    feed.stops["dist"] = ((feed.stops["stop_lat"] - lat) ** 2 + (feed.stops["stop_lon"] - lon) ** 2) ** 0.5
    
    # Obtener la parada más cercana
    nearest_stop = feed.stops.sort_values("dist").iloc[0]
    
    return {
        "id": nearest_stop["stop_id"],
        "name": nearest_stop["stop_name"],
        "lat": float(nearest_stop["stop_lat"]),
        "lon": float(nearest_stop["stop_lon"])
    }

def tiempo_a_minutos(tiempo_str):
    """Convierte tiempo en formato GTFS a minutos desde medianoche"""
    if pd.isna(tiempo_str):
        return None
    
    try:
        horas, minutos, segundos = map(int, tiempo_str.split(':'))
        return horas * 60 + minutos + segundos / 60
    except:
        return None

def calcular_tiempo_viaje(feed, trip_id, stop_id_origen, stop_id_destino):
    """Calcula el tiempo de viaje entre dos paradas en un viaje específico"""
    # Obtener los tiempos de las paradas para este viaje
    tiempos_viaje = feed.stop_times[feed.stop_times["trip_id"] == trip_id]
    
    # Verificar si hay datos de tiempo disponibles
    if "arrival_time" not in tiempos_viaje.columns or "departure_time" not in tiempos_viaje.columns:
        return None
    
    # Obtener tiempo de salida del origen
    tiempo_origen = tiempos_viaje[tiempos_viaje["stop_id"] == stop_id_origen]["departure_time"].iloc[0]
    
    # Obtener tiempo de llegada al destino
    tiempo_destino = tiempos_viaje[tiempos_viaje["stop_id"] == stop_id_destino]["arrival_time"].iloc[0]
    
    # Convertir a minutos
    minutos_origen = tiempo_a_minutos(tiempo_origen)
    minutos_destino = tiempo_a_minutos(tiempo_destino)
    
    if minutos_origen is None or minutos_destino is None:
        return None
    
    # Calcular duración
    duracion = minutos_destino - minutos_origen
    
    # Ajustar si cruza medianoche
    if duracion < 0:
        duracion += 24 * 60
    
    return duracion

def obtener_tiempo_promedio(feed, trips, stop_id_origen, stop_id_destino):
    """Obtiene el tiempo promedio de viaje para una lista de viajes"""
    tiempos = []
    for trip_id in trips:
        duracion = calcular_tiempo_viaje(feed, trip_id, stop_id_origen, stop_id_destino)
        if duracion is not None:
            tiempos.append(duracion)
    
    if tiempos:
        return int(np.mean(tiempos))
    else:
        return None

def obtener_paradas_ruta(feed, trip_id, stop_id_origen, stop_id_destino):
    """Obtiene las paradas de un viaje entre origen y destino"""
    # Obtener todas las paradas de este viaje en orden
    paradas_viaje = feed.stop_times[feed.stop_times["trip_id"] == trip_id].sort_values("stop_sequence")
    
    # Verificar si las paradas existen en este viaje
    if stop_id_origen not in paradas_viaje["stop_id"].values or stop_id_destino not in paradas_viaje["stop_id"].values:
        return None
    
    # Obtener índices de origen y destino
    idx_origen = paradas_viaje[paradas_viaje["stop_id"] == stop_id_origen].index[0]
    idx_destino = paradas_viaje[paradas_viaje["stop_id"] == stop_id_destino].index[0]
    
    # Verificar que el origen viene antes que el destino
    if idx_origen < idx_destino:
        # Obtener paradas entre origen y destino
        return paradas_viaje.loc[idx_origen:idx_destino]
    else:
        return None

def find_direct_routes(feed, origin_stop, destination_stop):
    """Encuentra rutas directas entre dos paradas"""
    # Filtrar los tiempos de las paradas
    stop_times_origen = feed.stop_times[feed.stop_times["stop_id"] == origin_stop["id"]]
    stop_times_destino = feed.stop_times[feed.stop_times["stop_id"] == destination_stop["id"]]
    
    trips_origen = stop_times_origen["trip_id"].unique()
    trips_destino = stop_times_destino["trip_id"].unique()
    
    # Encontrar viajes directos
    trips_validos = set(trips_origen).intersection(set(trips_destino))
    
    rutas_directas = []
    
    if trips_validos:
        # Agrupar viajes por ruta
        viajes_por_ruta = defaultdict(list)
        
        for trip_id in trips_validos:
            route_id = feed.trips[feed.trips["trip_id"] == trip_id]["route_id"].iloc[0]
            viajes_por_ruta[route_id].append(trip_id)
        
        # Procesar cada ruta
        for route_id, viajes in viajes_por_ruta.items():
            ruta_info = feed.routes[feed.routes["route_id"] == route_id].iloc[0]
            
            # Obtener un viaje representativo
            trip_id = viajes[0]
            
            # Obtener paradas de la ruta
            paradas_ruta = obtener_paradas_ruta(feed, trip_id, origin_stop["id"], destination_stop["id"])
            
            if paradas_ruta is not None:
                # Calcular tiempo promedio
                tiempo_promedio = obtener_tiempo_promedio(feed, viajes, origin_stop["id"], destination_stop["id"])
                
                # Obtener nombres de paradas
                paradas_nombres = []
                for _, parada in paradas_ruta.iterrows():
                    stop_info = feed.stops[feed.stops["stop_id"] == parada["stop_id"]].iloc[0]
                    paradas_nombres.append(stop_info["stop_name"])
                
                # Añadir a la lista de rutas directas
                rutas_directas.append({
                    "type": "direct",
                    "route_name": ruta_info.get("route_short_name", "Sin nombre"),
                    "route_description": ruta_info.get("route_long_name", "Sin descripción"),
                    "avg_time": tiempo_promedio,
                    "stops_count": len(paradas_ruta),
                    "boarding_stop": origin_stop["name"],
                    "destination_stop": destination_stop["name"],
                    "intermediate_stops": paradas_nombres[1:-1]
                })
    
    return rutas_directas

def find_routes(feed, lat_origen, lon_origen, lat_destino, lon_destino):
    """Encuentra todas las rutas posibles entre dos puntos"""
    # Encontrar las paradas más cercanas
    origin_stop = find_nearest_stop(feed, lat_origen, lon_origen)
    destination_stop = find_nearest_stop(feed, lat_destino, lon_destino)
    
    # Buscar rutas directas
    direct_routes = find_direct_routes(feed, origin_stop, destination_stop)
    
    # Combinar todas las rutas
    all_routes = []
    
    # Añadir rutas directas
    for route in direct_routes:
        all_routes.append({
            "type": route["type"],
            "total_time": route["avg_time"] or 999,
            "details": route
        })
    
    # Ordenar por tiempo total
    all_routes.sort(key=lambda x: x["total_time"])
    
    # Limitar a las 5 mejores opciones
    best_routes = all_routes[:5] if all_routes else []
    
    return {
        "origin_stop": origin_stop,
        "destination_stop": destination_stop,
        "routes": best_routes,
        "total_routes_found": len(all_routes)
    }