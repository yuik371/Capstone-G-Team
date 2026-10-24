import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './hospital.css';

export default function Hospital() {
    const navigate = useNavigate();
    
    const [hospital, setHospital] = useState({ er_status: true, or_status: true }); 
    const [message, setMessage] = useState("병원 정보 불러오는 중");
    const [currentTime, setCurrentTime] = useState(new Date().toLocaleString('ko-KR'));

    const [request, setRequest] = useState([
        {
            _id: 'REQ-104',
            severity: 'KTAS 1',
            severityLabel: '소생',
            name: '신원 미상',
            age: 67,
            gender: '남',
            location: '중구 119-2 (중구 을지로)',
            symptom: '두부 외상 · 의식 저하',
            description: '보행 중 차량 충돌. GCS 9, 경추 보호대 적용. 전두부 열상, 동공 반응 느림.',
            vitals: { bp: '162/94', hr: 58, spo2: '90%', rr: 10 },
            departments: ['신경외과', '응급의학과', '외상외과'],
            eta: '6분',
            etaTime: '23:54 경',
            requestTime: '50초 전',
            image: 'https://via.placeholder.com/120x90?text=Trauma'
        }
    ]);

    const [acceptedPatients, setAcceptedPatients] = useState([
        {
            _id: 'REQ-101',
            severity: 'KTAS 2',
            severityLabel: '긴급',
            name: '오태양',
            symptom: '낙상 - 좌측 하지 골절 의심',
            location: '성북 119-1',
            etaTime: '02:50',
            etaAbsolute: '23:51',
            image: 'https://via.placeholder.com/80x60?text=Trauma'
        }
    ]);

    useEffect(() => {
        async function HospitalData() {
            const token = sessionStorage.getItem("access_token");

            if (!token) {
                navigate("/login");
                return;
            }

            const headers = { Authorization: `Bearer ${token}` };

            try {
                const hospitalTopstatus = await fetch("http://127.0.0.1:8000/hospital/topstatus", { headers });
                const hospitalRequests = await fetch("http://127.0.0.1:8000/hospital/requests", { headers });

                const topstatusData = await hospitalTopstatus.json();
                const requestsData = await hospitalRequests.json();

                if (!hospitalTopstatus.ok) {
                    throw new Error(topstatusData.detail || "병원 정보 오류");
                }
                if (!hospitalRequests.ok) {
                    throw new Error(requestsData.detail || "환자 요청 정보 오류");
                }

                setHospital(topstatusData);
                
                if (Array.isArray(requestsData) && requestsData.length > 0) {
                    setRequest(requestsData); 
                }
                setMessage("");
                
            } catch (error) {
                setMessage(error.message);
                console.error("API 연동 에러:", error.message);
            }
        }
        HospitalData();
    }, [navigate]);

    useEffect(() => {
        const timer = setInterval(() => {
            setCurrentTime(new Date().toLocaleString('ko-KR'));
        }, 1000);
        return () => clearInterval(timer);
    }, []);

    function logout() {
        sessionStorage.removeItem("access_token");
        navigate("/login");
    }

    const handleStatusToggle = (type) => {
        setHospital(prev => ({ ...prev, [type === 'er' ? 'er_status' : 'or_status']: !prev[type === 'er' ? 'er_status' : 'or_status'] }));
    };

    const handleDecision = (id, decision) => {
        if (decision === 'accept') {
            alert(`${id} 요청을 수락했습니다.`);
        } else {
            alert(`${id} 요청을 거절했습니다.`);
        }
        setRequest(prev => prev.filter(req => req._id !== id));
    };

    const getKtasColor = (ktas) => {
        if (!ktas) return 'bg-gray-500 text-white';
        if (ktas.includes('1')) return 'bg-red-600 text-white';
        if (ktas.includes('2')) return 'bg-orange-500 text-white';
        if (ktas.includes('3')) return 'bg-yellow-400 text-gray-800';
        return 'bg-green-500 text-white';
    };

    return (
    <div className="min-h-screen bg-[#f1f5f9] p-6 font-sans">
      {/* 1. 상단 GNB 헤더 (한 줄 정렬 및 깔끔한 간격) */}
      {/* 슬림형 한 줄 상단 GNB 헤더 */}
      <header className="flex items-center justify-between bg-white px-6 py-2.5 rounded-xl shadow-xs mb-5 border border-gray-200/60 whitespace-nowrap">
        {/* 왼쪽: 로고 & 타이틀 */}
        <div className="flex items-center gap-3">
          <div className="bg-[#dc2626] text-white rounded-lg font-bold text-lg flex items-center justify-center w-8 h-8 shadow-xs flex-shrink-0">+</div>
          <div className="flex items-center gap-2">
            <h1 className="text-base font-extrabold text-gray-900 tracking-tight">{hospital.name || "서울중앙의료원"}</h1>
            <span className="text-xs text-gray-400 font-normal">|</span>
            <p className="text-xs text-gray-400 font-medium">지역응급의료센터 - 환자 수용 관제</p>
          </div>
        </div>

        {/* 오른쪽: 시간 & 상태 스위치 & 유저 정보 */}
        <div className="flex items-center gap-6">
          <div className="text-xs font-semibold text-gray-400">{currentTime}</div>
          
          {/* 응급실/수술실 토글 스위치 (슬림형) */}
          <div className="flex items-center gap-2 bg-gray-100/70 px-3 py-1 rounded-full border border-gray-200/50 text-xs">
            <span className="font-bold text-gray-700">응급실</span>
            <button className={`px-2 py-0.5 text-[10px] font-bold rounded-full text-white ${hospital.er_status ? 'bg-[#10b981]' : 'bg-gray-400'}`}>
              {hospital.er_status ? 'ON' : 'OFF'}
            </button>
            <span className="font-bold text-gray-700 ml-1.5">수술실</span>
            <button className={`px-2 py-0.5 text-[10px] font-bold rounded-full text-white ${hospital.or_status ? 'bg-[#10b981]' : 'bg-gray-400'}`}>
              {hospital.or_status ? 'ON' : 'OFF'}
            </button>
          </div>

          <div className="flex items-center gap-2 text-xs text-gray-500 font-medium">
            <span>SN30112 · 응급의학과 의사</span>
            <button onClick={() => navigate('/login')} className="font-bold text-gray-800 hover:text-red-600 underline ml-1">
              로그아웃
            </button>
          </div>
        </div>
      </header>

      {/* 2. 메인 2열 그리드 레이아웃 */}
      <div className="grid grid-cols-12 gap-6">
        
        {/* [좌측] 응급실 환자 수용 요청 리스트 */}
        <div className="col-span-7 space-y-4">
          <div className="flex items-center justify-between px-1">
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-gray-900">응급실 환자 수용 요청</h2>
              <span className="bg-[#dc2626] text-white text-xs font-bold px-2 py-0.5 rounded-full">{request.length}</span>
            </div>
            <span className="text-xs text-gray-400 font-medium">중증도(KTAS) 순 정렬</span>
          </div>

          {request.map((item) => (
            <div key={item._id} className="bg-white rounded-2xl p-5 border border-gray-200/80 shadow-sm relative overflow-hidden flex gap-4">
              {/* 왼쪽 인디케이터 라인 */}
              <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-[#dc2626]"></div>

              {/* 환자 이미지 */}
              <div className="w-36 h-36 bg-gray-200 rounded-xl overflow-hidden flex-shrink-0 relative border border-gray-100">
                <img src="/api/placeholder/150/150" alt="외상 사진" className="w-full h-full object-cover" />
                <span className="absolute bottom-1 left-1 right-1 text-center bg-black/60 backdrop-blur-xs text-white text-[10px] py-0.5 rounded-md font-medium">외상 사진</span>
              </div>

              {/* 환자 정보 */}
              <div className="flex-1 space-y-2">
                <div className="flex items-center gap-2">
                  <span className="bg-[#dc2626] text-white text-xs font-bold px-2 py-0.5 rounded-md">{item.severity || "KTAS 1 · 소생"}</span>
                  <span className="text-xs font-bold text-gray-400">{item._id}</span>
                  <span className="text-xs text-gray-400 font-medium ml-auto">50초 전</span>
                </div>

                <h3 className="text-base font-bold text-gray-900">{item.symptom || "두부 외상 · 의식 저하"}</h3>
                <p className="text-xs text-gray-400">{item.name} · {item.age}세 · {item.gender} · {item.location}</p>
                <p className="text-xs text-gray-600 bg-gray-50/80 p-2.5 rounded-lg border border-gray-100/80 leading-relaxed">
                  보행 중 차량 충돌. GCS 9, 경추 보호대 적용. 전두부 열상, 동공 반응 느림.
                </p>

                {/* 바이탈 수치 박스 */}
                <div className="grid grid-cols-4 gap-2 text-center bg-gray-50/80 p-2 rounded-lg border border-gray-100/80 text-xs">
                  <div><span className="block text-[10px] text-gray-400 mb-0.5">혈압</span><strong className="text-[#dc2626] font-bold">162/94</strong></div>
                  <div><span className="block text-[10px] text-gray-400 mb-0.5">맥박</span><strong className="text-gray-700 font-bold">58</strong></div>
                  <div><span className="block text-[10px] text-gray-400 mb-0.5">SpO2</span><strong className="text-[#dc2626] font-bold">90%</strong></div>
                  <div><span className="block text-[10px] text-gray-400 mb-0.5">호흡</span><strong className="text-gray-700 font-bold">10</strong></div>
                </div>

                {/* 하단 진료과 & 거절/수락 버튼 */}
                <div className="flex items-center justify-between pt-1">
                  <div className="flex gap-1.5 text-[11px] items-center">
                    <span className="text-gray-400 font-medium">필요 진료과</span>
                    <span className="bg-blue-50 text-blue-600 font-bold px-2 py-0.5 rounded-md border border-blue-100">신경외과</span>
                    <span className="bg-blue-50 text-blue-600 font-bold px-2 py-0.5 rounded-md border border-blue-100">응급의학과</span>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-400 mr-1">예상 도착 <strong className="text-gray-800 font-bold">6분</strong> <span className="text-[10px] text-gray-400">(23:54 경)</span></span>
                    <button className="px-3.5 py-1.5 text-xs font-bold text-red-500 bg-white border border-gray-200 hover:bg-gray-50 rounded-lg shadow-2xs">거절</button>
                    <button className="px-4 py-1.5 text-xs font-bold text-white bg-[#1e40af] hover:bg-blue-900 rounded-lg shadow-sm">수락</button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* [우측] 지도 영역 및 최근 수락 환자 */}
        <div className="col-span-5 space-y-6">
          <div className="bg-white rounded-2xl p-5 border border-gray-200/80 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-gray-900">수락된 구급차 현재 위치</h3>
              <span className="text-xs text-blue-500 font-semibold">실시간 추적</span>
            </div>
            <div className="w-full h-72 bg-slate-100 rounded-xl relative overflow-hidden flex items-center justify-center border border-gray-200">
              <p className="text-xs font-bold text-gray-500 z-10 bg-white/90 backdrop-blur-xs px-4 py-2 rounded-full shadow-sm border border-gray-200">📍 지도 (OpenStreetMap / Leaflet 로딩 영역)</p>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}