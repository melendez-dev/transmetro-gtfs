from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware  # Importar el middleware CORS
from pydantic import BaseModel
from typing import Dict, List, Optional, Union, Any
import gtfs_service

app = FastAPI(title="GTFS Route Finder API", 
              description="API para encontrar rutas de transporte público usando datos GTFS")

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # Cambia a False cuando uses allow_origins=["*"]
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

class Coordinates(BaseModel):
    lat: float
    lng: float

class RouteRequest(BaseModel):
    origin: Coordinates
    dest: Coordinates

@app.get("/")
def read_root():
    return {"message": "GTFS Route Finder API", 
            "usage": "Envía una solicitud POST a /routes con las coordenadas de origen y destino"}

@app.post("/routes")
async def find_routes(request: RouteRequest):
    try:
        # Cargar el feed GTFS (esto podría optimizarse para cargar solo una vez)
        feed = gtfs_service.load_gtfs_feed("Barranquilla_GTFS.zip")
        
        # Buscar rutas entre los puntos
        routes = gtfs_service.find_routes(
            feed, 
            request.origin.lat, request.origin.lng,
            request.dest.lat, request.dest.lng
        )
        
        return {
            "success": True,
            "origin": {
                "name": routes["origin_stop"]["name"],
                "coordinates": {
                    "lat": routes["origin_stop"]["lat"],
                    "lng": routes["origin_stop"]["lon"]
                }
            },
            "destination": {
                "name": routes["destination_stop"]["name"],
                "coordinates": {
                    "lat": routes["destination_stop"]["lat"],
                    "lng": routes["destination_stop"]["lon"]
                }
            },
            "routes": routes["routes"],
            "total_routes_found": routes["total_routes_found"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al buscar rutas: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
