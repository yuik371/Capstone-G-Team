import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Login from "./pages/Login";
import Hospital from "./pages/hospital";

function ProtectedRoute({ children }) {
  const token = sessionStorage.getItem("access_token");
  console.log("ProtectedRoute 실행, 토큰 있음:", Boolean(token));
  return token ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/hospital"
          element={
            <ProtectedRoute>
              <Hospital />
            </ProtectedRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}