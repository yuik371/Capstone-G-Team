import { useState } from "react";
import { useNavigate } from "react-router-dom";
import "./AccountLink.css";

const VITE_SERVER_URL = import.meta.env.VITE_SERVER_URL;


export default function HospitalLink() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    account_type: "",
    account_name: "",
    hpid: "",
    applicant_name: "",
    position: "",
    phone: "",
    reason: "",
  });
  const [message, setMessage] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [hospitalMatches, setHospitalMatches] = useState([]);
  const [verifiedHospital, setVerifiedHospital] = useState(null);
  const [lookupMessage, setLookupMessage] = useState("");

async function checkHospital() {
  setLookupMessage("");
  setHospitalMatches([]);
  setVerifiedHospital(null);

  if (form.account_type !== "hospital") {
    setLookupMessage("병원 신청일 때만 병원 확인을 할 수 있습니다.");
    return;
  }

  if (!form.account_name.trim()) {
    setLookupMessage("기관명을 먼저 입력해 주세요.");
    return;
  }

  const token = sessionStorage.getItem("access_token");
  if (!token) {
    navigate("/login", { replace: true });
    return;
  }

  try {
    const response = await fetch(
      `${VITE_SERVER_URL}/auth/link/hospitals?name=${encodeURIComponent(form.account_name.trim())}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "병원 조회에 실패했습니다.");
    }

    const exactMatches = data.exact_matches || [];
    const similarMatches = data.similar_matches || [];

    if (exactMatches.length === 1) {
      const hospital = exactMatches[0];

      setVerifiedHospital(hospital);
      setForm((previous) => ({
        ...previous,
        account_name: hospital.name,
        hpid: hospital.hpid,
      }));
      setLookupMessage(
        `확인 완료: ${hospital.name} (HPID: ${hospital.hpid})`
      );
    } else if (exactMatches.length > 1) {
      setHospitalMatches(exactMatches);
      setLookupMessage("같은 이름의 병원이 여러 곳입니다. 해당 병원을 선택해 주세요.");
    } else {
      setHospitalMatches(similarMatches);
      setLookupMessage(
        similarMatches.length
          ? "정확히 일치하는 병원이 없습니다. 검색 결과에서 선택해 주세요."
          : "일치하는 병원을 찾지 못했습니다."
      );
    }
  } catch (error) {
    setLookupMessage(error.message);
  }
}

function updateField(event) {
  const { name, value } = event.target;

  setForm((previous) => ({
    ...previous,
    [name]: value,
    ...(name === "account_name" || name === "account_type"
      ? { hpid: "" }
      : {}),
  }));

  if (name === "account_name" || name === "account_type") {
    setVerifiedHospital(null);
    setHospitalMatches([]);
    setLookupMessage("");
  }
}

  async function handleSubmit(event) {
    event.preventDefault();
    setMessage("");
    if (form.account_type === "hospital" && !verifiedHospital) {
      setMessage("먼저 병원 확인을 해주세요.");
      return;
    }
    const token = sessionStorage.getItem("access_token");
    if (!token) {
      navigate("/login", { replace: true });
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(
        `${VITE_SERVER_URL}/auth/link/requests`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(form),
        }
      );

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        const detail = data.detail;
        const errorMessage = Array.isArray(detail)
          ? detail.map((item) => item.msg).join(", ")
          : typeof detail === "string"
            ? detail
            : "신청을 보내지 못했습니다.";

        throw new Error(errorMessage);
      }

      setSubmitted(true);
      setMessage("신청이 접수됐습니다. 관리자가 확인한 뒤 처리합니다.");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="link-request-page">
      <header className="link-request-brand">
        <div className="link-request-logo">+</div>
        <div>
          <strong>ER-LINK</strong>
          <span>응급 환자 수용 관제 플랫폼</span>
        </div>
      </header>

      <section className="link-request-card">
        <h1>계정 연결 신청</h1>
        <p className="link-request-sub">
          담당 중인 기관 정보를 입력해 주세요.
        </p>

        <form onSubmit={handleSubmit}>
          <label>
            <span>신청 종류</span>
            <select name="account_type" value={form.account_type} onChange={updateField} required disabled={submitted}>
            <option value="" disabled>신청 종류를 선택하세요.</option>
            <option value="hospital">병원</option>
            <option value="amb">구급대원</option>
            </select>
          </label>

          <label>
            <span>기관명</span>
            <div className="account-area">
              <input name="account_name" value={form.account_name} onChange={updateField} placeholder="예: 충주병원" required disabled={submitted}/>
              <button type="button" className="account-check-btn" onClick={checkHospital}>병원 확인</button>
            </div>
            {lookupMessage && <p>{lookupMessage}</p>}
            <div className="hpid-matches">
            {hospitalMatches.map((hospital) => (
            <button
              type="button" 
              className="hpid-matches-btn"
              key={hospital.hpid}
              onClick={() => {
                setVerifiedHospital(hospital);
                setForm((previous) => ({
                  ...previous,
                  account_name: hospital.name,
                  hpid: hospital.hpid
                }));
                setLookupMessage(
                  `선택 완료: ${hospital.name} (HPID: ${hospital.hpid})`
                );
                setHospitalMatches([]);
              }}
            >
              {hospital.name}
            </button>
          ))}
          </div>
          </label>

          {form.account_type === "hospital" && (
          <label>
            <span>기관 코드 (HPID)</span>
            <input name="account_code" value={form.hpid} onChange={updateField} placeholder="병원 확인 후 자동 입력" required disabled={submitted} readOnly/>
          </label>
          )}

          <label>
            <span>담당자 이름</span>
            <input name="applicant_name" value={form.applicant_name} onChange={updateField} placeholder="이름 입력" required disabled={submitted}/>
          </label>

          <label>
            <span>직책</span>
            <input name="position" value={form.position} onChange={updateField} placeholder="예: 응급실 담당자" required disabled={submitted}/>
          </label>

          <label>
            <span>연락처</span>
            <input name="phone" type="tel" value={form.phone} onChange={updateField} placeholder="연락 가능한 전화번호" required disabled={submitted} />
          </label>

          <label>
            <span>신청 내용</span>
            <textarea name="reason" value={form.reason} onChange={updateField} placeholder="병원 담당자임을 확인할 수 있는 내용을 작성해 주세요." rows={4} required disabled={submitted}/>
          </label>

          {message && (
            <p className={submitted ? "link-request-success" : "link-request-error"}>
              {message}
            </p>
          )}

          {!submitted && (
            <button type="submit" disabled={loading}>
              {loading ? "신청 중..." : "기관 연결 신청"}
            </button>
          )}
        </form>

        <button className="link-request-back" type="button" onClick={() => {navigate("/login")}}>로그인 화면으로</button>
      </section>
    </main>
  );
}