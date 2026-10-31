import { Route, Routes } from "react-router-dom";
import BrightloopIntro from "./pages/BrightloopIntro";
import Login from "./pages/Login";
import Landing from "./pages/Landing";

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<BrightloopIntro />} />
      <Route path="/login" element={<Login />} />
      <Route path="/status" element={<Landing />} />
      <Route path="*" element={<BrightloopIntro />} />
    </Routes>
  );
}
