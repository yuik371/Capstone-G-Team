import React, { useState, useEffect } from 'react';
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
  MapPin
} from 'lucide-react';

const getEnvVar = (key, fallback = '') => {
  try {
    if (typeof process !== 'undefined' && process.env && process.env[key]) {
      return process.env[key];
    }
    if (typeof window !== 'undefined' && window.__ENV__ && window.__ENV__[key]) {
      return window.__ENV__[key];
    }
  } catch (e) {
  }
  return fallback;
};

const API_BASE_URL = getEnvVar('VITE_API_BASE_URL', 'http://localhost:8080');

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');

  const [hospital, setHospital] = useState({
    hospitalid: null,
    userid: '',
    name: '병원 정보 연동 대기',
    er_status: 'OFF',
    or_status: 'OFF'
  });

  const [pendingPatients, setPendingPatients] = useState([]);
  const [acceptedPatients, setAcceptedPatients] = useState([]);
  const [historyPatients, setHistoryPatients] = useState([]);

  const [currentTime, setCurrentTime] = useState(new Date());
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [selectedImageModal, setSelectedImageModal] = useState(null);

  const [mapModalData, setMapModalData] = useState(null);
  const [isMapLoading, setIsMapLoading] = useState(false);

  const [rejectModalPatient, setRejectModalPatient] = useState(null);
  const [rejectReason, setRejectReason] = useState('응급실 병상 포화');
  const [customRejectReason, setCustomRejectReason] = useState('');

  const REJECT_REASONS = [
    '응급실 병상 포화',
    '수술실 가용 불가 (집도 중)',
    '중환자실(ICU) 병상 부족',
    '해당 진료과 전문의 부재',
    '필수 의료장비·시설 가동 불가',
    '격리 병상 부족 (감염 의심)',
    '기타'
  ];

  const getAuthHeaders = () => {
    const token = localStorage.getItem('accessToken') || getEnvVar('VITE_API_TOKEN', '');
    return {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    };
  };

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    const headers = getAuthHeaders();

    try {
      const [statusRes, reqRes, accRes, listRes] = await Promise.allSettled([
        fetch(`${API_BASE_URL}/hospital/topstatus`, { headers }),
        fetch(`${API_BASE_URL}/hospital/requests`, { headers }),
        fetch(`${API_BASE_URL}/hospital/accepted`, { headers }),
        fetch(`${API_BASE_URL}/hospital/requestlist`, { headers })
      ]);

      if (statusRes.status === 'fulfilled' && statusRes.value.ok) {
        const statusData = await statusRes.value.json();
        setHospital(prev => ({ ...prev, ...statusData }));
      }

      if (reqRes.status === 'fulfilled' && reqRes.value.ok) {
        const reqData = await reqRes.value.json();
        setPendingPatients(Array.isArray(reqData) ? reqData : reqData.data || []);
      }

      if (accRes.status === 'fulfilled' && accRes.value.ok) {
        const accData = await accRes.value.json();
        setAcceptedPatients(Array.isArray(accData) ? accData : accData.data || []);
      }

      if (listRes.status === 'fulfilled' && listRes.value.ok) {
        const listData = await listRes.value.json();
        setHistoryPatients(Array.isArray(listData) ? listData : listData.data || []);
      }
    } catch (error) {
      console.error('대시보드 데이터 조회 실패:', error);
    } finally {
      setTimeout(() => {
        setIsRefreshing(false);
      }, 400);
    }
  };

  useEffect(() => {
    handleRefresh();
  }, []);

  useEffect(() => {
    const token = localStorage.getItem('accessToken') || getEnvVar('VITE_API_TOKEN', '');
    const sseUrl = token
      ? `${API_BASE_URL}/hospital/sse?token=${encodeURIComponent(token)}`
      : `${API_BASE_URL}/hospital/sse`;

    const eventSource = new EventSource(sseUrl, { withCredentials: true });

    eventSource.onmessage = (event) => {
      try {
        const incomingPatient = JSON.parse(event.data);
        if (incomingPatient && incomingPatient.patientid) {
          setPendingPatients(prev => {
            const exists = prev.some(p => p.patientid === incomingPatient.patientid);
            return exists ? prev : [incomingPatient, ...prev];
          });
        }
      } catch (err) {
        console.log('SSE 메시지 수신:', event.data);
      }
    };

    eventSource.onerror = (err) => {
      console.warn('SSE 연결 상태 확인 필요:', err);
    };

    return () => {
      eventSource.close();
    };
  }, []);

  const handleOpenHospitalMap = async () => {
    setIsMapLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/hospital/map`, {
        headers: getAuthHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        setMapModalData(data);
      } else {
        setMapModalData({ error: '병원 위치 정보를 불러오지 못했습니다. (인증 토큰 확인 필요)' });
      }
    } catch (error) {
      setMapModalData({ error: '서버와 연결할 수 없습니다.' });
    } finally {
      setIsMapLoading(false);
    }
  };

  const toggleErStatus = async () => {
    const nextStatus = hospital.er_status === 'ON' ? 'OFF' : 'ON';
    setHospital(prev => ({ ...prev, er_status: nextStatus }));
  };

  const toggleOrStatus = async () => {
    const nextStatus = hospital.or_status === 'ON' ? 'OFF' : 'ON';
    setHospital(prev => ({ ...prev, or_status: nextStatus }));
  };

  const handleAcceptRequest = async (patient) => {
    const targetId = patient.patientid || patient._id;
    try {
      await fetch(`${API_BASE_URL}/hospital/requests/${targetId}/decision`, {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          decision: 'ACCEPTED'
        })
      });

      const updatedPatient = {
        ...patient,
        request_status: 'ACCEPTED',
        handled_at: new Date().toISOString()
      };

      setPendingPatients(prev => prev.filter(p => (p.patientid || p._id) !== targetId));
      setAcceptedPatients(prev => [updatedPatient, ...prev]);
      setHistoryPatients(prev => [updatedPatient, ...prev]);
    } catch (error) {
      console.error('환자 수락 처리 실패:', error);
    }
  };

  const openRejectModal = (patient) => {
    setRejectModalPatient(patient);
    setRejectReason(REJECT_REASONS[0]);
    setCustomRejectReason('');
  };

  const confirmRejectRequest = async () => {
    if (!rejectModalPatient) return;

    const targetId = rejectModalPatient.patientid || rejectModalPatient._id;
    const finalReason = rejectReason === '기타'
      ? customRejectReason.trim() || '기타 사유 (상세 미입력)'
      : rejectReason;

    try {
      await fetch(`${API_BASE_URL}/hospital/requests/${targetId}/decision`, {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          decision: 'REJECTED',
          reason: finalReason
        })
      });

      setPendingPatients(prev => prev.filter(p => (p.patientid || p._id) !== targetId));
      setHistoryPatients(prev => [
        {
          ...rejectModalPatient,
          request_status: 'REJECTED',
          reject_reason: finalReason,
          handled_at: new Date().toISOString()
        },
        ...prev
      ]);
    } catch (error) {
      console.error('환자 거절 처리 실패:', error);
    } finally {
      setRejectModalPatient(null);
      setCustomRejectReason('');
    }
  };

  const formattedDateStr = currentTime.toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }) + ' ' + currentTime.toLocaleTimeString('ko-KR', { hour12: true });

  return (
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
              ID: {hospital.userid || '-'}
            </div>
            <div className="mt-3 space-y-2">
              <button
                onClick={handleOpenHospitalMap}
                disabled={isMapLoading}
                className="w-full py-1.5 px-3 bg-sky-500/15 hover:bg-sky-500/25 text-sky-300 hover:text-sky-200 text-xs font-semibold rounded-lg transition flex items-center justify-center gap-1.5 border border-sky-500/30"
              >
                <MapPin className="w-3.5 h-3.5 text-sky-400" />
                {isMapLoading ? '위치 조회 중...' : '병원 위치 조회 (지도)'}
              </button>

              <button
                onClick={() => {
                  localStorage.removeItem('accessToken');
                  console.log('로그아웃 처리');
                }}
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
              onClick={() => setActiveTab('history')}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition ${
                activeTab === 'history'
                  ? 'bg-blue-600/90 text-white shadow-lg shadow-blue-900/30'
                  : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200'
              }`}
            >
              <FileText className="w-5 h-5" />
              수락 내역 관리
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
                    {hospital.name || '병원 미연동'}
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
                <button
                  onClick={toggleErStatus}
                  className={`px-3 py-1 text-xs font-extrabold rounded-md transition flex items-center gap-1 whitespace-nowrap ${
                    hospital.er_status === 'ON'
                      ? 'bg-emerald-500 text-white shadow-sm hover:bg-emerald-600'
                      : 'bg-slate-300 text-slate-600 hover:bg-slate-400'
                  }`}
                >
                  {hospital.er_status}
                </button>
              </div>

              <div className="flex items-center gap-2 px-3 py-1.5 bg-white rounded-lg border border-slate-200 shadow-sm shrink-0">
                <span className="text-xs font-bold text-slate-700 whitespace-nowrap">수술실</span>
                <button
                  onClick={toggleOrStatus}
                  className={`px-3 py-1 text-xs font-extrabold rounded-md transition flex items-center gap-1 whitespace-nowrap ${
                    hospital.or_status === 'ON'
                      ? 'bg-emerald-500 text-white shadow-sm hover:bg-emerald-600'
                      : 'bg-slate-300 text-slate-600 hover:bg-slate-400'
                  }`}
                >
                  {hospital.or_status}
                </button>
              </div>
            </div>

            <button
              onClick={handleRefresh}
              className={`px-4 py-2.5 bg-white border border-slate-200 rounded-xl hover:bg-slate-50 text-slate-700 transition shadow-sm flex items-center gap-2 text-xs font-bold shrink-0 whitespace-nowrap ${
                isRefreshing ? 'opacity-70 cursor-not-allowed' : ''
              }`}
              title="데이터 새로고침"
            >
              <RefreshCw className={`w-4 h-4 text-slate-600 ${isRefreshing ? 'animate-spin text-blue-600' : ''}`} />
              <span>새로고침</span>
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-8 bg-[#F8FAFC]">
          {activeTab === 'dashboard' ? (
            <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            <section className="lg:col-span-7 xl:col-span-8 space-y-4">
              <div className="flex items-center justify-between pb-2">
                <div className="flex items-center gap-3">
                  <h3 className="text-lg font-black text-slate-900 tracking-tight flex items-center gap-2">
                    응급실 환자 수용 요청
                  </h3>
                  <span className="w-6 h-6 rounded-full bg-red-600 text-white text-xs font-black flex items-center justify-center shadow-xs">
                    {pendingPatients.length}
                  </span>
                </div>
              </div>

              {pendingPatients.length === 0 ? (
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
                  {pendingPatients.map((patient) => (
                    <div
                      key={patient.patientid || patient._id}
                      className="bg-white rounded-2xl border border-slate-200/90 shadow-md hover:shadow-lg transition overflow-hidden border-l-4 border-l-red-600"
                    >
                      <div className="p-6">
                        <div className="flex flex-col md:flex-row gap-6">
                          <div className="w-full md:w-44 h-44 bg-slate-100 rounded-xl border border-slate-200 relative overflow-hidden shrink-0 flex flex-col justify-center items-center group">
                            {patient.image ? (
                              <>
                                <img
                                  src={patient.image}
                                  alt="외상 사진"
                                  className="w-full h-full object-cover group-hover:scale-105 transition duration-300"
                                />
                                <div className="absolute inset-0 bg-black/30 opacity-0 group-hover:opacity-100 transition flex items-center justify-center">
                                  <button
                                    onClick={() => setSelectedImageModal(patient.image)}
                                    className="px-3 py-1.5 bg-white/90 backdrop-blur-xs text-slate-900 rounded-lg text-xs font-bold flex items-center gap-1.5 shadow-lg"
                                  >
                                    <Eye className="w-3.5 h-3.5" /> 크게 보기
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
                                <span className="text-xs text-slate-400 font-medium">외상 사진 없음</span>
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
                                  <span className="text-xs text-slate-400 font-mono">환자번호: {patient.patientid}</span>
                                </div>
                                <span className="text-xs text-slate-400 flex items-center gap-1 font-medium">
                                  <Clock className="w-3.5 h-3.5" />
                                  접수: {new Date(patient.created_at).toLocaleTimeString('ko-KR')}
                                </span>
                              </div>

                              <h4 className="text-xl font-extrabold text-slate-900 tracking-tight">
                                {patient.name || '신원 미상'}
                              </h4>
                              
                              <div className="mt-3 p-3 bg-slate-50 border border-slate-100 rounded-xl text-xs text-slate-700">
                                <div className="flex items-center gap-2 mb-1">
                                  <Ambulance className="w-4 h-4 text-slate-500" />
                                  <span className="font-semibold">구급차 ID:</span> {patient.ambid}
                                </div>
                              </div>
                            </div>

                            <div className="mt-5 pt-4 border-t border-slate-100 flex items-center justify-between">
                              <div className="flex items-center gap-3">
                                <div className="text-left">
                                  <div className="text-[11px] text-slate-400">예상 도착 (ETA)</div>
                                  <div className="text-xs font-bold text-slate-800">
                                    <span className="text-blue-600 font-extrabold text-sm">{patient.eta}</span>
                                  </div>
                                </div>
                              </div>

                              <div className="flex items-center gap-3">
                                <button
                                  onClick={() => openRejectModal(patient)}
                                  className="px-5 py-2.5 bg-white border border-slate-300 hover:bg-red-50 hover:border-red-300 text-red-600 font-bold text-sm rounded-xl transition shadow-2xs"
                                >
                                  거절
                                </button>
                                <button
                                  onClick={() => handleAcceptRequest(patient)}
                                  className="px-6 py-2.5 bg-blue-700 hover:bg-blue-800 text-white font-extrabold text-sm rounded-xl transition shadow-md shadow-blue-900/20 active:scale-95"
                                >
                                  수락
                                </button>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
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
                ) : (
                  <div className="space-y-3">
                    {acceptedPatients.map((patient) => (
                      <div
                        key={patient.patientid || patient._id}
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
                              <p className="text-xs text-slate-500 mt-1">ID: {patient.patientid}</p>
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
          ) : (
            <div className="max-w-7xl mx-auto space-y-4 animate-fade-in">
              <div className="flex items-center gap-3 pb-2">
                <h3 className="text-lg font-black text-slate-900 tracking-tight flex items-center gap-2">
                  최근 환자 이력 관리
                </h3>
                <span className="px-2.5 py-0.5 bg-slate-200 text-slate-700 text-xs font-bold rounded-full">
                  총 {historyPatients.length}건
                </span>
              </div>
              
              <div className="bg-white border border-slate-200/90 rounded-2xl shadow-xs overflow-hidden">
                {historyPatients.length === 0 ? (
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
                          <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">환자번호</th>
                          <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">이름</th>
                          <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">중증도</th>
                          <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">요청 일시</th>
                          <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">처리 일시</th>
                          <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider text-center">상태</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-200/80">
                        {historyPatients.map(patient => (
                          <tr key={patient.patientid || patient._id} className="hover:bg-slate-50/50 transition">
                            <td className="px-6 py-4 text-sm text-slate-600 font-mono">{patient.patientid}</td>
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
                              {patient.handled_at ? new Date(patient.handled_at).toLocaleString('ko-KR') : '-'}
                            </td>
                            <td className="px-6 py-4 text-center">
                              {patient.request_status === 'REJECTED' ? (
                                <span className="px-3 py-1 bg-rose-100 text-rose-800 text-xs font-bold rounded-full border border-rose-200 shadow-2xs" title={patient.reject_reason}>
                                  수용 거절
                                </span>
                              ) : (
                                <span className="px-3 py-1 bg-emerald-100 text-emerald-800 text-xs font-bold rounded-full border border-emerald-200 shadow-2xs">
                                  수락 완료
                                </span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
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
                <XCircle className="w-5 h-5 text-red-600" />
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
                onClick={confirmRejectRequest}
                disabled={rejectReason === '기타' && !customRejectReason.trim()}
                className="px-5 py-2 bg-red-600 hover:bg-red-700 disabled:bg-slate-300 disabled:cursor-not-allowed text-white font-extrabold text-xs rounded-xl transition shadow-sm"
              >
                거절 확정
              </button>
            </div>
          </div>
        </div>
      )}

      {mapModalData && (
        <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-fade-in">
          <div className="bg-white rounded-2xl max-w-lg w-full overflow-hidden shadow-2xl border border-slate-200">
            <div className="p-5 border-b border-slate-200 flex justify-between items-center bg-slate-50">
              <div className="flex items-center gap-2">
                <MapPin className="w-5 h-5 text-sky-600" />
                <h3 className="font-extrabold text-slate-900 text-base">병원 위치 정보</h3>
              </div>
              <button
                onClick={() => setMapModalData(null)}
                className="p-1 hover:bg-slate-200 rounded-lg text-slate-500 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              {mapModalData.error ? (
                <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-xs font-semibold text-rose-700">
                  {mapModalData.error}
                </div>
              ) : (
                <>
                  <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl text-xs space-y-1.5">
                    <div className="font-extrabold text-slate-900 text-sm">{mapModalData.name || hospital.name}</div>
                    {mapModalData.address && <div className="text-slate-600">주소: {mapModalData.address}</div>}
                    <div className="text-slate-500 font-mono">
                      좌표: 위도 {mapModalData.lat || mapModalData.latitude || '-'} / 경도 {mapModalData.lng || mapModalData.longitude || '-'}
                    </div>
                  </div>
                  <div
                    id="kakao-hospital-map"
                    className="w-full h-64 bg-slate-100 rounded-xl border border-slate-200 flex items-center justify-center text-xs text-slate-400"
                  >
                    {window.kakao && window.kakao.maps
                      ? '지도 렌더링 영역'
                      : 'index.html에 Kakao Maps SDK 스크립트를 연결하면 지도가 표시됩니다.'}
                  </div>
                </>
              )}
            </div>

            <div className="px-6 py-4 bg-slate-50 border-t border-slate-200 flex justify-end">
              <button
                onClick={() => setMapModalData(null)}
                className="px-5 py-2 bg-slate-800 hover:bg-slate-700 text-white font-bold text-xs rounded-xl transition"
              >
                닫기
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}