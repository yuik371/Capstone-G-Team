import React, { useState, useEffect } from 'react';
import { 
  Plus, 
  LayoutDashboard, 
  Clock, 
  UserPlus, 
  Users, 
  RotateCcw, 
  AlertCircle, 
  X, 
  ShieldAlert, 
  LogOut, 
  Check, 
  Building2, 
  Activity,
  Maximize2,
  FileText,
  HeartPulse
} from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  
  // 상태 관리
  const [hospital, setHospital] = useState(null);
  const [patients, setPatients] = useState([]);
  
  const [currentTime, setCurrentTime] = useState(new Date());
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [selectedImageModal, setSelectedImageModal] = useState(null);
  const [isTestMode, setIsTestMode] = useState(false);

  // 실시간 타이머
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // 새로고침 시뮬레이션
  const handleRefresh = () => {
    if (!hospital) return;
    setIsRefreshing(true);
    setTimeout(() => setIsRefreshing(false), 600);
  };

  // 응급실/수술실 토글
  const toggleErStatus = () => {
    if (!hospital) return;
    setHospital(prev => ({ ...prev, er_status: prev.er_status === 'ON' ? 'OFF' : 'ON' }));
  };

  const toggleOrStatus = () => {
    if (!hospital) return;
    setHospital(prev => ({ ...prev, or_status: prev.or_status === 'ON' ? 'OFF' : 'ON' }));
  };

  // 수락 및 거절 처리
  const handleAcceptRequest = (patientId) => {
    const now = new Date().toISOString();
    setPatients(patients.map(p => 
      p._id === patientId ? { ...p, request_status: 'ACCEPTED', handled_at: now } : p
    ));
  };

  const handleRejectRequest = (patientId) => {
    const now = new Date().toISOString();
    setPatients(patients.map(p => 
      p._id === patientId ? { ...p, request_status: 'REJECTED', handled_at: now } : p
    ));
  };

  // 더미 데이터 생성 (실제 의료/외상 사진 반영)
  const toggleTestMode = () => {
    if (isTestMode) {
      setHospital(null);
      setPatients([]);
      setIsTestMode(false);
    } else {
      setHospital({
        _id: 'mock_hospital_id',
        hospitalid: 1,
        name: '서울대학교병원 (응급의료센터)',
        er_status: 'ON',
        or_status: 'ON',
        userid: 'admin_sn30112',
        created_at: new Date().toISOString()
      });

      setPatients([
        {
          _id: 'mock_patient_1',
          patientid: 'REQ-104',
          hospitalid: 1,
          name: '신원 미상 · 67세 · 남',
          severity: 'KTAS 1',
          eta: '6분',
          // 두부 외상 CT 단층 촬영 사진
          image: 'https://images.unsplash.com/photo-1516549655169-df83a0774514?auto=format&fit=crop&w=800&q=80', 
          imageTitle: '두부 외상 (Head Trauma) CT Scan',
          request_status: 'PENDING',
          ambid: '중구 119-2',
          created_at: new Date().toISOString(),
          handled_at: null,
          details: '보행 중 덤프트럭 충돌. GCS 9점, 경추 보호대 적용. 전두부 수직 열상(12cm) 및 함몰 골절, 동공 반응 느림.',
          vitals: { bp: '162/94', hr: '58', spo2: '90', rr: '10' }
        },
        {
          _id: 'mock_patient_2',
          patientid: 'REQ-105',
          hospitalid: 1,
          name: '오태양 · 32세 · 남',
          severity: 'KTAS 2',
          eta: '12분',
          // 하퇴부 복합 골절 X-Ray 사진
          image: 'https://images.unsplash.com/photo-1530497610245-94d3c16cda28?auto=format&fit=crop&w=800&q=80',
          imageTitle: '하지 외상 (胫骨 Fractured Leg) X-Ray',
          request_status: 'PENDING',
          ambid: '성북 119-1',
          created_at: new Date(Date.now() - 10 * 60000).toISOString(),
          handled_at: null,
          details: '공사현장 3m 낙상. 좌측 하퇴부 개방성 복합 골절(Open Fracture), 출혈 심함. 부목 및 압박대 조치 완료.',
          vitals: { bp: '130/85', hr: '104', spo2: '97', rr: '22' }
        },
        {
          _id: 'mock_patient_3',
          patientid: 'REQ-106',
          hospitalid: 1,
          name: '김지연 · 45세 · 여',
          severity: 'KTAS 3',
          eta: '18분',
          // 흉부 손상 CT 사진
          image: 'https://images.unsplash.com/photo-1579684385127-1ef15d508118?auto=format&fit=crop&w=800&q=80',
          imageTitle: '흉부 외상 (Chest Trauma) 스캔 사진',
          request_status: 'ACCEPTED',
          ambid: '강남 119-3',
          created_at: new Date(Date.now() - 25 * 60000).toISOString(),
          handled_at: new Date(Date.now() - 15 * 60000).toISOString(),
          details: '차량 추돌 사고, 운전석 핸들 흉부 압박 shock. 늑골 골절 및 기흉(Pneumothorax) 의심. 산소 4L 투여 중.',
          vitals: { bp: '110/70', hr: '95', spo2: '94', rr: '24' }
        }
      ]);
      setIsTestMode(true);
    }
  };

  const formattedDateStr = currentTime.toLocaleDateString('ko-KR', {
    year: 'numeric', month: '2-digit', day: '2-digit'
  }) + ' ' + currentTime.toLocaleTimeString('ko-KR', { hour12: true });

  const pendingPatients = patients.filter(p => p.request_status === 'PENDING');
  const acceptedPatients = patients.filter(p => p.request_status === 'ACCEPTED');

  return (
    <div className="flex h-screen w-full bg-[#F8FAFC] font-sans text-slate-800 overflow-hidden">
      
      {/* 1. 사이드바 (Dark Navy Theme) */}
      <aside className="w-64 bg-[#0f2147] text-white flex flex-col justify-between shrink-0 shadow-2xl border-r border-[#0a1630] z-20">
        <div>
          <div className="h-20 flex items-center px-6 border-b border-white/10">
            <div className="bg-rose-600 p-2 rounded-xl mr-3 shadow-lg shadow-rose-600/30">
              <Activity className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="font-black text-xl leading-tight tracking-wider text-white">ER-LINK</h1>
              <p className="text-[10px] text-blue-200/70 font-semibold">응급 환자 수용 관제 플랫폼</p>
            </div>
          </div>
          
          <div className="mx-4 my-5 p-4 bg-white/5 border border-white/10 rounded-2xl text-center backdrop-blur-sm">
            <div className="w-12 h-12 bg-[#0a1630] border border-white/10 rounded-full flex items-center justify-center mx-auto mb-2.5 text-slate-300">
              <Building2 className="w-6 h-6 text-sky-400" />
            </div>
            <div className="font-bold text-white text-base truncate" title={hospital?.name}>
              {hospital ? hospital.name : '로그인 대기'}
            </div>
            <div className="text-xs text-blue-200/60 mt-0.5 truncate">
              ID: {hospital ? hospital.userid : '-'}
            </div>
            <button className="mt-3.5 w-full py-2 px-3 bg-white/10 hover:bg-white/20 text-white text-xs font-bold rounded-xl transition-all flex items-center justify-center gap-1.5 border border-white/10">
              <LogOut className="w-3.5 h-3.5" /> 로그아웃
            </button>
          </div>

          <nav className="p-4 space-y-1.5">
            <button
              onClick={() => setActiveTab('dashboard')}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-bold transition-all ${
                activeTab === 'dashboard' ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/30' : 'text-blue-200/70 hover:text-white hover:bg-white/5'
              }`}
            >
              <LayoutDashboard className="w-5 h-5" /> 수용 관제 대시보드
            </button>
            <button
              onClick={() => setActiveTab('history')}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-bold transition-all ${
                activeTab === 'history' ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/30' : 'text-blue-200/70 hover:text-white hover:bg-white/5'
              }`}
            >
              <Clock className="w-5 h-5" /> 수락 내역 관리
            </button>
            <button className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold text-blue-200/50 hover:text-white hover:bg-white/5 transition-all">
              <UserPlus className="w-5 h-5" /> 계정 발급 요청
            </button>
            <button className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold text-blue-200/50 hover:text-white hover:bg-white/5 transition-all">
              <Users className="w-5 h-5" /> 의료진 계정 관리
            </button>
          </nav>
        </div>
        
        <div className="p-4 border-t border-white/10 bg-[#0a1630]/60">
          <button
            onClick={toggleTestMode}
            className={`w-full py-3 px-4 rounded-xl text-sm font-bold transition-all shadow-md flex items-center justify-center gap-2 ${
              isTestMode 
                ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40 hover:bg-rose-500/30' 
                : 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white hover:opacity-95'
            }`}
          >
            {isTestMode ? <X className="w-4 h-4" /> : <Check className="w-4 h-4" />}
            {isTestMode ? '테스트 데이터 비우기' : 'API 더미 데이터 생성'}
          </button>
        </div>
      </aside>

      {/* 2. 메인 화면 (Full Width Layout) */}
      <main className="flex-1 flex flex-col h-full w-full min-w-0 overflow-hidden">
        
        {/* 상단 헤더 */}
        <header className="h-20 bg-white border-b border-slate-200/80 flex items-center justify-between px-6 shrink-0 z-10 shadow-sm">
          <div className="flex items-center gap-4 min-w-0">
            <div className="bg-rose-50 p-2.5 rounded-2xl border border-rose-100 shrink-0">
              <ShieldAlert className="w-6 h-6 text-rose-500" />
            </div>
            <div className="flex items-center gap-3 overflow-hidden">
              <h2 className="text-xl font-black text-slate-900 truncate">{hospital ? hospital.name : '병원 정보 없음'}</h2>
              <span className="text-xs font-semibold text-slate-500 bg-slate-100 px-3 py-1 rounded-full whitespace-nowrap shrink-0 border border-slate-200">
                {hospital ? hospital.userid : '-'}
              </span>
              <span className="text-sm font-bold text-slate-700 bg-blue-50 px-3.5 py-1.5 rounded-full whitespace-nowrap shrink-0 border border-blue-100 hidden md:inline">
                {formattedDateStr}
              </span>
            </div>
          </div>
          
          <div className="flex items-center gap-4 shrink-0 ml-4">
            <div className="flex bg-slate-100 rounded-2xl p-1.5 border border-slate-200/80 shadow-inner whitespace-nowrap shrink-0">
              <div className="flex items-center gap-2.5 px-3 border-r border-slate-200">
                <span className="text-xs font-black text-slate-700">응급실</span>
                <button 
                  onClick={toggleErStatus}
                  disabled={!hospital}
                  className={`w-12 h-6 rounded-full transition-colors flex items-center px-1 ${!hospital ? 'bg-slate-300' : hospital.er_status === 'ON' ? 'bg-emerald-500' : 'bg-slate-300'}`}
                >
                  <div className={`w-4 h-4 bg-white rounded-full shadow-md transition-transform ${hospital?.er_status === 'ON' ? 'translate-x-6' : 'translate-x-0'}`}></div>
                </button>
              </div>
              <div className="flex items-center gap-2.5 px-3">
                <span className="text-xs font-black text-slate-700">수술실</span>
                <button 
                  onClick={toggleOrStatus}
                  disabled={!hospital}
                  className={`w-12 h-6 rounded-full transition-colors flex items-center px-1 ${!hospital ? 'bg-slate-300' : hospital.or_status === 'ON' ? 'bg-emerald-500' : 'bg-slate-300'}`}
                >
                  <div className={`w-4 h-4 bg-white rounded-full shadow-md transition-transform ${hospital?.or_status === 'ON' ? 'translate-x-6' : 'translate-x-0'}`}></div>
                </button>
              </div>
            </div>

            <button 
              onClick={handleRefresh}
              disabled={isRefreshing || !hospital}
              className={`flex items-center gap-2 px-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm font-bold text-slate-700 hover:bg-slate-50 hover:text-blue-600 transition-all shadow-sm shrink-0 ${isRefreshing ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <RotateCcw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-blue-600' : ''}`} />
              새로고침
            </button>
          </div>
        </header>

        {/* 본문 콘텐츠 (100% 가로 채움) */}
        <div className="flex-1 w-full overflow-y-auto p-6 lg:p-8 bg-[#F8FAFC]">
          {!hospital ? (
             <div className="h-full flex flex-col items-center justify-center text-slate-400">
               <div className="w-24 h-24 bg-slate-100 rounded-3xl flex items-center justify-center mb-6 border border-slate-200 shadow-sm">
                 <FileText className="w-12 h-12 text-slate-400" />
               </div>
               <p className="text-xl font-extrabold text-slate-700 mb-2">응급 관제 시스템 연동 대기 중</p>
               <p className="text-sm text-slate-400">좌측 하단의 <span className="font-bold text-blue-600">'API 더미 데이터 생성'</span> 버튼을 눌러 외상 환자 데이터를 불러오세요.</p>
             </div>
          ) : activeTab === 'dashboard' ? (
            
            // 12-Column 전체 폭 그리드
            <div className="w-full grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
              
              {/* Left Column: 수용 요청 환자 카운터 (8 Columns) */}
              <section className="lg:col-span-8 w-full space-y-4">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <h3 className="text-xl font-black text-slate-900 tracking-tight">응급실 환자 수용 요청</h3>
                    <span className="bg-rose-500 text-white text-xs font-black px-3 py-1 rounded-full shadow-sm">
                      {pendingPatients.length}건 대기 중
                    </span>
                  </div>
                </div>

                {pendingPatients.length === 0 ? (
                  <div className="bg-white rounded-3xl border border-slate-200/80 p-20 flex flex-col items-center justify-center text-slate-400 shadow-sm">
                    <AlertCircle className="w-16 h-16 mb-4 text-slate-300" />
                    <p className="font-extrabold text-lg text-slate-600">대기 중인 긴급 수용 요청이 없습니다.</p>
                  </div>
                ) : (
                  <div className="space-y-6">
                    {pendingPatients.map(patient => (
                      <div key={patient._id} className="bg-white rounded-3xl p-6 shadow-sm border border-slate-200/80 relative overflow-hidden flex flex-col md:flex-row gap-6 transition-all hover:shadow-md">
                        {/* 응급 심각도 표시 바 */}
                        <div className={`absolute left-0 top-0 bottom-0 w-2 ${patient.severity === 'KTAS 1' ? 'bg-rose-600' : 'bg-rose-500'}`}></div>
                        
                        {/* 환자 외상 / 진단 사진 썸네일 */}
                        <div className="w-full md:w-44 h-48 bg-slate-900 rounded-2xl shrink-0 overflow-hidden relative group cursor-pointer border border-slate-200" onClick={() => setSelectedImageModal(patient)}>
                          <img src={patient.image} alt={patient.imageTitle} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300 opacity-90" />
                          <div className="absolute inset-0 bg-slate-950/40 group-hover:bg-slate-950/20 transition-colors flex flex-col items-center justify-center p-2 text-center">
                            <Maximize2 className="text-white w-7 h-7 mb-1 drop-shadow-md group-hover:scale-110 transition-transform" />
                            <span className="text-[10px] font-black text-white bg-black/60 px-2 py-0.5 rounded-full backdrop-blur-md border border-white/20">
                              외상 사진 확대
                            </span>
                          </div>
                          <div className="absolute bottom-0 left-0 right-0 bg-slate-950/80 text-slate-200 text-[10px] font-medium text-center py-1 truncate px-1">
                            {patient.imageTitle}
                          </div>
                        </div>

                        {/* 상세 정보 */}
                        <div className="flex-1 min-w-0 flex flex-col">
                          <div className="flex flex-wrap justify-between items-start gap-2 mb-2">
                            <div className="flex items-center gap-2.5">
                              <span className={`text-white text-xs font-black px-3 py-1 rounded-lg shadow-sm ${patient.severity === 'KTAS 1' ? 'bg-rose-600' : 'bg-rose-500'}`}>
                                {patient.severity}
                              </span>
                              <span className="text-slate-400 text-sm font-mono font-bold tracking-tight">{patient.patientid}</span>
                            </div>
                            <span className="text-rose-600 text-sm font-black bg-rose-50 px-3.5 py-1 rounded-full border border-rose-100 animate-pulse flex items-center gap-1.5">
                              <Clock className="w-4 h-4" /> {patient.eta} 도착 예정
                            </span>
                          </div>

                          <h4 className="text-xl font-black text-slate-900 mb-1">{patient.name}</h4>
                          <p className="text-xs font-bold text-slate-500 mb-3 flex items-center gap-2">
                            <span>구급대: <strong className="text-slate-700">{patient.ambid}</strong></span>
                          </p>
                          
                          {/* 소견 및 외상 상태 상세 노트 */}
                          <div className="bg-slate-50 rounded-2xl p-4 text-sm text-slate-700 mb-4 border border-slate-100 font-medium leading-relaxed">
                            <span className="text-xs font-bold text-rose-600 block mb-1">[현장 구급대원 보고]</span>
                            {patient.details}
                          </div>

                          <div className="mt-auto flex flex-wrap justify-between items-center gap-4 pt-2 border-t border-slate-100">
                            {/* 바이탈 사인 */}
                            <div className="flex gap-4 sm:gap-6 bg-slate-100/70 border border-slate-200/60 rounded-xl px-4 py-2">
                              {patient.vitals && (
                                <>
                                  <div className="text-center">
                                    <div className="text-[10px] text-slate-400 font-bold">혈압 (BP)</div>
                                    <div className="font-extrabold text-rose-600 text-sm">{patient.vitals.bp}</div>
                                  </div>
                                  <div className="w-px bg-slate-200"></div>
                                  <div className="text-center">
                                    <div className="text-[10px] text-slate-400 font-bold">맥박 (HR)</div>
                                    <div className="font-extrabold text-slate-800 text-sm">{patient.vitals.hr}</div>
                                  </div>
                                  <div className="w-px bg-slate-200"></div>
                                  <div className="text-center">
                                    <div className="text-[10px] text-slate-400 font-bold">산소 (SpO2)</div>
                                    <div className="font-extrabold text-emerald-600 text-sm">{patient.vitals.spo2}%</div>
                                  </div>
                                </>
                              )}
                            </div>
                            
                            {/* 수락 / 거절 버튼 */}
                            <div className="flex gap-2.5 shrink-0 w-full sm:w-auto">
                              <button onClick={() => handleRejectRequest(patient._id)} className="flex-1 sm:flex-none px-6 py-2.5 rounded-xl border-2 border-rose-200 text-rose-600 font-bold text-sm hover:bg-rose-50 transition-colors">
                                수용 불가 (거절)
                              </button>
                              <button onClick={() => handleAcceptRequest(patient._id)} className="flex-1 sm:flex-none px-8 py-2.5 rounded-xl bg-[#0f2147] text-white font-bold text-sm hover:bg-[#0a1630] transition-colors shadow-lg shadow-[#0f2147]/20">
                                환자 수용 (수락)
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              {/* Right Column: 최근 수락된 환자 (4 Columns) */}
              <aside className="lg:col-span-4 w-full">
                <div className="bg-white rounded-3xl p-6 border border-slate-200/80 shadow-sm sticky top-0">
                  <div className="flex items-center gap-3 mb-6">
                    <h3 className="text-lg font-black text-slate-900">최근 수락 환자</h3>
                    <span className="bg-blue-100 text-blue-700 text-xs font-extrabold px-3 py-0.5 rounded-full">{acceptedPatients.length}명</span>
                  </div>
                  
                  {acceptedPatients.length === 0 ? (
                    <div className="py-16 flex flex-col items-center justify-center text-slate-400">
                      <HeartPulse className="w-10 h-10 mb-2 text-slate-300" />
                      <p className="font-bold text-sm text-slate-400">수락된 환자가 없습니다.</p>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {acceptedPatients.map(patient => (
                        <div key={patient._id} className="p-4 rounded-2xl border border-slate-200/80 bg-slate-50 flex gap-4 hover:border-blue-400 transition-all cursor-pointer" onClick={() => setSelectedImageModal(patient)}>
                          <div className="w-14 h-14 rounded-xl bg-slate-900 shrink-0 overflow-hidden relative border border-slate-200">
                            <img src={patient.image} alt="외상 사진" className="w-full h-full object-cover" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex justify-between items-center mb-1">
                              <span className="font-black text-slate-900 text-sm truncate">{patient.name.split('·')[0]}</span>
                              <span className="text-[10px] text-blue-600 font-extrabold bg-blue-50 px-2 py-0.5 rounded-md border border-blue-100">{patient.eta}</span>
                            </div>
                            <p className="text-xs text-slate-500 line-clamp-2 font-medium">{patient.details}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </aside>

            </div>
          ) : (
            <div className="w-full">
               <h3 className="text-xl font-black text-slate-900 mb-6">수락 내역 관리</h3>
               <div className="bg-white rounded-3xl border border-slate-200/80 p-24 flex flex-col items-center justify-center text-slate-400 shadow-sm">
                 <Clock className="w-16 h-16 mb-4 text-slate-300" />
                 <p className="font-extrabold text-slate-600 text-lg">아직 등록된 수락 이력이 없습니다.</p>
               </div>
            </div>
          )}
        </div>
      </main>

      {/* 3. 외상 사진 고화질 확대 모달창 */}
      {selectedImageModal && (
        <div className="fixed inset-0 bg-slate-950/90 backdrop-blur-md z-50 flex items-center justify-center p-4 md:p-8" onClick={() => setSelectedImageModal(null)}>
          <div className="relative max-w-4xl w-full bg-slate-900 rounded-3xl overflow-hidden shadow-2xl border border-slate-700 flex flex-col" onClick={(e) => e.stopPropagation()}>
            
            {/* 모달 헤더 */}
            <div className="p-5 bg-slate-900 border-b border-slate-800 flex justify-between items-center text-white">
              <div>
                <h3 className="font-extrabold text-lg text-white">{selectedImageModal.imageTitle}</h3>
                <p className="text-xs text-slate-400 font-mono mt-0.5">{selectedImageModal.name} ({selectedImageModal.patientid})</p>
              </div>
              <button 
                className="text-slate-400 hover:text-white bg-slate-800 p-2 rounded-full transition-colors" 
                onClick={() => setSelectedImageModal(null)}
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            {/* 고화질 이미지 영역 */}
            <div className="bg-black flex items-center justify-center p-4 min-h-[400px] max-h-[70vh] overflow-hidden">
              <img src={selectedImageModal.image} alt="외상 사진 확대" className="max-h-[65vh] w-auto object-contain rounded-lg" />
            </div>

            {/* 모달 하단 외상 설명 */}
            <div className="p-5 bg-slate-900 border-t border-slate-800 text-slate-300 text-sm font-medium">
              <span className="text-xs font-bold text-rose-400 block mb-1">진단 및 소견 노트:</span>
              {selectedImageModal.details}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}