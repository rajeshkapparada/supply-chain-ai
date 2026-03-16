import { NavLink, Outlet, useLocation } from "react-router-dom";
import "./layout.css";

const MENU = [
  { to: "/", title: "Dashboard", sub: "Overview" },
  { to: "/forecast", title: "Feature 1: Forecasting", sub: "Demand models" },
  { to: "/inventory", title: "Feature 2: Inventory", sub: "Reorder decisions" },
  { to: "/suppliers", title: "Feature 3: Suppliers", sub: "Reliability score" },
  { to: "/regions", title: "Feature 4: Regions", sub: "Demand by region" },
  { to: "/promotions", title: "Feature 5: Promotions", sub: "Promo analytics" },
];

export default function AppLayout() {
  const location = useLocation();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-logo">SC</div>
          <div>
            <div className="brand-title">SupplyChain AI</div>
            <div className="brand-sub">Inventory Intelligence</div>
          </div>
        </div>

        <div className="menu-label">Navigation</div>

        <nav className="menu-list">
          {MENU.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `menu-item${isActive ? " menu-item-active" : ""}`
              }
            >
              <div className="menu-item-title">{item.title}</div>
              <div className="menu-item-sub">{item.sub}</div>
            </NavLink>
          ))}
        </nav>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div>
            <div className="topbar-title">Agentic Supply Chain Dashboard</div>
            <div className="topbar-sub">Current route: {location.pathname}</div>
          </div>
        </header>

        <section className="page-content">
          <Outlet />
        </section>
      </main>
    </div>
  );
}
