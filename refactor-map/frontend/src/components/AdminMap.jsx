import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";

const createHospitalIcon = (color) =>
  L.divIcon({
    className: "",
    html: `<div style="
      width: 22px;
      height: 22px;
      background: ${color};
      border: 3px solid white;
      border-radius: 50%;
      box-shadow: 0 1px 5px #555;
    "></div>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });


const memberIcon = createHospitalIcon("#2563eb");
const nonMemberIcon = createHospitalIcon("#dc2626");

export default function AdminMap({ hospitals = [] }) {
  const hospitalsLocation = hospitals.filter((hospital) => {
    const lat = Number(hospital.location?.lat);
    const lon = Number(hospital.location?.lon);

    return (
      hospital.location?.lat != null &&
      hospital.location?.lon != null &&
      Number.isFinite(lat) &&
      Number.isFinite(lon)
    );
  });


  return (
    <MapContainer
      center={[36.5, 127.8]}
      zoom={7}
      style={{ height: "500px", width: "100%" }}
    >
      <TileLayer
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'
      />

      {hospitalsLocation.map((hospital) => (
        <Marker
          key={hospital._id}
          position={[
            Number(hospital.location.lat),
            Number(hospital.location.lon),
          ]}
          icon={hospital.is_member ? memberIcon : nonMemberIcon}
        >
          <Popup>
            {hospital.name}
            <br />
            HospitalID: {hospital.hospitalid}
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}