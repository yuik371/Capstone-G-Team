from db.mongo import hospital_all_collection, patients_collection, emergency_request_collection
from services.sse_service import send_hospital_sse
from math import radians, sin, cos, sqrt, asin
import os
import osmnx as ox
import networkx as nx
from datetime import datetime,timezone, timedelta


#distance 계산식
def haversine(lat: float, lon: float, hospital_lat: float, hospital_lon: float):
    R = 6371

    lat1 = radians(lat)
    lon1 = radians(lon)
    lat2 = radians(hospital_lat)
    lon2 = radians(hospital_lon)

    deltalat = lat2 - lat1
    deltalon = lon2 - lon1

    sindeltalat = sin(deltalat / 2)
    sindeltalon = sin(deltalon / 2)
    squareRoot = sqrt(sindeltalat * sindeltalat + cos(lat1) * cos(lat2) * sindeltalon **2)

    distance = 2 * R * asin(squareRoot)

    return distance
    

#map-test (road_graph)
MAP_FILE_PATH = "map/chungju_road_network.graphml"

def get_roadNetwork_graph():
    if os.path.exists(MAP_FILE_PATH):
        print("캐시에서  지도 데이터를 불러오는 중")
        G = ox.load_graphml(MAP_FILE_PATH)

    else:
        print("OSM 서버에서 지도 데이터를 다운로드 중")
        G = ox.graph_from_place("Chungju-si, South Korea", network_type="drive")

        ox.save_graphml(G, MAP_FILE_PATH)
        print("지도 데이터 다운로드 및 저장")

    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)
    return G

G = get_roadNetwork_graph()

#가중치
def emergency_weight(u,v,data):
    best = float("inf")
    for edge in data.values():
        time = edge.get("travel_time", edge["length"]/10)
        hw = edge.get("highway")
        if hw == "residential" or (isinstance(hw,list) and "residential" in hw):
            time *= 1.3
        best = min(best,time)
    return best

def get_dijkstra(G,lat,lon,hospital_lat,hospital_lon):

    start = ox.nearest_nodes(G,X=lon, Y=lat,)
    end = ox.nearest_nodes(G,X=hospital_lon, Y=hospital_lat )

    route = nx.shortest_path(G, start, end, weight = emergency_weight)
    seconds = nx.shortest_path_length(G,start,end,weight=emergency_weight)

    return seconds

#distance 값 
async def get_nearest_hospital(lat,lon):
    hospitals = await hospital_all_collection.find().to_list(None)

    for hospital in hospitals:
        hospital_lat = float(hospital["location"]["lat"])
        hospital_lon = float(hospital["location"]["lon"])

        hospital["distance"] = haversine(lat,lon,hospital_lat,hospital_lon)

    hospitals.sort(key=lambda h:h["distance"])

    top10 =  hospitals[:10]
    for h in top10:
        try:
            h["eta_seconds"] = get_dijkstra(G,lat,lon,float(h["location"]["lat"]),float(h["location"]["lon"]))
        except nx.NetworkXNoPath:
            h["eta_seconds"] = None
    return top10


#recommend_hospital
async def get_recommend_hospital(req,lat: float, lon: float, severity: int, patientid):
    hospitals = await get_nearest_hospital(lat, lon)
    hospital_recommend = []

    for h in hospitals:
        if h["eta_seconds"] is None:
            continue
        eta_minutes = h["eta_seconds"] / 60
        score = 0
        score += 100.0 / (eta_minutes + 1.0)
        hospital_recommend.append({
            "hpid": h["hpid"],
            "hospitalid": h["hospitalid"],
            "name": h["name"],
            "is_member": h["is_member"],
            "eta_seconds": h["eta_seconds"],
            "er1_count": h["er1_count"],
            "er2_count": h["er2_count"],
            "er3_count": h["er3_count"],
            "er4_count": h["er4_count"],
            "location":{
                "lat": float(h["location"]["lat"]),
                "lon": float(h["location"]["lon"])
            },
            "score": score
        })
    hospital_recommend = sorted(hospital_recommend, key=lambda x: x["score"],reverse=True)[:5]

    for hospital_r in hospital_recommend:
        if hospital_r["is_member"]:
            await emergency_request_collection.insert_one({
                "patientid": patientid,
                "name": req.name,
                "age": req.age,
                "hospitalid": hospital_r["hospitalid"],
                "request_status": "pending",
                "symptom": req.symptom,
                "is_member": hospital_r["is_member"],
                "created_at": datetime.now(timezone(timedelta(hours=9)))
            })

            await send_hospital_sse(hospital_r["hospitalid"],"request","Amb:emergency_call")

        else:
            continue


    return hospital_recommend

async def create_patient_status(req, ambid, severity):
    result = await patients_collection.insert_one({
        "name": req.name,
        "age": req.age,
        "severity": severity,
        "symptom": req.symptom,
        "image": req.image,
        "request_status": "pending",
        "ambid": ambid,
        "hospitalid": None,
        "first_location": {
            "lat": req.lat,
            "lon": req.lon
        },
        "created_at": datetime.now(timezone(timedelta(hours=9))),
        "handled_at": None
    })

    return result

async def get_transported_patient(amb):
    cursor = patients_collection.find({
        "ambid": amb["ambid"],
        "request_status": "accepted"
    }).sort('handled_at',-1)

    patients = await cursor.to_list(length = 100)

    for patient in patients:
        patient["id"] = str(patient.pop("_id"))