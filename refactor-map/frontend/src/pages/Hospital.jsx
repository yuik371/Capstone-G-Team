import { useEffect,useState,useRef } from "react";
import { fetchEventSource } from "@microsoft/fetch-event-source"
import { useNavigate } from "react-router-dom"
import HospitalMap from "../components/HospitalMap.jsx";
import patient_sound from "../assets/sound/amb_sound.mp3";
import ctImage from "../assets/equipment/ct.png";
import mriImage from "../assets/equipment/mri.png";
import angiographyImage from "../assets/equipment/angiography.png";
import ventilatorImage from "../assets/equipment/ventilator.png";
import ecmoImage from "../assets/equipment/ecmo.png";


import {
  Activity,
  AlertTriangle,
  Ambulance,
  Bell,
  Building2,
  Calendar,
  CheckCircle2,
  Clock,
  FileText,
  Heart,
  LogOut,
  Moon,
  PhoneCall,
  Power,
  RefreshCw,
  Shield,
  ShieldAlert,
  User,
  UserCheck,
  X,
  XCircle,
  Eye,
  ChevronRight,
  Info,
  MapPin,
  Music,
  Stethoscope,
  Bed,
  ShieldCheck,
  BarChart3
} from 'lucide-react';

const equipmentImages = {
    ct: ctImage,
    mri: mriImage,
    ventilator: ventilatorImage,
    angiography: angiographyImage,
    ecmo: ecmoImage
}

const VITE_SERVER_URL = import.meta.env.VITE_SERVER_URL;

export default function Hospital() {
    const navigate = useNavigate();
    const [hospital, setHospital] = useState({
    hospitalid: null,
    userid: '',
    name: '병원 정보 연동 대기',
    er_status: 'OFF',
    or_status: 'OFF'
    });
    const [activeTab, setActiveTab] = useState('dashboard');
    const [currentTime, setCurrentTime] = useState(new Date());
    const [requestsList, setRequestsList] = useState([]);
    const [requests, setRequests] = useState([]);
    const [message, setMessage] = useState("병원 정보 불러오는 중");
    const [sseStatus, setSseStatus] = useState("연결 중...");
    const [selectedImageModal, setSelectedImageModal] = useState(null);
    const [statsInfo, setStatsInfo] = useState(null);

    const [mapModalData, setMapModalData] = useState(null);
    const [isMapLoading, setIsMapLoading] = useState(false);

    const [acceptedPatients, setAcceptedPatients] = useState([]);

    const [AudioProcessing, setAudioProcessing] = useState(false);

    const [processing, setProcessing] = useState(null);
    const [rejectModalPatient, setRejectModalPatient] = useState(null);
    const [rejectReason, setRejectReason] = useState('응급실 병상 포화');
    const [customRejectReason, setCustomRejectReason] = useState('');
    const [erInfo, setErInfo ] =useState(null);
    const [equipmentInfo, setEquipmentInfo ] = useState({});

    const REJECT_REASONS = [
        '응급실 병상 포화',
        '수술실 가용 불가 (집도 중)',
        '중환자실(ICU) 병상 부족',
        '해당 진료과 전문의 부재',
        '필수 의료장비·시설 가동 불가',
        '격리 병상 부족 (감염 의심)',
        '기타'
    ];
    const audioRef = useRef(null);
    function logout() {
    sessionStorage.removeItem("access_token");
    navigate("/login")
    }

    function getHeaders() {
        const token = sessionStorage.getItem("access_token");

        if(!token){
            navigate("/login")
            return null;
        }

        return {Authorization: `Bearer ${token}`};
    }

    async function patientSound() {
        try{
            const audio = audioRef.current;
            audio.currentTime = 0;
            await audio.play();
        } catch (error){
            console.error("알람음 재생 실패", error);
        }
    }




    useEffect(()=>{
        audioRef.current = new Audio(patient_sound);
    }, []);

    async function enableSound(){
        try{
            await audioRef.current.play();
            audioRef.current.pause();
            audioRef.current.currentTime = 0;
            console.log("알람음 활성화");
            setAudioProcessing(true);
        } catch (error){
            console.error("알람음 활성화 실패", error);
        }
    }
    

    async function loadInfo() {
        const headers = getHeaders();
        if (!headers) return;
        try{
            const hospitalTopstatus = await fetch(`${VITE_SERVER_URL}/hospital/info`, {headers});
            const topstatusData = await hospitalTopstatus.json();
            
            if(!hospitalTopstatus.ok){
                throw new Error(topstatusData.detail || "병원 정보 오류");
            }

            setHospital(topstatusData);
            setMessage("");
            
        } catch(error){
            setMessage(error.message);
        }
    }

    async function loadStatsInfo() {
        const headers = getHeaders();
        if(!headers) return;
        
        try{
            const hospitalStatsInfo = await fetch(`${VITE_SERVER_URL}/hospital/info/stats`,{headers});
            const statsInfoData = await hospitalStatsInfo.json();

            if(!hospitalStatsInfo.ok){
                throw new Error(statsInfoData.detail || "병원 정보 오류");
            }
            setStatsInfo(statsInfoData);
            setmessage("");
        } catch (err){
            setmessage(error.message);
        }
    }

    async function loadErInfo() {
        const headers = getHeaders();
        if(!headers) return;

        try{
            const hospitalErInfo = await fetch(`${VITE_SERVER_URL}/hospital/info/er`, {headers});
            const erInfoData = await hospitalErInfo.json();

            if(!hospitalErInfo.ok){
                throw new Error(erInfoData.detail || "병원 정보 오류");
            }
            setErInfo(erInfoData);
        }catch(error){
            setMessage(error.message);
        }
        
    }

    async function loadEquipmentInfo(){
        const headers = getHeaders();
        if(!headers) return;

        try{
            const hospitalEquipmentInfo = await fetch(`${VITE_SERVER_URL}/hospital/info/equipment`,{headers});
            const equipmentInfoData = await hospitalEquipmentInfo.json();

            if(!hospitalEquipmentInfo.ok){
                throw new Error(equipmentInfoData.detail ||"병원 정보 오류");
            }
                        
            setEquipmentInfo(equipmentInfoData.equipment ?? {});
        } catch(error){
            setMessage(error.message);
        }
    }

    async function updateHospitalStatus(field) {
        if(!hospital) return;
        const headers = getHeaders();
        if(!headers) return;
        const nextStatus = hospital[field] === "ON" ? "OFF" : "ON" ;
        const res = await fetch(`${VITE_SERVER_URL}/hospital/status`, {
            method: "PATCH",
            headers:{
                ...headers,
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ [field]: nextStatus }),
        });
        const data = await res.json()
        if(!res.ok) {
            throw new Error (data.detail || "상태 변경에 실패")
        }
        setHospital((prev) => ({ ...prev, [field]: data[field] ?? nextStatus}))
    }

        const toggleErStatus = async () => {
        updateHospitalStatus("er_status");
    };

    const toggleOrStatus = async () => {
        updateHospitalStatus("or_status");
    };


    async function loadRequests() {
        const headers = getHeaders();
        if (!headers) return;
        try{
            const hospitalRequests = await fetch(`${VITE_SERVER_URL}/hospital/requests`, {headers});
            const requestsData = await hospitalRequests.json();

            if(!hospitalRequests.ok){
                    throw new Error(requestsData.detail || "환자 요청 정보 오류");
            }
            setRequests(Array.isArray(requestsData) ? requestsData:[]);
            setMessage("");

        } catch(error){
            setMessage(error.message);
        }
    }
    
    

    async function loadAcceptedPatients() {
        const headers = getHeaders();
        if (!headers) return;

        try{
            const hospitalAccepted = await fetch(`${VITE_SERVER_URL}/hospital/accepted`, {headers});
            const acceptedData = await hospitalAccepted.json();

            if(!hospitalAccepted.ok){
                throw new Error(acceptedData.detail || "환자 리스트 정보 오류");
            }
            setAcceptedPatients(Array.isArray(acceptedData)? acceptedData:[]);
            setMessage("");
        } catch(error){
            setMessage(error.message);
        }        
    }

    async function loadRequestsList() {
        const headers = getHeaders();
        if (!headers) return;

        try{
            const hospitalRequestsList = await fetch(`${VITE_SERVER_URL}/hospital/requests/list`, {headers});
            const requestsListData = await hospitalRequestsList.json();

            if(!hospitalRequestsList.ok){
                throw new Error(requestsListData.detail || "환자 리스트 정보 오류");
            }
            setRequestsList(Array.isArray(requestsListData)? requestsListData:[]);
            setMessage("");
        } catch(error){
            setMessage(error.message);
        }        
    }

    async function loadHospitalMap() {
        const headers = getHeaders();
        if(!headers) return;
        setIsMapLoading(true);

        try{
            const hospitalMap = await fetch(`${VITE_SERVER_URL}/hospital/map`, {headers});
            const hospitalMapData = await hospitalMap.json();
            if(!hospitalMap.ok){
                throw new Error(hospitalMapData.detail || "병원 위치 정보 오류");
            }
            setMapModalData(hospitalMapData);
        } catch (error){
            throw new Error("병원 지도 오류")
        } finally {
            setIsMapLoading(false);
        }
    }

    const handleAcceptRequest = async (patient) => {
        const patientid = patient.patientid;
        setProcessing(patientid);
        try{
            const headers = getHeaders();
            if(!headers) return;
            const res = await fetch(`${VITE_SERVER_URL}/hospital/requests/${patientid}/decision`, {
                method: 'PATCH',
                headers: {
                    ...headers,
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({decision: "accepted"})
            })
            if(!res.ok){
                throw new Error("수락 실패");
            }
            
        } catch (error){
            setMessage("수락 오류")
        } finally {
            setProcessing(null);
        }
    }
    const handleAllowIp = async () => {
        const inputIp = window.prompt("허용할 IP 주소를 입력하세요 (예: 123.45.67.89)");
        if (!inputIp) return;

        const ip = inputIp.trim();
        // 간단한 IPv4 형식 체크
        const ipv4Regex = /^(?:\d{1,3}\.){3}\d{1,3}$/;
        if (!ipv4Regex.test(ip)) {
            alert("올바른 IPv4 형식으로 입력해 주세요.");
            return;
        }

        try {
            const headers= getHeaders();
            if(!headers) return;

            const res = await fetch(`${VITE_SERVER_URL}/auth/allowed-ip`,{
                method: 'POST',
                headers:{
                    ...headers,
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ip: ip})
            })

            alert(`${ip} 허용 요청을 처리했습니다.`);

        } catch (err) {
            console.error(err);
            alert("IP 등록 중 오류가 발생했습니다.");
        }
    };


    const openRejectModal = (patient) => {
    setRejectModalPatient(patient);
    setRejectReason(REJECT_REASONS[0]);
    setCustomRejectReason('');
  };

  const handleRejectRequest = async () => {
    if(!rejectModalPatient) return;
    const headers = getHeaders();
    if(!headers) return;
    
    const patientid = rejectModalPatient.patientid;
    setProcessing(patientid);
    const finalReason = rejectReason === '기타' ? customRejectReason.trim() || '기타 사유 (상세 미입력)' : rejectReason;
    
    try{
        const res = await fetch(`${VITE_SERVER_URL}/hospital/requests/${patientid}/decision`,{
            method: 'PATCH',
            headers: {
                ...headers,
                "Content-Type": "application/json" 
            },
            body: JSON.stringify({decision: 'rejected', rejection_reason: finalReason})
        });
        if(!res.ok){
                throw new Error("수락 실패");
            }
    } catch(error){
        setMessage("거절 오류");
    } finally {
        setProcessing(null);
        setRejectModalPatient(null);
        setCustomRejectReason('');
    }
  }

  const formattedDateStr = currentTime.toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }) + ' ' + currentTime.toLocaleTimeString('ko-KR', { timeZone: "Asia/Seoul", hour12: true });

  function formatKoreaDateTime(value) {
    if (!value) return "-";

    const str = String(value).trim();
    const hasTimezone = /([zZ]|[+-]\d{2}:\d{2})$/.test(str);
    const date = new Date(hasTimezone ? str : `${str}Z`);

    if (Number.isNaN(date.getTime())) return "-";

    return date.toLocaleString("ko-KR", {
        timeZone: "Asia/Seoul",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: true,
    });
}

    function formatRelativeTime(value) {
        if (!value) return "-";

        const str = String(value).trim();
        const hasTimezone = /([zZ]|[+-]\d{2}:\d{2})$/.test(str);
        const date = new Date(hasTimezone ? str : `${str}Z`);

        if (Number.isNaN(date.getTime())) return "-";

        const diffMs = Date.now() - date.getTime();
        const diffSec = Math.floor(diffMs / 1000);

        // 혹시 시간 오차로 미래 시각이 잡히는 경우 방어
        if (diffSec < 10) return "방금 전";
        if (diffSec < 60) return `${diffSec}초 전`;

        const diffMin = Math.floor(diffSec / 60);
        if (diffMin < 60) return `${diffMin}분 전`;

        const diffHour = Math.floor(diffMin / 60);
        if (diffHour < 24) return `${diffHour}시간 전`;

        const diffDay = Math.floor(diffHour / 24);
        return `${diffDay}일 전`;
    }




    useEffect(() =>{  
        loadInfo();
        loadRequests();
        loadAcceptedPatients();
        loadHospitalMap();
        loadRequestsList();
        loadErInfo();
        loadEquipmentInfo();
        loadStatsInfo();
    }, []);

    useEffect(()=>{
        const headers = getHeaders();
        if(!headers) return;

        const controller = new AbortController();

        fetchEventSource(`${VITE_SERVER_URL}/hospital/sse`,{
            headers,
            signal: controller.signal,
            async onopen(response) {
                const type = response.headers.get("content-type") || "";
                if (response.ok && type.startsWith("text/event-stream")) {
                    console.log("SSE 연결 성공");
                    setSseStatus("연결 성공");
                } else {
                    throw new Error(`SSE 연결 실패: ${response.status}`);
                }
            },

            onmessage(event){
                console.log("SSE 수신:", event.event, event.data);
                if (event.event === "request"){
                    console.log("SSE 성공");
                    loadRequests();
                    loadAcceptedPatients();
                    patientSound();

                }
                else if (event.event === "request_changed"){
                    console.log("SSE 성공: Chaanged");
                    loadRequests();
                    loadAcceptedPatients();
                }
            },

            onerror(error){
                console.error("SSE 연결 오류", error);
                setSseStatus("재연결 중...");
            },
        }).catch((error)=> {
            if(!controller.signal.aborted){
                console.error("SSE 종료",error)
            }
        });
        return () => controller.abort();

    }, []);


    return(
        <div className="flex h-screen w-full bg-[#F8FAFC] font-sans antialiased text-slate-800 overflow-hidden">
            <aside className="w-64 bg-[#0f2147] text-white flex flex-col justify-between shrink-0 shadow-2xl border-r border-slate-800 z-20">
                <div>
                    <div className="p-6 border-b border-slate-800/80 flex items-center space-x-3">
                        <div className="w-10 h-10 bg-red-600 rounded-xl flex items-center justify-center text-white shadow-lg shadow-red-900/40 font-bold text-xl">
                        +
                        </div>
                        <div>
                            <h1 className="font-extrabold text-xl tracking-tight text-white flex items-center gap-1.5">
                                ER-LINK
                            </h1>
                            <p className="text-[11px] text-slate-400 font-medium">응급 환자 수용 관제 플랫폼</p>
                        </div>
                    </div>
                        <div className="mx-4 my-5 p-4 bg-slate-900/70 border border-slate-800 rounded-xl text-center">
                            <div className="w-12 h-12 bg-slate-800 border border-slate-700 rounded-full flex items-center justify-center mx-auto mb-2 text-slate-300">
                                <Building2 className="w-6 h-6 text-sky-400" />
                            </div>
                            <div className="font-bold text-white text-base truncate" title={hospital.name}>
                                {hospital.name || '병원 미연동'} 
                            </div>
                            <div className="text-xs text-slate-400 mt-0.5 truncate">
                                HospitalID: {hospital.hospitalid || '-'}
                            </div>
                            <div className="mt-3 space-y-2">
                                <button
                                    onClick={loadHospitalMap}
                                    disabled={isMapLoading}
                                    className="w-full py-1.5 px-3 bg-sky-500/15 hover:bg-sky-500/25 text-sky-300 hover:text-sky-200 text-xs font-semibold rounded-lg transition flex items-center justify-center gap-1.5 border border-sky-500/30"
                                >
                                    <MapPin className="w-3.5 h-3.5 text-sky-400" />
                                    {isMapLoading ? '위치 조회 중...' : '병원 위치 조회 (지도)'}
                                </button>
                                <button
                                    onClick={enableSound}
                                    className="w-full py-1.5 px-3 bg-slate-800/90 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-semibold rounded-lg transition flex items-center justify-center gap-1.5 border border-slate-700/60"
                                    >
                                    <Music className={`w-3.5 h-3.5 ${AudioProcessing ? "text-slate-400" : "text-rose-400"}`} />
                                    {AudioProcessing ? "알람음 활성화" : "알람음 비 활성화"}
                                </button>
                                <button
                                    onClick={handleAllowIp}
                                    className="w-full py-1.5 px-3 bg-slate-800/90 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-semibold rounded-lg transition flex items-center justify-center gap-1.5 border border-slate-700/60"
                                >
                                <ShieldCheck className="w-3.5 h-3.5 text-slate-400" />
                                IP 허용
                                </button>
                                <button
                                    onClick={logout}
                                    className="w-full py-1.5 px-3 bg-slate-800/90 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-semibold rounded-lg transition flex items-center justify-center gap-1.5 border border-slate-700/60"
                                    >
                                    <LogOut className="w-3.5 h-3.5 text-slate-400" />
                                    로그아웃
                                </button>
                            </div>
                        </div>

                        <nav className="px-3 space-y-1">
                            <button
                            onClick={() => setActiveTab('dashboard')}
                            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition ${
                                activeTab === 'dashboard'
                                ? 'bg-blue-600/90 text-white shadow-lg shadow-blue-900/30'
                                : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200'
                            }`}
                            >
                                <Activity className="w-5 h-5" />
                                응급 환자 수용 관제
                            </button>
                            
                            <button
                                onClick={() => setActiveTab('requests_list')}
                                className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition ${
                                    activeTab === 'requests_list'
                                    ? 'bg-blue-600/90 text-white shadow-lg shadow-blue-900/30'
                                    : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200'
                                }`}
                                >
                                <FileText className="w-5 h-5" />
                                환자 처리 이력
                            </button>
                            <button
                                onClick={() => setActiveTab('er_status')}
                                className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition ${
                                    activeTab === 'er_status'
                                    ? 'bg-blue-600/90 text-white shadow-lg shadow-blue-900/30'
                                    : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200'
                                }`}
                                >
                                <Bed className="w-5 h-5" />
                                병상 현황
                            </button>
                            <button
                                onClick={() => setActiveTab('equipment')}
                                className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition ${
                                    activeTab === 'equipment'
                                    ? 'bg-blue-600/90 text-white shadow-lg shadow-blue-900/30'
                                    : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200'
                                }`}
                                >
                                <Stethoscope className="w-5 h-5" />
                                의료 장비 현황
                            </button>
                            <button
                                onClick={() => setActiveTab('stats')}
                                className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition ${
                                    activeTab === 'stats'
                                    ? 'bg-blue-600/90 text-white shadow-lg shadow-blue-900/30'
                                    : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200'
                                }`}
                                >
                                <BarChart3 className="w-5 h-5" />
                                통계
                            </button>
                        </nav>
                    </div>
                     <div className="p-4 border-t border-slate-800/80 bg-slate-950/40 text-center">
                        <p className="text-[11px] text-slate-500 font-medium">ER-LINK Control System</p>
                    </div>           
                </aside>   

                <div className="flex-1 flex flex-col overflow-hidden">
                    <header className="h-20 bg-white border-b border-slate-200/80 px-6 lg:px-8 flex items-center justify-between shrink-0 shadow-sm z-10 overflow-x-auto">
                        <div className="flex items-center space-x-4 shrink-0">
                            <div className="flex items-center gap-3">
                                <div className="w-9 h-9 rounded-lg bg-red-100 border border-red-200 flex items-center justify-center shrink-0">
                                    <ShieldAlert className="w-5 h-5 text-red-600" />
                                </div>
                                <div>
                                    <div className="flex items-center gap-2 whitespace-nowrap">
                                        <h2 className="text-xl font-black text-slate-900 tracking-tight">
                                            {hospital.name || "병원 미연동"}{" "}
                                                <small className="inline-flex items-center gap-1.5 text-xs">
                                                    실시간 상태 연결: {sseStatus} <span className={`h-2 w-2 rounded-full ${sseStatus === "연결 성공" ? "bg-green-500" : "bg-yellow-400"}`}/> 
                                                </small>
                                        </h2>
                                        <span className="text-xs bg-slate-100 text-slate-600 px-2.5 py-0.5 rounded-full border border-slate-200 font-medium">
                                            {hospital.userid || '-'}
                                        </span>
                                    </div>
                                    <div className="text-xs text-slate-500 mt-0.5 flex items-center gap-2 whitespace-nowrap">
                                        <span>환자 수용 관제 모니터링</span>
                                        <span className="text-slate-300">•</span>
                                        <span className="font-mono text-slate-600 font-medium">{formattedDateStr}</span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="flex items-center gap-4 shrink-0 ml-4">
                            <div className="flex items-center gap-2 bg-slate-50 p-1.5 rounded-xl border border-slate-200 shrink-0">
                                <div className="flex items-center gap-2 px-3 py-1.5 bg-white rounded-lg border border-slate-200 shadow-sm shrink-0">
                                    <span className="text-xs font-bold text-slate-700 whitespace-nowrap">응급실</span>
                                    {hospital && ( <button
                                    onClick={toggleErStatus}
                                    className={`px-3 py-1 text-xs font-extrabold rounded-md transition flex items-center gap-1 whitespace-nowrap ${
                                        hospital.er_status === 'ON'
                                        ? 'bg-emerald-500 text-white shadow-sm hover:bg-emerald-600'
                                        : 'bg-slate-300 text-slate-600 hover:bg-slate-400'
                                    }`}
                                    >
                                    {hospital.er_status}
                                    </button>)}
                                </div>
                                <div className="flex items-center gap-2 px-3 py-1.5 bg-white rounded-lg border border-slate-200 shadow-sm shrink-0">
                                    <span className="text-xs font-bold text-slate-700 whitespace-nowrap">수술실</span>
                                    {hospital && (<button
                                    onClick={toggleOrStatus}
                                    className={`px-3 py-1 text-xs font-extrabold rounded-md transition flex items-center gap-1 whitespace-nowrap ${
                                        hospital.or_status === 'ON'
                                        ? 'bg-emerald-500 text-white shadow-sm hover:bg-emerald-600'
                                        : 'bg-slate-300 text-slate-600 hover:bg-slate-400'
                                    }`}
                                    >
                                    {hospital.or_status}
                                    </button>)}
                                </div>
                            </div>
                        </div>
                    </header>

                    <main className="flex-1 overflow-y-auto p-8 bg-[#F8FAFC]">
                        {activeTab === "dashboard" && (
                            <DashboardContent
                                requests={requests}
                                acceptedPatients={acceptedPatients}
                                mapModalData={mapModalData}
                                processing={processing}
                                handleAcceptRequest={handleAcceptRequest}
                                openRejectModal={openRejectModal}
                                setSelectedImageModal={setSelectedImageModal}
                                formatKoreaDateTime={formatKoreaDateTime}
                                erInfo={erInfo}
                                formatRelativeTime={formatRelativeTime}
                                handleAllowIp={handleAllowIp}
                            />
                            )}
                        {activeTab === "requests_list" && (
                            <RequestslistContent 
                            requestsList={requestsList}
                            />
                            )}

                        {activeTab === "er_status" && (
                            <ErstatusContent
                            erInfo={erInfo}
                            />
                        )}

                        {activeTab === "equipment" &&(
                            <EquipmentContent
                            equipmentInfo={equipmentInfo}
                            />
                        )}
                        {activeTab === "stats" &&(
                            <StatsContent
                            statsInfo={statsInfo}
                            />
                        )}
                    </main>
                </div>

                {selectedImageModal && (
                <div className="fixed inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center p-6 z-50 animate-fade-in">
                <div className="bg-white rounded-2xl max-w-2xl w-full overflow-hidden shadow-2xl">
                    <div className="p-4 border-b border-slate-200 flex justify-between items-center bg-slate-50">
                    <h3 className="font-extrabold text-slate-900 text-sm flex items-center gap-2">
                        <Eye className="w-4 h-4 text-blue-600" /> 외상 현장 사진 상세보기
                    </h3>
                    <button
                        onClick={() => setSelectedImageModal(null)}
                        className="p-1 hover:bg-slate-200 rounded-lg text-slate-500 transition"
                    >
                        <X className="w-5 h-5" />
                    </button>
                    </div>
                    <div className="p-4 bg-slate-950 flex justify-center items-center max-h-[70vh]">
                    <img src={selectedImageModal} alt="확대된 외상 사진" className="max-h-[65vh] object-contain rounded-lg" />
                    </div>
                    <div className="p-4 bg-white flex justify-end">
                    <button
                        onClick={() => setSelectedImageModal(null)}
                        className="px-4 py-2 bg-slate-800 text-white font-bold text-xs rounded-xl hover:bg-slate-700 transition"
                    >
                        닫기
                    </button>
                    </div>
                </div>
                </div>
            )}

            {rejectModalPatient && (
                <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-fade-in">
                <div className="bg-white rounded-2xl max-w-md w-full overflow-hidden shadow-2xl border border-slate-200">
                    <div className="p-5 border-b border-slate-200 flex justify-between items-center bg-slate-50">
                    <div className="flex items-center gap-2">
                     Y   <XCircle className="w-5 h-5 text-red-600" />
                        <h3 className="font-extrabold text-slate-900 text-base">환자 수용 거절 사유 선택</h3>
                    </div>
                    <button
                        onClick={() => setRejectModalPatient(null)}
                        className="p-1 hover:bg-slate-200 rounded-lg text-slate-500 transition"
                    >
                        <X className="w-5 h-5" />
                    </button>
                    </div>

                    <div className="p-6 space-y-4">
                    <div className="p-3.5 bg-red-50/70 border border-red-100 rounded-xl text-xs text-slate-700">
                        <div className="font-bold text-slate-900 mb-0.5">
                        대상 환자: {rejectModalPatient.name || '신원 미상'} ({rejectModalPatient.severity})
                        </div>
                        <div className="text-slate-500">
                        구급대: {rejectModalPatient.ambid} • 환자번호: {rejectModalPatient.patientid}
                        </div>
                    </div>

                    <div>
                        <label className="block text-xs font-extrabold text-slate-700 mb-2">
                        수용 불가 사유 <span className="text-red-500">*</span>
                        </label>
                        <select
                        value={rejectReason}
                        onChange={(e) => setRejectReason(e.target.value)}
                        className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-red-500/20 focus:border-red-500 transition"
                        >
                        {REJECT_REASONS.map((reason) => (
                            <option key={reason} value={reason}>
                            {reason}
                            </option>
                        ))}
                        </select>
                    </div>

                    {rejectReason === '기타' && (
                        <div className="animate-fade-in">
                        <label className="block text-xs font-extrabold text-slate-700 mb-2">
                            상세 사유 직접 입력 <span className="text-red-500">*</span>
                        </label>
                        <textarea
                            rows={3}
                            value={customRejectReason}
                            onChange={(e) => setCustomRejectReason(e.target.value)}
                            placeholder="구급대원에게 전달할 구체적인 수용 불가 사유를 입력하세요."
                            className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-red-500/20 focus:border-red-500 transition resize-none"
                        />
                        </div>
                    )}
                    </div>

                    <div className="px-6 py-4 bg-slate-50 border-t border-slate-200 flex justify-end gap-2.5">
                    <button
                        onClick={() => setRejectModalPatient(null)}
                        className="px-4 py-2 bg-white border border-slate-300 text-slate-700 font-bold text-xs rounded-xl hover:bg-slate-100 transition"
                    >
                        취소
                    </button>
                    <button
                        onClick={handleRejectRequest}
                        disabled={rejectReason === '기타' && !customRejectReason.trim()}
                        className="px-5 py-2 bg-red-600 hover:bg-red-700 disabled:bg-slate-300 disabled:cursor-not-allowed text-white font-extrabold text-xs rounded-xl transition shadow-sm"
                    >
                        거절 확정
                    </button>
                    </div>
                </div>
                </div>
            )}

            
            </div>
        );
        }

function DashboardContent({
    requests,
    acceptedPatients,
    mapModalData,
    processing,
    handleAcceptRequest,
    openRejectModal,
    setSelectedImageModal,
    formatKoreaDateTime,
    erInfo,
    formatRelativeTime,
    handleAllowIp
}) {
    return (
                <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        <section className="lg:col-span-7 xl:col-span-8 space-y-4">
            <div className="flex items-center justify-between pb-2">
            <div className="flex items-center gap-3">
                <h3 className="text-lg font-black text-slate-900 tracking-tight flex items-center gap-2">
                응급실 환자 수용 요청
                </h3>

                <span className="w-6 h-6 rounded-full bg-red-600 text-white text-xs font-black flex items-center justify-center shadow-xs">
                {requests.length}
                </span>
            </div>
            </div>

            {requests.length === 0 ? (
            <div className="bg-white border border-slate-200/90 rounded-2xl p-16 text-center shadow-xs">
                <div className="w-16 h-16 bg-slate-50 border border-slate-100 rounded-full flex items-center justify-center mx-auto mb-4 text-slate-300">
                <Ambulance className="w-8 h-8 text-slate-400" />
                </div>

                <h4 className="text-base font-bold text-slate-700 mb-1">
                대기 중인 환자 수용 요청이 없습니다.
                </h4>

                <p className="text-xs text-slate-400 max-w-sm mx-auto">
                새로운 구급대 수용 요청이 접수되면 알림 소리와 함께 실시간으로 표시됩니다.
                </p>
            </div>
            ) : (
            <div className="space-y-4">
                {requests.map((patient) => {
                const patientId = patient.patientid
                const hasImage = patient.image && patient.image !== "noimage";

                return (
                    <div
                    key={patientId}
                    className="bg-white rounded-2xl border border-slate-200/90 shadow-md hover:shadow-lg transition overflow-hidden border-l-4 border-l-red-600"
                    >
                    <div className="p-6">
                        <div className="flex flex-col md:flex-row gap-6">
                        <div className="w-full md:w-44 h-44 bg-slate-100 rounded-xl border border-slate-200 relative overflow-hidden shrink-0 flex flex-col justify-center items-center group">
                            {hasImage ? (
                            <>
                                <img
                                src={patient.image}
                                alt="외상 사진"
                                className="w-full h-full object-cover group-hover:scale-105 transition duration-300"
                                />

                                <div className="absolute inset-0 bg-black/30 opacity-0 group-hover:opacity-100 transition flex items-center justify-center">
                                <button
                                    type="button"
                                    onClick={() => setSelectedImageModal(patient.image)}
                                    className="px-3 py-1.5 bg-white/90 backdrop-blur-xs text-slate-900 rounded-lg text-xs font-bold flex items-center gap-1.5 shadow-lg"
                                >
                                    <Eye className="w-3.5 h-3.5" />
                                    크게 보기
                                </button>
                                </div>

                                <div className="absolute bottom-2 left-2 right-2 bg-slate-900/80 backdrop-blur-xs text-white text-[11px] py-1 text-center font-medium rounded">
                                외상 사진 (확인 가능)
                                </div>
                            </>
                            ) : (
                            <div className="text-center p-4">
                                <div className="w-10 h-10 rounded-full bg-slate-200/80 flex items-center justify-center mx-auto mb-2 text-slate-400">
                                <Eye className="w-5 h-5" />
                                </div>
                                <span className="text-xs text-slate-400 font-medium">
                                외상 사진 없음
                                </span>
                            </div>
                            )}
                        </div>

                        <div className="flex-1 flex flex-col justify-between">
                            <div>
                            <div className="flex items-center justify-between mb-2">
                                <div className="flex items-center gap-2">
                                <span className="px-2.5 py-1 bg-red-600 text-white text-xs font-extrabold rounded-md shadow-2xs">
                                    중증도: {patient.severity}
                                </span>

                                <span className="rounded-md bg-amber-100 px-2.5 py-1 text-xs font-bold text-amber-900">
                                    주 증상: {patient.symptom || "증상 미입력"}
                                </span>
                                </div>

                                <span className="text-xs text-slate-400 flex items-center gap-1 font-medium">
                                <Clock className="w-3.5 h-3.5" />
                                    접수:{" "} {patient.created_at ? formatKoreaDateTime(patient.created_at): "-"}
                                </span>
                            </div>

                            <h4 className="text-xl font-extrabold text-slate-900 tracking-tight">
                                {patient.name || "신원 미상"}
                            </h4>

                            <div className="mt-3 p-3 bg-slate-50 border border-slate-100 rounded-xl text-xs text-slate-700">
                                <div className="flex items-center gap-2 mb-1">
                                <Ambulance className="w-4 h-4 text-slate-500" />
                                <span className="font-semibold">구급차 ID:</span>
                                {patient.ambid || "-"}
                                </div>
                            </div>
                            </div>

                            <div className="mt-5 pt-4 border-t border-slate-100 flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className="text-left">
                                <div className="text-[11px] text-slate-400">
                                    예상 도착 (ETA)
                                </div>
                                <div className="text-xs font-bold text-slate-800">
                                    <span className="text-blue-600 font-extrabold text-sm">
                                    {patient.eta || "미정"}
                                    </span>
                                </div>
                                </div>
                            </div>

                            <div className="flex items-center gap-3">
                                <button
                                type="button"
                                onClick={() => openRejectModal(patient)}
                                disabled={processing === patientId}
                                className="px-5 py-2.5 bg-white border border-slate-300 hover:bg-red-50 hover:border-red-300 text-red-600 font-bold text-sm rounded-xl transition shadow-2xs disabled:opacity-50"
                                >
                                거절
                                </button>

                                <button
                                type="button"
                                onClick={() => handleAcceptRequest(patient)}
                                disabled={processing === patientId}
                                className="px-6 py-2.5 bg-blue-700 hover:bg-blue-800 text-white font-extrabold text-sm rounded-xl transition shadow-md shadow-blue-900/20 active:scale-95 disabled:opacity-50"
                                >
                                {processing === patientId ? "처리 중..." : "수락"}
                                </button>
                            </div>
                            </div>
                        </div>
                        </div>
                    </div>
                    </div>
                );
                })}
            </div>
            )}
        </section>
        <section className="lg:col-span-5 xl:col-span-4 space-y-4">
            <h3 className="text-lg font-black text-slate-900">병원 위치</h3>

            <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                {mapModalData?.location?.lat != null && mapModalData?.location?.lon != null && (<HospitalMap hospital={mapModalData} /> )}
            </div>
            
            <div className="flex items-center justify-between pb-2">
                <h3 className="test-lg font-black text-slate-900 tracking-tight">
                병상 현황 <span className="inline-flex items-center gap-1 text-xs text-slate-500"><Clock className="w-3.5 h-3.5" />{formatKoreaDateTime(erInfo?.updated_at ?? "정보 없음")} {erInfo?.updated_at && `(${formatRelativeTime(erInfo.updated_at)})`} </span>
                </h3>
            </div>
            <div className="bg-white border border-slate-200/90 rounded-2xl p-4 shadow-xs">
                {erInfo === null ? (
                    <div className="py-12 px-4 text-center">
                        <div className="w-12 h-12 bg-slate-50 border border-slate-100 rounded-full items-center justify-center mx-auto mb-3 text-slate-300">
                            <UserCheck className="w-6 h-6 text-slate-400" />
                        </div>
                        <h4 className="text-sm font-bold text-slate-700">병상 정보를 찾을 수 없습니다.</h4>
                    </div>  
                    ):(
                    <div className="py-2 px-2 font-bold">
                        {erInfo.er_count >= 10 ? (
                            <div className="text-slate-950">
                            <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 mr-1"/>
                            <span className="bg-emerald-50 text-emerald-700 mr-2 text-xs px-1.5 py-0.5 rounded">여유</span>
                            응급실 일반 병상: <span className="text-slate-950">{erInfo.er_count}</span>
                            </div>
                        ): erInfo.er_count >=4 ? (
                            <div className="text-slate-950">
                            <span className="inline-block w-2 h-2  rounded-full bg-amber-600 mr-1"/>
                            <span className="bg-amber-50 text-amber-700 mr-2 text-xs px-1.5 py-0.5 rounded">주의</span>
                            응급실 일반 병상: <span className="text-amber-600">{erInfo.er_count}</span>
                            </div>
                        ):(
                            <div className="text-slate-950">
                            <span className="inline-block w-2 h-2  rounded-full bg-rose-600 mr-1"/>
                            <span className="bg-rose-50 text-rose-700 mr-2 text-xs px-1.5 py-0.5 rounded">부족</span>
                            응급실 일반 병상: <span className="text-rose-600">{erInfo.er_count}</span>
                            </div>
                        )}

                        {erInfo.or_count >= 3 ? (
                            <div className="text-slate-950">
                            <span className="inline-block w-2 h-2  rounded-full bg-emerald-500 mr-1"/>
                            <span className="bg-emerald-50 text-emerald-700 mr-2 text-xs px-1.5 py-0.5 rounded">여유</span>
                            일반 수술실: <span className="text-slate-950">{erInfo.or_count}</span>
                            </div>
                        ): erInfo.or_count >=1 ? (
                            <div className="text-slate-950">
                            <span className="inline-block w-2 h-2  rounded-full bg-amber-600 mr-1"/>
                            <span className="bg-amber-50 text-amber-700 mr-2 text-xs px-1.5 py-0.5 rounded">주의</span>
                            일반 수술실: <span className="text-amber-600">{erInfo.or_count}</span>
                            </div>
                        ):(
                            <div className="text-slate-950">
                            <span className="inline-block w-2 h-2  rounded-full bg-rose-600 mr-1"/>
                            <span className="bg-rose-50 text-rose-700 mr-2 text-xs px-1.5 py-0.5 rounded">부족</span>
                            일반 수술실: <span className="text-rose-600">{erInfo.or_count}</span>
                            </div>
                        )}
                    </div>      
                    )}
            </div>

        </section>
        <section className="lg:col-span-5 xl:col-span-4 space-y-4">
            <div className="flex items-center justify-between pb-2">
                <div className="flex items-center gap-2">
                <h3 className="text-lg font-black text-slate-900 tracking-tight">최근 수락 환자</h3>
                <span className="w-5 h-5 rounded-full bg-slate-200 text-slate-700 text-xs font-bold flex items-center justify-center">
                    {acceptedPatients.length}
                </span>
            </div>
        </div>
            <div className="bg-white border border-slate-200/90 rounded-2xl p-4 shadow-xs">
                {acceptedPatients.length === 0 ? (
                <div className="py-12 px-4 text-center">
                    <div className="w-12 h-12 bg-slate-50 border border-slate-100 rounded-full flex items-center justify-center mx-auto mb-3 text-slate-300">
                    <UserCheck className="w-6 h-6 text-slate-400" />
                    </div>
                    <h4 className="text-sm font-bold text-slate-700">최근 수락된 환자가 없습니다.</h4>
                </div>
                ):(
                <div className="space-y-3">
                    {acceptedPatients.map((patient) => (
                    <div
                        key={patient.patientid}
                        className="bg-slate-50/70 border border-slate-200/70 rounded-xl p-4 hover:border-slate-300 transition"
                    >
                        <div className="flex items-start justify-between">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 bg-slate-200 text-slate-700 rounded-xl font-bold flex items-center justify-center text-sm border border-slate-300/60">
                            {(patient.name || '미').charAt(0)}
                            </div>
                            <div>
                            <div className="flex items-center gap-2">
                                <span className="font-extrabold text-slate-900 text-sm">{patient.name || '신원 미상'}</span>
                                <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-blue-100 text-blue-800">
                                {patient.severity} 
                                </span>
                            </div>
                            <p className="text-xs text-slate-500 mt-1">주 증상: {patient.symptom}</p>
                            <p className="text-xs text-slate-500 mt-1">수락 시간: {formatKoreaDateTime(patient.handled_at)}</p>
                            </div>
                        </div>

                        <div className="text-right shrink-0">
                            <span className="px-2 py-0.5 bg-emerald-100 text-emerald-800 text-[10px] font-bold rounded">
                            수락 완료
                            </span>
                            <div className="text-sm font-black text-slate-900 font-mono mt-1">
                            ETA: {patient.eta}
                            </div>
                        </div>
                        </div>
                    </div>
                    ))}
                </div>
                )}
            </div>                                    
        </section>
    </div>
    );
}

function RequestslistContent({
    requestsList 
})
{
    const [ currentPage, setCurrentPage ] = useState(1);
    const pageSize = 15;

    const totalPages = Math.ceil(requestsList.length / pageSize);
    const StartIndex = (currentPage -1) * pageSize
    const pageRequests = requestsList.slice(StartIndex, StartIndex + pageSize)
    return(
        <div className="max-w-7xl mx-auto space-y-4 animate-fade-in">
            <div className="flex items-center gap-3 pb-2">
                <h3 className="text-lg font-black text-slate-900 tracking-tight flex items-center gap-2">
                환자 처리 이력
                </h3>
                <span className="px-2.5 py-0.5 bg-slate-200 text-slate-700 text-xs font-bold rounded-full">
                총 {requestsList.length}건
                </span>
            </div>
            <div className="bg-white border border-slate-200/90 rounded-2xl shadow-xs overflow-hidden">
                {requestsList.length === 0 ? (
                <div className="py-24 text-center flex flex-col items-center">
                    <div className="w-16 h-16 bg-slate-50 border border-slate-100 rounded-full flex items-center justify-center mb-4 text-slate-300">
                        <FileText className="w-8 h-8 text-slate-400" />
                    </div>
                    <h4 className="text-base font-bold text-slate-700">조회된 환자 이력이 없습니다.</h4>
                    <p className="text-sm text-slate-400 mt-1">환자 수용 요청이 처리되면 이곳에 기록됩니다.</p>
                </div>
                ) : (
                <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse min-w-[800px]">
                        <thead>
                            <tr className="bg-slate-50 border-b border-slate-200">
                            <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">주 증상</th>
                            <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">이름</th>
                            <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">중증도</th>
                            <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">요청 일시</th>
                            <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">처리 일시</th>
                            <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider text-center">상태</th>
                            <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider text-center">거절 사유</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-200/80">
                            {pageRequests.map(patient => (
                            <tr key={patient.patientid} className="hover:bg-slate-50/50 transition">
                                <td className="px-6 py-4 text-sm text-slate-600 font-mono">{patient.symptom}</td>
                                <td className="px-6 py-4 text-sm font-extrabold text-slate-900">{patient.name || '신원 미상'}</td>
                                <td className="px-6 py-4">
                                    <span className="px-2.5 py-1 rounded bg-red-100 text-red-800 text-xs font-bold border border-red-200/50">
                                    {patient.severity}
                                    </span>
                                </td>
                                <td className="px-6 py-4 text-sm text-slate-500">
                                {patient.created_at ? new Date(patient.created_at).toLocaleString('ko-KR') : '-'}
                                </td>
                                <td className="px-6 py-4 text-sm text-slate-500">
                                {patient.created_at ? new Date(patient.handled_at).toLocaleString('ko-KR') : '-'}
                                </td>
                                <td className="px-6 py-4 text-center">
                                {patient.request_status === 'rejected' ? (
                                    <span className="px-3 py-1 bg-rose-100 text-rose-800 text-xs font-bold rounded-full border border-rose-200 shadow-2xs">
                                    수용 거절
                                    </span>
                                ) : (
                                    <span className="px-3 py-1 bg-emerald-100 text-emerald-800 text-xs font-bold rounded-full border border-emerald-200 shadow-2xs">
                                    수락 완료
                                    </span>
                                )}
                                </td>
                                <td className="px-6 py-4 text-center">
                                {patient.rejection_reason}
                                </td>
                            </tr>
                            ))}
                        </tbody>
                    </table>
                    <div className="flex justify-center items-center gap-3 p-4">
                        <button
                            onClick={()=> setCurrentPage((page) => Math.max(page -1,1))}
                            disabled={currentPage === 1}
                            className="px-4 py-2 rounded-lg border border-slate-300 bg-white
                            text-sm font-bold text-slate-700 shadow-sm transition
                            hover:bg-slate-50 hover:border-slate-400
                            disabled:cursor-not-allowed disabled:opacity-40">
                        이전
                        </button>

                        <span className="text-sm font-semibold text-slate-600">
                            <span className="text-blue-700">{currentPage} </span>{" / "} {totalPages || 1}</span>

                        <button
                            onClick={()=>
                                setCurrentPage((page) => Math.min(page + 1, totalPages))}
                                disabled={currentPage >= totalPages}
                                className="px-4 py-2 rounded-lg border border-blue-700 bg-blue-700
                                text-sm font-bold text-white shadow-sm transition
                                hover:bg-blue-800 hover:border-blue-800
                                disabled:cursor-not-allowed disabled:opacity-40">
                        다음
                        </button>
                    </div>
                </div>
                )}
            </div>
        </div>
    )
    
}

function ErstatusContent({
    erInfo
}){
    return(
        <div className="max-w-7xl mx-auto space-y-4 animate-fade-in">
            <div className="flex items-center gap-3 pb-2">
                <h3 className="text-lg font-black text-slate-900 tracking-tight flex items-center gap-2">
                병상 현황 <span className="px-2.5 py-0.5 bg-slate-200 text-slate-700 text-xs font-bold rounded-full"> 일반 응급 병상: {erInfo?.er1_count ?? "정보 없음"} 병상 </span>
                </h3>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                {erInfo.er_count >= 10 ? (
                    <div className="text-slate-950">
                    <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 mr-1"/>
                    <span className="bg-emerald-50 text-emerald-700 mr-2 text-xs px-1.5 py-0.5 rounded">여유</span>
                    응급실 일반 병상: <span className="text-slate-950">{erInfo.er_count}</span>
                    </div>
                ): erInfo.er_count >=4 ? (
                    <div className="text-slate-950">
                    <span className="inline-block w-2 h-2  rounded-full bg-amber-600 mr-1"/>
                    <span className="bg-amber-50 text-amber-700 mr-2 text-xs px-1.5 py-0.5 rounded">주의</span>
                    응급실 일반 병상: <span className="text-amber-600">{erInfo.er_count}</span>
                    </div>
                ):(
                    <div className="text-slate-950">
                    <span className="inline-block w-2 h-2  rounded-full bg-rose-600 mr-1"/>
                    <span className="bg-rose-50 text-rose-700 mr-2 text-xs px-1.5 py-0.5 rounded">부족</span>
                    응급실 일반 병상: <span className="text-rose-600">{erInfo.er_count}</span>
                    </div>
                )}
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                {erInfo.er1_count >= 10 ? (
                    <div className="text-slate-950">
                    <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 mr-1"/>
                    <span className="bg-emerald-50 text-emerald-700 mr-2 text-xs px-1.5 py-0.5 rounded">여유</span>
                    일반 병상: <span className="text-slate-950">{erInfo.er1_count}</span>
                    </div>
                ): erInfo.er1_count >=4 ? (
                    <div className="text-slate-950">
                    <span className="inline-block w-2 h-2  rounded-full bg-amber-600 mr-1"/>
                    <span className="bg-amber-50 text-amber-700 mr-2 text-xs px-1.5 py-0.5 rounded">주의</span>
                    일반 병상: <span className="text-amber-600">{erInfo.er1_count}</span>
                    </div>
                ):(
                    <div className="text-slate-950">
                    <span className="inline-block w-2 h-2  rounded-full bg-rose-600 mr-1"/>
                    <span className="bg-rose-50 text-rose-700 mr-2 text-xs px-1.5 py-0.5 rounded">부족</span>
                    일반 병상: <span className="text-rose-600">{erInfo.er1_count}</span>
                    </div>
                )}
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                {erInfo.er2_count >= 10 ? (
                    <div className="text-slate-950">
                    <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 mr-1"/>
                    <span className="bg-emerald-50 text-emerald-700 mr-2 text-xs px-1.5 py-0.5 rounded">여유</span>
                    소아 병상: <span className="text-slate-950">{erInfo.er2_count}</span>
                    </div>
                ): erInfo.er2_count >=4 ? (
                    <div className="text-slate-950">
                    <span className="inline-block w-2 h-2  rounded-full bg-amber-600 mr-1"/>
                    <span className="bg-amber-50 text-amber-700 mr-2 text-xs px-1.5 py-0.5 rounded">주의</span>
                    소아 병상: <span className="text-amber-600">{erInfo.er2_count}</span>
                    </div>
                ):(
                    <div className="text-slate-950">
                    <span className="inline-block w-2 h-2  rounded-full bg-rose-600 mr-1"/>
                    <span className="bg-rose-50 text-rose-700 mr-2 text-xs px-1.5 py-0.5 rounded">부족</span>
                    소아 병상: <span className="text-rose-600">{erInfo.er2_count}</span>
                    </div>
                )}
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                {erInfo.e3_count >= 10 ? (
                    <div className="text-slate-950">
                    <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 mr-1"/>
                    <span className="bg-emerald-50 text-emerald-700 mr-2 text-xs px-1.5 py-0.5 rounded">여유</span>
                    음압 격리 병상: <span className="text-slate-950">{erInfo.er3_count}</span>
                    </div>
                ): erInfo.er3_count >=4 ? (
                    <div className="text-slate-950">
                    <span className="inline-block w-2 h-2  rounded-full bg-amber-600 mr-1"/>
                    <span className="bg-amber-50 text-amber-700 mr-2 text-xs px-1.5 py-0.5 rounded">주의</span>
                    음압 격리 병상: <span className="text-amber-600">{erInfo.er3_count}</span>
                    </div>
                ):(
                    <div className="text-slate-950">
                    <span className="inline-block w-2 h-2  rounded-full bg-rose-600 mr-1"/>
                    <span className="bg-rose-50 text-rose-700 mr-2 text-xs px-1.5 py-0.5 rounded">부족</span>
                    음압 격리 병상: <span className="text-rose-600">{erInfo.er3_count}</span>
                    </div>
                )}
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                {erInfo.er4_count >= 10 ? (
                    <div className="text-slate-950">
                    <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 mr-1"/>
                    <span className="bg-emerald-50 text-emerald-700 mr-2 text-xs px-1.5 py-0.5 rounded">여유</span>
                    일반 격리 병상: <span className="text-slate-950">{erInfo.er4_count}</span>
                    </div>
                ): erInfo.er4_count >=4 ? (
                    <div className="text-slate-950">
                    <span className="inline-block w-2 h-2  rounded-full bg-amber-600 mr-1"/>
                    <span className="bg-amber-50 text-amber-700 mr-2 text-xs px-1.5 py-0.5 rounded">주의</span>
                    일반 격리 병상: <span className="text-amber-600">{erInfo.er4_count}</span>
                    </div>
                ):(
                    <div className="text-slate-950">
                    <span className="inline-block w-2 h-2  rounded-full bg-rose-600 mr-1"/>
                    <span className="bg-rose-50 text-rose-700 mr-2 text-xs px-1.5 py-0.5 rounded">부족</span>
                    음압 격리 병상: <span className="text-rose-600">{erInfo.er4_count}</span>
                    </div>
                )}
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                {erInfo.er5_count >= 10 ? (
                    <div className="text-slate-950">
                    <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 mr-1"/>
                    <span className="bg-emerald-50 text-emerald-700 mr-2 text-xs px-1.5 py-0.5 rounded">여유</span>
                    응급 전용 중환자실: <span className="text-slate-950">{erInfo.er5_count}</span>
                    </div>
                ): erInfo.er4_count >=5 ? (
                    <div className="text-slate-950">
                    <span className="inline-block w-2 h-2  rounded-full bg-amber-600 mr-1"/>
                    <span className="bg-amber-50 text-amber-700 mr-2 text-xs px-1.5 py-0.5 rounded">주의</span>
                    응급 전용 중환자실: <span className="text-amber-600">{erInfo.er5_count}</span>
                    </div>
                ):(
                    <div className="text-slate-950">
                    <span className="inline-block w-2 h-2  rounded-full bg-rose-600 mr-1"/>
                    <span className="bg-rose-50 text-rose-700 mr-2 text-xs px-1.5 py-0.5 rounded">부족</span>
                    응급 전용 중환자실: <span className="text-rose-600">{erInfo.er5_count}</span>
                    </div>
                )}
            </div>
            <hr/>
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                {erInfo.or_count >= 4 ? (
                    <div className="text-slate-950">
                    <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 mr-1"/>
                    <span className="bg-emerald-50 text-emerald-700 mr-2 text-xs px-1.5 py-0.5 rounded">여유</span>
                    일반 수술실: <span className="text-slate-950">{erInfo.or_count}</span>
                    </div>
                ): erInfo.or_count >=2 ? (
                    <div className="text-slate-950">
                    <span className="inline-block w-2 h-2  rounded-full bg-amber-600 mr-1"/>
                    <span className="bg-amber-50 text-amber-700 mr-2 text-xs px-1.5 py-0.5 rounded">주의</span>
                    일반 수술실: <span className="text-amber-600">{erInfo.or_count}</span>
                    </div>
                ):(
                    <div className="text-slate-950">
                    <span className="inline-block w-2 h-2  rounded-full bg-rose-600 mr-1"/>
                    <span className="bg-rose-50 text-rose-700 mr-2 text-xs px-1.5 py-0.5 rounded">부족</span>
                    일반 수술실: <span className="text-rose-600">{erInfo.or_count}</span>
                    </div>
                )}
            </div>
        </div>
    )
}

function EquipmentContent({
    equipmentInfo
}){
    return(
        <div className="max-w-7xl mx-auto space-y-4 animate-fade-in">
            <div className="flex items-center gap-3 pb-2">
                <h3 className="text-lg font-black text-slate-900 tracking-tight flex items-center gap-2">
                의료 장비 현황 <span className="px-2.5 py-0.5 bg-slate-200 text-slate-700 text-xs font-bold rounded-full"> 장비 현황 </span>
                </h3>       
            </div>

            <div className="grid grid-cols-2 gap-4">
                {Object.entries(equipmentInfo).map(([imagecode, enabled]) => {
                if (!enabled) return null;

                const image = equipmentImages[imagecode];

                return(
                    <div key={imagecode} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                        <img src={image} alt={imagecode} className="h-40 w-full object-contain"/>
                        <p className="mt-2 font-bold">{imagecode.toUpperCase()}<span className="text-xs text-slate-500"> 장비 보유중</span></p>
                    </div>
                );
                })}
            </div>
        </div>
    )
}

function StatsContent({
    statsInfo
}){
    return(
        <div className="max-w-7xl mx-auto space-y-4 animate-fade-in">
            <div className="flex items-center gap-3 pb-2">
                <h3 className="text-lg font-black text-slate-900 tracking-tight flex items-center gap-2">
                통계 <span className="px-2.5 py-0.5 bg-slate-200 text-slate-700 text-xs font-bold rounded-full"> 병원 정보 통계 </span>
                </h3>       
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4"><span className="text-slate-950 text-lg font-bold mb-4 block"> 증상 통계 </span>
            {Object.entries(statsInfo.symptom_count ?? {}).sort((a, b) => b[1] - a[1]).map(([symptom, count]) => (
                <div key={symptom} className="mb-3">
                    <div className="mb-1 flex justify-between text-sm">
                        <span>{symptom}</span>
                        <span>{count}건</span>
                    </div>

                    <div className="h-2 rounded-full bg-slate-100">
                        <div
                            className="h-2 rounded-full bg-blue-600"
                            style={{
                            width: `${Math.min(
                                100,
                                (count / Math.max(...Object.values(statsInfo?.symptom_count ?? {}))) * 100
                            )}%`,
                            }}
                        />
                        </div>
                    </div>
            ))}
            </div>
            <div className="rounded-xl border border-slate-300 shadow-sm flex items-center gap-3 px-2.5 py-2.5">
                <div className="rounded-xl border border-white bg-slate-200 shadow-sm px-1 py-1">전체: {statsInfo?.total_count} 건</div>
                <div className="rounded-xl border border-white bg-blue-200 shadow-sm px-1 py-1">수락: {statsInfo?.accepted_count} 건</div>
                <div className="rounded-xl border border-white bg-rose-200 shadow-sm px-1 py-1">거절: {statsInfo?.rejected_count} 건</div>
                <div className="rounded-xl border border-white bg-slate-100 shadow-sm px-1 py-1">대기: {(statsInfo?.total_count)-(statsInfo?.accepted_count)+(statsInfo?.rejected_count)} 건</div>
            </div>
            <div className="rounded-xl border border-white shadow-sm px-2 py-2">평균 응답 시간: {parseInt(statsInfo?.average_seconds)} 초</div>
            
        </div>
    )
}