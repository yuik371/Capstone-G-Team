import { useState } from "react";
import { useNavigate } from "react-router-dom";
import "./Login.css";

const FEATURES = [
  { icon: "pulse", title: "중증도 예측 · 필요 진료과", desc: "KTAS 기반 환자 상태 요약" },
  { icon: "pin", title: "실시간 구급차 위치", desc: "수락 환자의 도착 예정 시간 추적" },
  { icon: "photo", title: "현장 외상 사진", desc: "구급대원이 전송한 사진 즉시 확인" },
];

function Icon({ name }) {
  const p = { width: 18, height: 18, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round" };
  switch (name) {
    case "pulse": return <svg {...p}><path d="M3 12h4l2-6 4 12 2-6h6" /></svg>;
    case "pin": return <svg {...p}><path d="M12 21s7-6.2 7-11a7 7 0 10-14 0c0 4.8 7 11 7 11z" /><circle cx="12" cy="10" r="2.5" /></svg>;
    case "photo": return <svg {...p}><rect x="3" y="5" width="18" height="14" rx="2" /><circle cx="9" cy="10" r="1.5" /><path d="M21 16l-5-5-8 8" /></svg>;
    case "id": return <svg {...p}><rect x="3" y="5" width="18" height="14" rx="2" /><circle cx="9" cy="11" r="2" /><path d="M14 10h4M14 14h4M6 16c.6-1.4 1.8-2 3-2s2.4.6 3 2" /></svg>;
    case "lock": return <svg {...p}><rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 018 0v3" /></svg>;
    default: return null;
  }
}

export default function Login() {
  const navigate = useNavigate();
  const [userid, setUserid] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setMessage("");
    setLoading(true);

    try {
      const response = await fetch("http://127.0.0.1:8000/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ userid, password }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "로그인에 실패했습니다.");
      }

      sessionStorage.setItem("access_token", data.access_token);
      navigate("/hospital");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login">
      {/* 왼쪽 */}
      <section className="login_hero">
        <div className="login_brand">
          <div className="login_logo">+</div>
          <div>
            <strong>ER-LINK</strong>
            <span>응급 환자 수용 관제 플랫폼</span>
          </div>
        </div>

        <div className="login_copy">
          <h1>
            구급차 환자 수용 요청을
            <br /> 한 화면에서 판단하세요.
          </h1>
          <p>로그인하면 소속 의료기관의 응급실 관제 화면으로 바로 연결됩니다</p>

          <ul className="login_features">
            {FEATURES.map((f) => (
              <li key={f.title}>
                <span className="login_feature-icon"><Icon name={f.icon} /></span>
                <div>
                  <strong>{f.title}</strong>
                  <span>{f.desc}</span>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <p className="login_notice">
          <Icon name="lock" />
          등록된 의료기관 계정만 접근 가능합니다.
        </p>
      </section>

      {/* 오른쪽 */}
      <section className="login_panel">
        <form className="login_form" onSubmit={handleSubmit} noValidate>
          <h2> 의료기관 로그인 </h2>
          <p className="login_sub">소속 병원 계정으로 로그인하세요.</p>

          <label className="field">
            <span className="field_label">아이디</span>
            <span className="field_box">
              <Icon name="id" />
              <input type="text" value={userid} onChange={(e) => setUserid(e.target.value)} placeholder="아이디 입력" autoComplete="username" />
            </span>
          </label>

          <label className="field">
            <span className="field_label">비밀번호</span>
            <span className="field_box">
              <Icon name="lock" />
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="비밀번호 입력" autoComplete="current-password" />
            </span>
          </label>

          {message && <p className="login_error">{message}</p>}

          <button type="submit" className="login_submit" disabled={loading}>
            {loading ? "로그인 중..." : "로그인"}
          </button>

          <div className="login_help">
            <span>계정 발급 · 장애 문의</span>
            <strong>전화번호</strong>
          </div>
        </form>
      </section>
    </div>
  );
}