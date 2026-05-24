import React from "react";
import { RefreshCw, WalletCards } from "lucide-react";
import { money } from "../formatters";

export function PageHeader({ title, subtitle, status, onRefresh, children }) {
  return (
    <>
      <header className="topbar">
        <div>
          <span className="eyebrow">{subtitle}</span>
          <h1>{title}</h1>
        </div>
        <div className="top-actions">
          {children}
          <button className="ghost" onClick={onRefresh}><RefreshCw />Atualizar</button>
        </div>
      </header>
      <div className="status-line">{status}</div>
    </>
  );
}

export function MonthFilter({ month, setMonth }) {
  const [year, selectedMonth] = month.split("-");
  const currentYear = new Date().getFullYear();
  const years = Array.from({ length: 8 }, (_, index) => currentYear - 5 + index);
  const months = [
    ["01", "Janeiro"],
    ["02", "Fevereiro"],
    ["03", "Marco"],
    ["04", "Abril"],
    ["05", "Maio"],
    ["06", "Junho"],
    ["07", "Julho"],
    ["08", "Agosto"],
    ["09", "Setembro"],
    ["10", "Outubro"],
    ["11", "Novembro"],
    ["12", "Dezembro"],
  ];

  function update(nextYear, nextMonth) {
    setMonth(`${nextYear}-${nextMonth}`);
  }

  return (
    <div className="month-filter">
      <label>
        <span>Mes</span>
        <select value={selectedMonth} onChange={(event) => update(year, event.target.value)}>
          {months.map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </label>
      <label>
        <span>Ano</span>
        <select value={year} onChange={(event) => update(event.target.value, selectedMonth)}>
          {years.map((item) => (
            <option key={item} value={item}>{item}</option>
          ))}
        </select>
      </label>
    </div>
  );
}

export function Tabs({ active, setActive, tabs }) {
  return <nav className="tabs">{tabs.map(([id, label, Icon]) => <button className={`tab ${active === id ? "active" : ""}`} key={id} onClick={() => setActive(id)}><Icon />{label}</button>)}</nav>;
}

export function ChartPanel({ title, children }) {
  return <section className="panel chart-panel"><div className="panel-heading"><h2>{title}</h2></div>{children}</section>;
}

export function Metric({ icon, label, value }) {
  return <article className="metric"><div className="metric-icon">{icon}</div><span>{label}</span><strong>{value}</strong></article>;
}

export function Brand() {
  return <div className="brand"><div className="brand-mark"><WalletCards /></div><div><strong>Planly</strong><span>Planejamento financeiro</span></div></div>;
}

export function SidebarAlerts({ alerts }) {
  return <section className="sidebar-alerts"><strong>Alertas de gastos</strong>{!alerts.length && <span>Nenhum limite estourado.</span>}{alerts.slice(0, 4).map((alert) => <article key={alert.id}><span>{alert.name}</span><small>{money(Math.abs(alert.remaining))} acima</small></article>)}</section>;
}

export function Input({ label, value, onChange, type = "text", required = false }) {
  return <label className="field"><span>{label}</span><input type={type} value={value} onChange={(event) => onChange(event.target.value)} required={required} step={type === "number" ? "0.01" : undefined} /></label>;
}

export function Select({ label, value, onChange, options, optional = false }) {
  return <label className="field"><span>{label}</span><select value={value} onChange={(event) => onChange(event.target.value)} required={!optional}>{optional && <option value="">Sem categoria</option>} {!optional && <option value="">Selecione</option>}{options.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>;
}

export function Textarea({ label, value, onChange, required = false }) {
  return <label className="field"><span>{label}</span><textarea value={value} onChange={(event) => onChange(event.target.value)} required={required} /></label>;
}

export function EmptyState({ text }) {
  return <div className="empty">{text}</div>;
}

export function roleLabel(role) {
  return { admin: "Administrador", planner: "Planejador", client: "Cliente" }[role] || role;
}
