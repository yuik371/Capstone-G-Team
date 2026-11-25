import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Login from "./pages/Login";
import Register from "./pages/Register";
import AccountLink from "./pages/AccountLink";
import Hospital from "./pages/Hospital";
import Admin from "./pages/Admin";

const VITE_SERVER_URL = import.meta.env.VITE_SERVER_URL


function HospitalRoute({ children }) {
  const token = sessionStorage.getItem("access_token");
  const [status, setStatus] = useState("checking");

  useEffect(() => {
    if (!token) {
      setStatus("unauthorized");
      return;
    }

    fetch(`${VITE_SERVER_URL}/auth/me`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error("사용자 정보를 확인할 수 없습니다.");
        }
        return response.json();
      })
      .then((user) => {
        if (user.role==="hospital") setStatus("allowed");
        else if (user.role === "admin") setStatus("admin");
        else setStatus("forbidden")
      })
      .catch(() => {
        setStatus("unauthorized");
      });
  }, [token]);

  if (status === "checking") return <p>확인 중...</p>;
  if (status === "unauthorized") return <Navigate to="/login" replace />;
  if (status === "admin") return <Navigate to="/admin" replace />;
  if (status === "forbidden") return <Navigate to="/login" replace />;

  return children;
}

function AdminRoute({ children }) {
  const token = sessionStorage.getItem("access_token");
  const [status, setStatus] = useState("checking");

  useEffect(() => {
    if (!token) {
      setStatus("unauthorized");
      return;
    }

    fetch(`${VITE_SERVER_URL}/auth/me`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
  })
  .then((response) => {
    if(!response.ok){
      throw new Error("사용자 정보를 확인할 수 없습니다,");
    }
    return response.json();
  })
  .then((user) => {
    setStatus(user.role === "admin"? "authorized" : "unauthorized");
  })
  .catch(()=> setStatus("unauthorized"));
  }, [token]);
  if(status === "checking") return <p>확인 중...</p>
  if(status === "unauthorized") return <Navigate to="/login" replace />;

  return children;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<Login />} />
        <Route path="/hospital" element={<HospitalRoute><Hospital/></HospitalRoute>}/>
        <Route path="/register" element={<Register />} />
        <Route path="/account-link" element={<AccountLink />} />
        <Route path="/admin" element={<AdminRoute> <Admin /> </AdminRoute>}/>
      </Routes>
    </BrowserRouter>
  );
}