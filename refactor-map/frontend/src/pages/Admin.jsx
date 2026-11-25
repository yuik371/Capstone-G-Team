import { useEffect,useState,useCallback } from "react";
import {useNavigate } from "react-router-dom";
import { Building2, FileText, LogOut, MapPin, Users } from "lucide-react";
import "./Admin.css";
import AdminMap from "../components/AdminMap.jsx"

const VITE_SERVER_URL = import.meta.env.VITE_SERVER_URL;

function accountTypeLabel(type){
  if(type==="hospital") return "병원";
  if(type==="amb") return "구급대원";
  if(type==="admin") return "관리자";
  return type || "-";
}

function  displayDate(value) {
  if(!value) return "-";

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "-": date.toLocaleString("ko-KR");
}

export default function Admin(){
  const [processing, setProcessing] = useState(false);
  const [activeMenu, setActiveMenu] = useState("requests");
  const [requests, setRequest] = useState([]);
  const [users, setUsers] = useState([]);
  const [maps, setMaps] = useState([]);
  const memberCount = maps.filter((hospital) => hospital.is_member).length;
  const nonMemberCount = maps.length - memberCount;
  const [loading, setLoading] = useState(false);
  const [processingId, setProcessingId] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [currentUser, setCurrentUser] = useState(null);

  const navigate = useNavigate();

  function logout(){
    sessionStorage.removeItem("access_token");
    navigate("/login");
  }
  function getHeaders() {
      const token = sessionStorage.getItem("access_token");

      if(!token){
          navigate("/login")
          return null;
      }

      return {Authorization: `Bearer ${token}`};
  }

  async function executeHospitals() {
    const headers = getHeaders();
    if(!headers) return;
    setProcessing(true);
    try{
      const response = await fetch(`${VITE_SERVER_URL}/admin/hospital/all/first`,{
      method: "POST",
      headers: {...headers}
    }
  );
  const data = await response.json();
  if(!response.ok) {
    throw new Error(data.detail || "병원 정보 수동 입력 실패");     
  }
  setMessage("병원 정보 수동 입력 성공");
  } catch (err){
    setError(err.message);
  } finally {
    setProcessing(false);
  }
}

  const loadData = useCallback(async() =>{
  const token = sessionStorage.getItem("access_token");




    if(!token){
      setError("로그인 필요");
      return;
    }

    setLoading(true);
    setError("");

    const paths = {
      requests: "/admin/account/requests",
      map: "/admin/hospital/map",
      users: "/admin/user/list",
    };

    const path = paths[activeMenu];

    try {
      const headers = getHeaders();
      const response = await fetch(`${VITE_SERVER_URL}${path}`,{
        headers:{
          Authorization: `Bearer ${token}`
        }
      });

      const data = await response.json().catch(() => ({}));
      if(!response.ok){
        throw new Error(data.detail || "목록을 불러오지 못했습니다.");
      }
      if (activeMenu === "requests"){
        setRequest(Array.isArray(data.requests) ? data.requests : []);
      } else if (activeMenu === "users") {
        setUsers(Array.isArray(data.users) ? data.users : []);
      } else if (activeMenu === "map"){
        setMaps(Array.isArray(data.hospitals_location) ? data.hospitals_location : []);
      } 

    } catch(err){
      setError(err.message);
    } finally{
      setLoading(false);
    }
  }, [activeMenu]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function handleDecision(requestId,decision) {
    const token = sessionStorage.getItem("access_token");
    setProcessingId(requestId);
    setError("");
    setMessage("");
    
    try{
      const response = await fetch(`${VITE_SERVER_URL}/admin/account/requests/${requestId}/decision`,
        {
          method: "PATCH",
          headers:{
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ decision })
        }
      );

      const data = await response.json().catch(()=> ({}));

      setMessage(decision === "accepted"? "신청을 승인했습니다" : "신천을 거절했습니다.");
      await loadData();
    } catch(err){
      setError(err.message);
    } finally{
      setProcessingId("");
    }
  }
  useEffect(() => {
  async function loadCurrentUser() {
    const token = sessionStorage.getItem("access_token");

    try {
      const response = await fetch(`${VITE_SERVER_URL}/auth/me`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error("사용자 정보를 불러오지 못했습니다.");
      }

      setCurrentUser(await response.json());
    } catch (err) {
      setError(err.message);
    }
  }

  loadCurrentUser();
}, []);

  return (
    <div className="admin-layout">
      <aside className="w-64 bg-[#0f2147] text-white flex flex-col justify-between shrink-0 shadow-2xl border-r border-slate-800 z-20">
        <div>
          {/* 로고 */}
          <div className="p-6 border-b border-slate-800/80 flex items-center space-x-3">
            <div className="w-10 h-10 bg-red-600 rounded-xl flex items-center justify-center text-white shadow-lg shadow-red-900/40 font-bold text-xl">
              +
            </div>

            <div>
              <h1 className="font-extrabold text-xl tracking-tight text-white">
                ER-LINK
              </h1>
              <p className="text-[11px] text-slate-400 font-medium">
                응급 환자 수용 관제 플랫폼
              </p>
            </div>
          </div>

          {/* 관리자 계정 카드 */}
          <div className="mx-4 my-5 p-4 bg-slate-900/70 border border-slate-800 rounded-xl text-center">
            <div className="w-12 h-12 bg-slate-800 border border-slate-700 rounded-full flex items-center justify-center mx-auto mb-2 text-slate-300">
              <Building2 className="w-6 h-6 text-sky-400" />
            </div>

            <div className="font-bold text-white text-base truncate">
              {currentUser?.userid || "관리자"}
            </div>

            <div className="text-xs text-slate-400 mt-0.5">
              관리자 계정
            </div>

            <button
              onClick={logout}
              className="w-full mt-3 py-1.5 px-3 bg-slate-800/90 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-semibold rounded-lg transition flex items-center justify-center gap-1.5 border border-slate-700/60"
            >
              <LogOut className="w-3.5 h-3.5 text-slate-400" />
              로그아웃
            </button>
          </div>

          {/* 메뉴 */}
          <nav className="px-3 space-y-1">
            <button
              onClick={() => setActiveMenu("requests")}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition ${
                activeMenu === "requests"
                  ? "bg-blue-600/90 text-white shadow-lg shadow-blue-900/30"
                  : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
              }`}
            >
              <FileText className="w-5 h-5" />
              계정 발급 요청
            </button>

            <button
              onClick={() => setActiveMenu("users")}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition ${
                activeMenu === "users"
                  ? "bg-blue-600/90 text-white shadow-lg shadow-blue-900/30"
                  : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
              }`}
            >
              <Users className="w-5 h-5" />
              사용자 계정
            </button>

            <button
              onClick={() => setActiveMenu("map")}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition ${
                activeMenu === "map"
                  ? "bg-blue-600/90 text-white shadow-lg shadow-blue-900/30"
                  : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
              }`}
            >
              <MapPin className="w-5 h-5" />
              병원 지도
            </button>
          </nav>
        </div>

        {/* 하단 푸터 */}
        <div className="p-4 border-t border-slate-800/80 bg-slate-950/40 text-center">
          <p className="text-[11px] text-slate-500 font-medium">
            ER-LINK Control System
          </p>
        </div>
      </aside>
      <main className="admin-main">
        <header className="admin-header">
          <div>
            <p>ER-LINK / 관리자</p>
            <h1>
              {activeMenu === "requests" ? "계정 발급 요청" : activeMenu === "users" ? "사용자 계정" : "병원 지도"}
            </h1>
          </div>

          <button className="admin-refresh" onClick={loadData} disabled={loading}>
            새로고침
          </button>
        </header>

        {error && <p className="admin-alert error">{error}</p>}
        {message && <p className="admin-alert success">{message}</p>}

        {loading ? (
          <p className="admin-loading">목록을 불러오는 중...</p>
        ) : activeMenu === "requests" ? (
          <section className="admin-card">
            <h2>대기 중인 신청 ({requests.length})</h2>

            {requests.length === 0 ? (
              <p className="admin-empty">대기 중인 신청이 없습니다.</p>
            ) : (
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>종류 / 기관명</th>
                      <th>신청자</th>
                      <th>연락처</th>
                      <th>신청 내용</th>
                      <th>신청일</th>
                      <th>처리</th>
                    </tr>
                  </thead>
                  <tbody>
                    {requests.map((request) => (
                      <tr key={request.id}>
                        <td>
                          <strong>{accountTypeLabel(request.account_type)}</strong>
                          <span>{request.account_name || "-"}</span>
                          {request.hpid && (
                            <small>HPID: {request.hpid}</small>
                          )}
                        </td>
                        <td>
                          <strong>{request.applicant_name || "-"}</strong>
                          <span>{request.position || "-"}</span>
                        </td>
                        <td>{request.phone || "-"}</td>
                        <td className="admin-reason">{request.reason || "-"}</td>
                        <td>{displayDate(request.created_at)}</td>
                        <td>
                          <div className="admin-actions">
                            <button
                              className="approve"
                              disabled={processingId === request.id}
                              onClick={() => handleDecision(request.id, "accepted")}
                            >
                              수락
                            </button>
                            <button
                              className="reject"
                              disabled={processingId === request.id}
                              onClick={() => handleDecision(request.id, "rejected")}
                            >
                              거절
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        ) : activeMenu === "users" ? (
          <section className="admin-card">
            <h2>계정 목록 ({users.length})</h2>

            {users.length === 0 ? (
              <p className="admin-empty">등록된 계정이 없습니다.</p>
            ) : (
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>사용자 ID</th>
                      <th>역할</th>
                      <th>병원 ID</th>
                      <th>구급대 ID</th>
                      <th>가입일</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((user) => (
                      <tr key={user.id}>
                        <td>{user.userid || "-"}</td>
                        <td>{accountTypeLabel(user.role)}</td>
                        <td>{user.hospitalid ?? "-"}</td>
                        <td>{user.ambid || "-"}</td>
                        <td>{displayDate(user.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        ) : activeMenu === "map" ? (
          <section className="admin-card">
            <h2>병원 지도 ({maps.length})</h2>
              <button onClick={executeHospitals} disabled={processing} className="mb-4 rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white shadow-md transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-400">병원 동기화</button>
              <span className={"ml-3 text-slate-950 font-medium text-bold"}>{processing ? "병원 정보 적재 중..." :  "병원 정보 수동 적재 "}</span>
            <AdminMap hospitals={maps}/>
            <span className={"text-blue-600 font-medium"}>● 회원 병원: {memberCount} <span className={"ml-3 text-red-600 font-medium"}>● 비회원 병원 {nonMemberCount}</span></span>
          </section>
          
        ): null}
      </main>
    </div>
  );
}


