import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";

import AppLayout from "./layout/AppLayout.jsx";
import DashboardHome from "./pages/DashboardHome.jsx";
import Feature1Forecast from "./pages/Feature1Forecast.jsx";
import Feature2Inventory from "./pages/Feature2Inventory.jsx";
import Feature3Suppliers from "./pages/Feature3Suppliers.jsx";
import Feature4Regions from "./pages/Feature4Regions.jsx";
import Feature5Promotions from "./pages/Feature5Promotions.jsx";

import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<DashboardHome />} />
          <Route path="/forecast" element={<Feature1Forecast />} />
          <Route path="/inventory" element={<Feature2Inventory />} />
          <Route path="/suppliers" element={<Feature3Suppliers />} />
          <Route path="/regions" element={<Feature4Regions />} />
          <Route path="/promotions" element={<Feature5Promotions />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
