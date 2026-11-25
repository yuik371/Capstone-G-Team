import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";

export default function HospitalMap({ hospital }) {
  const lat = Number(hospital.location.lat);
  const lon = Number(hospital.location.lon);

  return (
    <MapContainer
      center={[lat, lon]}
      zoom={15}
      style={{ height: "400px", width: "100%" }}
    >
      <TileLayer
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'
      />
      <Marker position={[lat, lon]}>
        <Popup>{hospital.name}</Popup>
      </Marker>
    </MapContainer>
  );
}