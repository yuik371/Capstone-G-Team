import { useState } from "react";
import { useNavigate } from "react-router-dom";
import "./Register.css";

const VITE_SERVER_URL = import.meta.env.VITE_SERVER_URL

export default function Register() {
  const navigate = useNavigate();

  const [userid, setUserid] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [message, setMessage] = useState("");
  const [isSuccess, setIsSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setMessage("");
    setIsSuccess(false);

    if (password !== passwordConfirm) {
      setMessage("비밀번호가 서로 일치하지 않습니다.");
      return;
    }

    if (password.length < 8) {
      setMessage("비밀번호를 8자 이상 입력해 주세요.");
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(`${VITE_SERVER_URL}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          userid: userid.trim(),
          password,
        }),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(data.detail || "회원가입에 실패했습니다.");
      }

      setIsSuccess(true);
      setMessage(
        "회원가입이 완료되었습니다. 병원 연결은 관리자에게 요청해 주세요."
      );
      alert("회원가입이 완료되었습니다. 병원 연결은 관리자에게 요청해 주세요.");
      navigate("/login")
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

return (
  <main className="register-page">
    <header className="register-brand">
      <div className="register-logo">+</div>
      <div>
        <strong>ER-LINK</strong>
        <span>응급 환자 수용 관제 플랫폼</span>
      </div>
    </header>

    <section className="register-card">
      <h1>회원가입</h1>
      <p className="register-sub">
        ER-LINK에서 사용할 계정 정보를 입력하세요.
      </p>

      <form onSubmit={handleSubmit}>
        <label className="register-field">
          <span>아이디</span>
          <input value={userid} onChange={(event) => setUserid(event.target.value)} placeholder="사용할 아이디 입력" autoComplete="username" required/>
        </label>

        <label className="register-field">
          <span>비밀번호</span>
          <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="8자 이상 입력" autoComplete="new-password" required/>
        </label>

        <label className="register-field">
          <span>비밀번호 확인</span>
          <input type="password" value={passwordConfirm} onChange={(event) => setPasswordConfirm(event.target.value)} placeholder="비밀번호 다시 입력" autoComplete="new-password" required/>
        </label>

        {message && (
          <p className={isSuccess ? "register-success" : "register-error"}>
            {message}
          </p>
        )}

        <button className="register-submit" type="submit" disabled={loading}>
          {loading ? "가입 중..." : "회원가입"}
        </button>
      </form>

      <div className="register-login">
        이미 계정이 있나요?
        <button type="button" onClick={() => navigate("/login")}>로그인</button>
      </div>
    </section>
  </main>
);
}