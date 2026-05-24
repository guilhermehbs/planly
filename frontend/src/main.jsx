import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  BarChart3,
  BriefcaseBusiness,
  CreditCard,
  Goal,
  LogOut,
  Plus,
  Save,
  Search,
  Shield,
  UserRound,
  WalletCards,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "./api";
import { money, percent, today } from "./formatters";
import {
  chartColors,
  currentMonth,
  debtTypeLabel,
  debtTypeOptions,
  emptyBudget,
  emptyCategory,
  emptyClient,
  emptyDebt,
  emptyExpense,
  emptyIncome,
} from "./constants";
import {
  Brand,
  ChartPanel,
  EmptyState,
  Input,
  Metric,
  MonthFilter,
  PageHeader,
  Select,
  SidebarAlerts,
  Tabs,
  Textarea,
  roleLabel,
} from "./components/common";
import "./styles.css";

function App() {
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState("Carregando...");
  const [spendingAlerts, setSpendingAlerts] = useState([]);

  useEffect(() => {
    api.me().then(setUser).catch(() => {
      setStatus("Entre ou crie sua conta.");
    });
  }, []);

  async function handleAuth(result) {
    setUser(result.user);
    setStatus("Login realizado.");
  }

  async function logout() {
    await api.logout().catch(() => {});
    setUser(null);
    setStatus("Sessao encerrada.");
  }

  if (!user) return <AuthScreen onAuth={handleAuth} status={status} setStatus={setStatus} />;

  return (
    <main className="shell app-shell">
      <aside className="sidebar">
        <Brand />
        <div className="session-card">
          <div className="user-card">
            <strong>{user.name}</strong>
            <span>{roleLabel(user.role)}</span>
            <small>{user.email}</small>
          </div>
          <button className="ghost action-wide logout-button" onClick={logout}><LogOut />Sair</button>
        </div>
        <SidebarAlerts alerts={spendingAlerts} />
      </aside>
      <section className="workspace">
        {user.role === "admin" && <AdminApp status={status} setStatus={setStatus} setSpendingAlerts={setSpendingAlerts} />}
        {user.role === "planner" && <PlannerApp status={status} setStatus={setStatus} setSpendingAlerts={setSpendingAlerts} />}
        {user.role === "client" && <ClientApp user={user} setUser={setUser} status={status} setStatus={setStatus} setSpendingAlerts={setSpendingAlerts} />}
      </section>
    </main>
  );
}

function AuthScreen({ onAuth, status, setStatus }) {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  async function submit(event) {
    event.preventDefault();
    try {
      onAuth(mode === "login" ? await api.login(form) : await api.register(form));
    } catch (error) {
      setStatus(error.message);
    }
  }
  return (
    <main className="auth-page">
      <section className="auth-panel">
        <Brand />
        <h1>{mode === "login" ? "Entrar" : "Criar conta"}</h1>
        <form className="form" onSubmit={submit}>
          {mode === "register" && <Input label="Nome" value={form.name} onChange={(name) => setForm({ ...form, name })} required />}
          <Input label="E-mail" type="email" value={form.email} onChange={(email) => setForm({ ...form, email })} required />
          <Input label="Senha" type="password" value={form.password} onChange={(password) => setForm({ ...form, password })} required />
          <button className="primary" type="submit"><Shield />{mode === "login" ? "Entrar" : "Cadastrar"}</button>
        </form>
        <button className="ghost action-wide" onClick={() => setMode(mode === "login" ? "register" : "login")}>
          {mode === "login" ? "Criar conta" : "Ja tenho conta"}
        </button>
        <div className="status-line">{status}</div>
      </section>
    </main>
  );
}

function AdminApp({ status, setStatus, setSpendingAlerts }) {
  const [users, setUsers] = useState([]);
  const [categories, setCategories] = useState([]);
  async function load() {
    try {
      const [usersData, categoriesData] = await Promise.all([api.listUsers(), api.listGlobalCategories()]);
      setUsers(usersData);
      setCategories(categoriesData);
      setStatus("Administracao atualizada.");
    } catch (error) {
      setStatus(error.message);
    }
  }
  useEffect(() => { load(); }, []);
  useEffect(() => { setSpendingAlerts([]); }, []);
  async function changeRole(userId, role) {
    await api.updateUserRole(userId, role);
    await load();
  }
  async function removeUser(userId) {
    if (!confirm("Excluir este usuario?")) return;
    try {
      await api.deleteUser(userId);
      await load();
      setStatus("Usuario excluido.");
    } catch (error) {
      setStatus(error.message);
    }
  }
  return (
    <>
      <PageHeader title="Administracao" subtitle="Usuarios e categorias globais" status={status} onRefresh={load} />
      <div className="grid two">
        <section className="panel">
          <div className="panel-heading"><h2>Usuarios</h2></div>
          <div className="table-list">
            {users.map((item) => (
              <article className="row-card" key={item.id}>
                <div><strong>{item.name}</strong><span>{item.email}</span></div>
                <div className="row-actions">
                  <select value={item.role} onChange={(event) => changeRole(item.id, event.target.value)}>
                    <option value="client">Cliente</option>
                    <option value="planner">Planejador</option>
                    <option value="admin">Admin</option>
                  </select>
                  <button className="danger compact" onClick={() => removeUser(item.id)}>Excluir</button>
                </div>
              </article>
            ))}
          </div>
        </section>
        <GlobalCategoryManager categories={categories} onChange={load} setStatus={setStatus} />
      </div>
    </>
  );
}

function PlannerApp({ status, setStatus, setSpendingAlerts }) {
  const [clients, setClients] = useState([]);
  const [available, setAvailable] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [clientForm, setClientForm] = useState(emptyClient);
  const [search, setSearch] = useState("");
  const [activeTab, setActiveTab] = useState("dashboard");
  const [month, setMonth] = useState(currentMonth());
  const [globalCategories, setGlobalCategories] = useState([]);
  const [data, setData] = useState({ budgets: [], incomes: [], expenses: [], debts: [], dashboard: null });
  const selectedClient = clients.find((client) => client.id === selectedId) || null;
  const filteredClients = clients.filter((client) => client.name.toLowerCase().includes(search.toLowerCase()));

  async function loadClients() {
    const result = await api.plannerClients();
    setClients(result.assigned);
    setAvailable(result.available);
    setSelectedId((current) => current || result.assigned[0]?.id || null);
  }
  async function loadClientData(clientId = selectedId, selectedMonth = month) {
    if (!clientId) return;
    const [budgets, incomes, expenses, debts, dashboard, categories] = await Promise.all([
      api.listCategories(clientId),
      api.listIncomes(clientId, selectedMonth),
      api.listExpenses(clientId, selectedMonth),
      api.listDebts(clientId, selectedMonth),
      api.dashboard(clientId, selectedMonth),
      api.listGlobalCategories(),
    ]);
    setData({ budgets, incomes, expenses, debts, dashboard });
    setGlobalCategories(categories);
    setSpendingAlerts(dashboard.over_limit_categories || []);
  }
  async function loadAll() {
    try {
      await loadClients();
      await loadClientData();
      setStatus("Dados atualizados.");
    } catch (error) {
      setStatus(error.message);
    }
  }
  useEffect(() => { loadAll(); }, []);
  useEffect(() => {
    if (selectedClient) {
      setClientForm({ name: selectedClient.name || "", email: selectedClient.email || "", phone: selectedClient.phone || "", salary: selectedClient.salary || "", notes: selectedClient.notes || "" });
      loadClientData(selectedClient.id, month).catch((error) => setStatus(error.message));
    }
  }, [selectedId, month]);

  async function saveClient(event) {
    event.preventDefault();
    const payload = { ...clientForm, salary: Number(clientForm.salary || 0) };
    const saved = selectedClient ? await api.updateClient(selectedClient.id, payload) : await api.createClient(payload);
    await loadClients();
    setSelectedId(saved.id);
    setStatus("Cliente salvo.");
  }
  async function assignClient(clientId) {
    const client = await api.assignClient(clientId);
    await loadClients();
    setSelectedId(client.id);
  }
  return (
    <>
      <PageHeader title={selectedClient?.name || "Carteira do planejador"} subtitle="Dashboard mensal por cliente" status={status} onRefresh={loadAll}>
        <MonthFilter month={month} setMonth={setMonth} />
      </PageHeader>
      <div className="planner-grid">
        <section className="panel">
          <div className="search-box"><Search /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar cliente" /></div>
          <div className="stack">
            <button className="primary action-wide" onClick={() => { setSelectedId(null); setClientForm(emptyClient); setActiveTab("profile"); }}><Plus />Novo cliente</button>
            {filteredClients.map((client) => <button className={`client-item ${client.id === selectedId ? "active" : ""}`} key={client.id} onClick={() => setSelectedId(client.id)}><UserRound /><span>{client.name}</span></button>)}
          </div>
          {available.length > 0 && <div className="stack"><h2>Clientes sem planejador</h2>{available.map((client) => <button className="ghost action-wide" key={client.id} onClick={() => assignClient(client.id)}>Assumir {client.name}</button>)}</div>}
        </section>
        <section>
          <Metrics dashboard={data.dashboard} />
          <Tabs active={activeTab} setActive={setActiveTab} tabs={[["dashboard", "Dashboard", BarChart3], ["budgets", "Orcamento", Goal], ["incomes", "Ganhos", WalletCards], ["expenses", "Gastos", CreditCard], ["debts", "Dividas", BriefcaseBusiness], ["categories", "Categorias", Goal], ["profile", "Cliente", UserRound]]} />
          {activeTab === "dashboard" && <PlannerDashboard dashboard={data.dashboard} expenses={data.expenses} debts={data.debts} />}
          {activeTab === "budgets" && <BudgetManager client={selectedClient} budgets={data.budgets} globalCategories={globalCategories} onChange={() => loadClientData()} setStatus={setStatus} />}
          {activeTab === "incomes" && <IncomeManager client={selectedClient} incomes={data.incomes} categories={globalCategories} onChange={() => loadClientData()} setStatus={setStatus} />}
          {activeTab === "expenses" && <ExpenseManager client={selectedClient} categories={globalCategories} expenses={data.expenses} onChange={() => loadClientData()} setStatus={setStatus} canEdit />}
          {activeTab === "debts" && <DebtManager client={selectedClient} categories={globalCategories} debts={data.debts} onChange={() => loadClientData()} setStatus={setStatus} />}
          {activeTab === "categories" && <GlobalCategoryManager categories={globalCategories} onChange={() => loadClientData()} setStatus={setStatus} />}
          {activeTab === "profile" && <ClientProfileForm form={clientForm} setForm={setClientForm} onSubmit={saveClient} />}
        </section>
      </div>
    </>
  );
}

function ClientApp({ user, setUser, status, setStatus, setSpendingAlerts }) {
  const [client, setClient] = useState(user.client);
  const [month, setMonth] = useState(currentMonth());
  const [activeTab, setActiveTab] = useState("dashboard");
  const [globalCategories, setGlobalCategories] = useState([]);
  const [data, setData] = useState({ budgets: [], incomes: [], expenses: [], debts: [], dashboard: null });
  async function load(selectedMonth = month) {
    try {
      const me = await api.me();
      setUser(me);
      setClient(me.client);
      if (me.client) {
        const [budgets, incomes, expenses, debts, dashboard, categories] = await Promise.all([
          api.listCategories(me.client.id),
          api.listIncomes(me.client.id, selectedMonth),
          api.listExpenses(me.client.id, selectedMonth),
          api.listDebts(me.client.id, selectedMonth),
          api.dashboard(me.client.id, selectedMonth),
          api.listGlobalCategories(),
        ]);
        setData({ budgets, incomes, expenses, debts, dashboard });
        setGlobalCategories(categories);
        setSpendingAlerts(dashboard.over_limit_categories || []);
      }
      setStatus("Dados atualizados.");
    } catch (error) {
      setStatus(error.message);
    }
  }
  useEffect(() => { load(); }, []);
  useEffect(() => { load(month); }, [month]);
  return (
    <>
      <PageHeader title="Meu planejamento" subtitle={user.planner ? `Planejador: ${user.planner.name}` : "Sem planejador vinculado"} status={status} onRefresh={() => load()}>
        <MonthFilter month={month} setMonth={setMonth} />
      </PageHeader>
      <Metrics dashboard={data.dashboard} />
      <Tabs active={activeTab} setActive={setActiveTab} tabs={[["dashboard", "Dashboard", BarChart3], ["incomes", "Ganhos", WalletCards], ["expenses", "Gastos", CreditCard], ["debts", "Dividas", BriefcaseBusiness]]} />
      {activeTab === "dashboard" && <ClientDashboard dashboard={data.dashboard} />}
      {activeTab === "incomes" && <IncomeManager client={client} incomes={data.incomes} categories={globalCategories} onChange={() => load()} setStatus={setStatus} />}
      {activeTab === "expenses" && <ExpenseManager client={client} categories={globalCategories} expenses={data.expenses} onChange={() => load()} setStatus={setStatus} />}
      {activeTab === "debts" && <DebtManager client={client} categories={globalCategories} debts={data.debts} onChange={() => load()} setStatus={setStatus} />}
    </>
  );
}

function PlannerDashboard({ dashboard, expenses, debts }) {
  if (!dashboard) return <EmptyState text="Selecione um cliente." />;
  const pieData = dashboard.categories.filter((item) => item.spent > 0).map((item) => ({ name: item.name, value: item.spent }));
  const budgetData = dashboard.categories.map((item) => ({ name: item.name, limite: item.limit, gasto: item.spent, uso: item.used_percent }));
  const debtTotal = debts.reduce((sum, debt) => sum + Number(debt.installment_amount || 0), 0);
  return (
    <div className="dashboard-grid">
      <ChartPanel title="Gastos por categoria">
        {pieData.length ? <ResponsiveContainer width="100%" height={280}><PieChart><Pie data={pieData} dataKey="value" nameKey="name" outerRadius={95} label>{pieData.map((_, i) => <Cell key={i} fill={chartColors[i % chartColors.length]} />)}</Pie><Tooltip formatter={(v) => money(v)} /><Legend /></PieChart></ResponsiveContainer> : <EmptyState text="Sem gastos no mes." />}
      </ChartPanel>
      <ChartPanel title="Limite x gasto">
        <ResponsiveContainer width="100%" height={280}><BarChart data={budgetData}><CartesianGrid strokeDasharray="3 3" stroke="#34343d" /><XAxis dataKey="name" stroke="#a9a3b8" /><YAxis stroke="#a9a3b8" /><Tooltip formatter={(v) => money(v)} /><Legend /><Bar dataKey="limite" fill="#6d28d9" /><Bar dataKey="gasto" fill="#c084fc" /></BarChart></ResponsiveContainer>
      </ChartPanel>
      <ChartPanel title="Gastos por dia">
        <ResponsiveContainer width="100%" height={260}><AreaChart data={dashboard.daily_expenses}><CartesianGrid strokeDasharray="3 3" stroke="#34343d" /><XAxis dataKey="date" stroke="#a9a3b8" /><YAxis stroke="#a9a3b8" /><Tooltip formatter={(v) => money(v)} /><Area type="monotone" dataKey="amount" stroke="#8b5cf6" fill="#8b5cf6" fillOpacity={0.25} /></AreaChart></ResponsiveContainer>
      </ChartPanel>
      <ChartPanel title="Ganhos por categoria">
        <SimpleBarChart data={dashboard.income_by_category || []} dataKey="amount" />
      </ChartPanel>
      <ChartPanel title="Gastos por pagamento">
        <SimplePie data={dashboard.spending_by_payment_method || []} />
      </ChartPanel>
      <ChartPanel title="Dividas por tipo">
        <SimpleBarChart data={dashboard.debts_by_type || dashboard.debts_by_category || []} dataKey="amount" />
      </ChartPanel>
      <ChartPanel title="Dividas por status">
        <SimplePie data={dashboard.debts_by_status || []} />
      </ChartPanel>
      <section className="panel stack">
        <div className="panel-heading"><h2>Ranking de uso</h2></div>
        {budgetData.sort((a, b) => b.uso - a.uso).map((item) => <article className="goal-row" key={item.name}><div className="card-line"><strong>{item.name}</strong><span>{item.uso.toFixed(1)}%</span></div><div className="progress-track"><div style={{ width: `${Math.min(item.uso, 100)}%` }} /></div></article>)}
        <div className="hint">Dividas do mes: {money(debtTotal)}</div>
      </section>
      <section className="panel stack">
        <div className="panel-heading"><h2>Alertas de limite</h2></div>
        {(dashboard.over_limit_categories || []).length === 0 && <EmptyState text="Nenhuma categoria acima do limite." />}
        {(dashboard.over_limit_categories || []).map((item) => <article className="goal-row warning" key={item.id}><div className="card-line"><strong>{item.name}</strong><span>{money(Math.abs(item.remaining))} acima</span></div><div className="goal-meta"><span>{money(item.spent)} gastos</span><span>{money(item.limit)} limite</span></div></article>)}
      </section>
    </div>
  );
}

function ClientDashboard({ dashboard }) {
  if (!dashboard) return <EmptyState text="Sem dados para exibir." />;
  return <div className="dashboard-grid"><section className="panel stack"><div className="panel-heading"><h2>Disponivel por categoria</h2></div>{dashboard.categories.map((category) => <article className={`goal-row ${category.over_limit ? "warning" : ""}`} key={category.id}><div className="card-line"><strong>{category.name}</strong><span>{money(category.remaining)} disponivel</span></div><div className="progress-track"><div style={{ width: `${Math.min(category.used_percent, 100)}%` }} /></div><div className="goal-meta"><span>{money(category.spent)} de {money(category.limit)}</span><span>{percent(category.allocation_percent)}</span></div></article>)}</section><ChartPanel title="Ganhos x gastos"><SimpleBarChart data={[{ name: "Ganhos", amount: dashboard.total_income || 0 }, { name: "Gastos", amount: dashboard.total_spent || 0 }, { name: "Dividas", amount: dashboard.total_debts || 0 }]} dataKey="amount" /></ChartPanel><ChartPanel title="Gastos por pagamento"><SimplePie data={dashboard.spending_by_payment_method || []} /></ChartPanel><section className="panel stack"><div className="panel-heading"><h2>Alertas</h2></div>{(dashboard.over_limit_categories || []).length === 0 && <EmptyState text="Nenhuma categoria acima do limite." />}{(dashboard.over_limit_categories || []).map((item) => <article className="goal-row warning" key={item.id}><strong>{item.name}</strong><span>{money(Math.abs(item.remaining))} acima do limite</span></article>)}</section></div>;
}

function GlobalCategoryManager({ categories, onChange, setStatus }) {
  const [form, setForm] = useState(emptyCategory);
  const [editingId, setEditingId] = useState(null);
  async function submit(event) {
    event.preventDefault();
    try {
      editingId ? await api.updateGlobalCategory(editingId, form) : await api.createGlobalCategory(form);
      setForm(emptyCategory);
      setEditingId(null);
      await onChange();
      setStatus("Categoria global salva.");
    } catch (error) { setStatus(error.message); }
  }
  return <section className="panel"><div className="panel-heading"><h2>Categorias globais</h2></div><form className="form" onSubmit={submit}><Input label="Nome" value={form.name} onChange={(name) => setForm({ ...form, name })} required /><Select label="Tipo" value={form.type} onChange={(type) => setForm({ ...form, type })} options={[["expense", "Gasto"], ["income", "Ganho"], ["both", "Ambos"]]} /><label className="check"><input type="checkbox" checked={form.active} onChange={(event) => setForm({ ...form, active: event.target.checked })} />Ativa</label><button className="primary"><Save />Salvar</button></form><div className="stack">{categories.map((category) => <article className="row-card" key={category.id}><div><strong>{category.name}</strong><span>{category.type} · {category.active ? "ativa" : "inativa"}</span></div><button className="icon-button" onClick={() => { setEditingId(category.id); setForm({ name: category.name, type: category.type, active: Boolean(category.active) }); }}><Save /></button></article>)}</div></section>;
}

function BudgetManager({ client, budgets, globalCategories, onChange, setStatus }) {
  const [form, setForm] = useState(emptyBudget);
  const [editingId, setEditingId] = useState(null);
  if (!client) return <EmptyState text="Selecione um cliente." />;
  const expenseCategories = globalCategories.filter((c) => c.type === "expense" || c.type === "both");
  async function submit(event) {
    event.preventDefault();
    try {
      const payload = { ...form, category_id: Number(form.category_id), allocation_percent: Number(form.allocation_percent || 0), active: Boolean(form.active) };
      editingId ? await api.updateCategory(editingId, payload) : await api.createCategory(client.id, payload);
      setForm(emptyBudget); setEditingId(null); await onChange(); setStatus("Orcamento salvo.");
    } catch (error) { setStatus(error.message); }
  }
  return <div className="grid two"><form className="panel form" onSubmit={submit}><div className="panel-heading"><h2>Percentual por categoria</h2></div><Select label="Categoria" value={form.category_id} onChange={(category_id) => setForm({ ...form, category_id })} options={expenseCategories.map((c) => [c.id, c.name])} /><Input label="% dos ganhos" type="number" value={form.allocation_percent} onChange={(allocation_percent) => setForm({ ...form, allocation_percent })} /><label className="check"><input type="checkbox" checked={form.active} onChange={(event) => setForm({ ...form, active: event.target.checked })} />Ativa</label><button className="primary"><Save />Salvar</button></form><section className="panel stack"><div className="panel-heading"><h2>Orcamento do cliente</h2></div>{budgets.map((budget) => <article className="row-card" key={budget.id}><div><strong>{budget.name}</strong><span>{percent(budget.allocation_percent)} · {budget.active ? "ativa" : "inativa"}</span></div><button className="icon-button" onClick={() => { setEditingId(budget.id); setForm({ category_id: budget.category_id, allocation_percent: budget.allocation_percent, active: Boolean(budget.active) }); }}><Save /></button></article>)}</section></div>;
}

function IncomeManager({ client, incomes, categories, onChange, setStatus }) {
  const [form, setForm] = useState(emptyIncome);
  const [editingId, setEditingId] = useState(null);
  const incomeCategories = categories.filter((c) => c.type === "income" || c.type === "both");
  if (!client) return <EmptyState text="Selecione um cliente." />;
  async function submit(event) {
    event.preventDefault();
    try {
      const payload = { ...form, category_id: Number(form.category_id), amount: Number(form.amount || 0) };
      editingId ? await api.updateIncome(editingId, payload) : await api.createIncome(client.id, payload);
      setForm(emptyIncome);
      setEditingId(null);
      await onChange();
      setStatus("Ganho salvo.");
    } catch (error) { setStatus(error.message); }
  }
  function editIncome(income) {
    setEditingId(income.id);
    setForm({
      income_date: income.income_date,
      amount: income.amount,
      category_id: income.category_id,
      description: income.description || "",
    });
  }
  async function removeIncome(id) {
    if (!confirm("Excluir este ganho?")) return;
    try {
      await api.deleteIncome(id);
      await onChange();
      setStatus("Ganho excluido.");
    } catch (error) {
      setStatus(error.message);
    }
  }
  return <div className="grid two"><form className="panel form" onSubmit={submit}><div className="panel-heading"><h2>{editingId ? "Editar ganho" : "Novo ganho"}</h2></div><Input label="Data" type="date" value={form.income_date} onChange={(income_date) => setForm({ ...form, income_date })} /><Input label="Valor" type="number" value={form.amount} onChange={(amount) => setForm({ ...form, amount })} /><Select label="Categoria" value={form.category_id} onChange={(category_id) => setForm({ ...form, category_id })} options={incomeCategories.map((c) => [c.id, c.name])} /><Textarea label="Descricao" value={form.description} onChange={(description) => setForm({ ...form, description })} /><div className="button-row"><button className="primary"><Save />Salvar ganho</button>{editingId && <button className="ghost" type="button" onClick={() => { setEditingId(null); setForm(emptyIncome); }}>Cancelar</button>}</div></form><section className="panel stack"><div className="panel-heading"><h2>Ganhos do mes</h2></div>{incomes.map((income) => <article className="row-card" key={income.id}><div><strong>{money(income.amount)} - {income.category_name}</strong><span>{income.income_date}</span><small>{income.description}</small></div><div className="row-actions"><button className="icon-button" onClick={() => editIncome(income)}><Save /></button><button className="danger compact" onClick={() => removeIncome(income.id)}>Excluir</button></div></article>)}</section></div>;
}

function ExpenseManager({ client, categories, expenses, onChange, setStatus, canEdit = false }) {
  const [form, setForm] = useState(emptyExpense);
  const [editingId, setEditingId] = useState(null);
  const expenseCategories = categories.filter((c) => c.type === "expense" || c.type === "both");
  if (!client) return <EmptyState text="Selecione um cliente." />;
  async function submit(event) {
    event.preventDefault();
    const payload = { ...form, amount: Number(form.amount || 0), category_id: Number(form.category_id), installments: Number(form.installments || 1) };
    try {
      editingId ? await api.updateExpense(editingId, payload) : await api.createExpense(client.id, payload);
      setForm(emptyExpense); setEditingId(null); await onChange(); setStatus("Gasto salvo.");
    } catch (error) { setStatus(error.message); }
  }
  function edit(expense) {
    setEditingId(expense.id);
    setForm({ expense_date: expense.expense_date, amount: expense.original_amount || expense.amount, category_id: expense.global_category_id || expense.category_id, payment_method: expense.payment_method, installments: expense.installments, description: expense.description || "" });
  }
  async function removeExpense(id) {
    if (!confirm("Excluir este gasto e suas parcelas?")) return;
    try {
      await api.deleteExpense(id);
      await onChange();
      setStatus("Gasto excluido.");
    } catch (error) {
      setStatus(error.message);
    }
  }
  return <div className="grid two"><form className="panel form" onSubmit={submit}><div className="panel-heading"><h2>{editingId ? "Editar gasto" : "Novo gasto"}</h2></div><Input label="Data" type="date" value={form.expense_date} onChange={(expense_date) => setForm({ ...form, expense_date })} /><Input label="Valor total" type="number" value={form.amount} onChange={(amount) => setForm({ ...form, amount })} /><Select label="Categoria" value={form.category_id} onChange={(category_id) => setForm({ ...form, category_id })} options={expenseCategories.map((c) => [c.id, c.name])} /><Select label="Modo de pagamento" value={form.payment_method} onChange={(payment_method) => setForm({ ...form, payment_method })} options={[["pix", "Pix"], ["debito", "Debito"], ["credito", "Credito"], ["dinheiro", "Dinheiro"]]} />{form.payment_method === "credito" && <Input label="Parcelas" type="number" value={form.installments} onChange={(installments) => setForm({ ...form, installments })} />}<Textarea label="Descricao" value={form.description} onChange={(description) => setForm({ ...form, description })} /><button className="primary"><Save />Salvar gasto</button></form><section className="panel stack"><div className="panel-heading"><h2>Gastos do mes</h2></div>{expenses.map((expense) => <article className="row-card" key={expense.installment_id || expense.id}><div><strong>{money(expense.installment_amount || expense.amount)} - {expense.category_name}</strong><span>{expense.installment_date || expense.expense_date} · parcela {expense.installment_number || 1}/{expense.installments_total || expense.installments}</span><small>{expense.description}</small></div><div className="row-actions">{canEdit && <button className="icon-button" onClick={() => edit(expense)}><Save /></button>}<button className="danger compact" onClick={() => removeExpense(expense.id)}>Excluir</button></div></article>)}</section></div>;
}

function SimplePie({ data }) {
  if (!data.length) return <EmptyState text="Sem dados no mes." />;
  return <ResponsiveContainer width="100%" height={260}><PieChart><Pie data={data} dataKey="amount" nameKey="name" outerRadius={90} label>{data.map((_, i) => <Cell key={i} fill={chartColors[i % chartColors.length]} />)}</Pie><Tooltip formatter={(v) => money(v)} /><Legend /></PieChart></ResponsiveContainer>;
}

function SimpleBarChart({ data, dataKey }) {
  if (!data.length) return <EmptyState text="Sem dados no mes." />;
  return <ResponsiveContainer width="100%" height={260}><BarChart data={data}><CartesianGrid strokeDasharray="3 3" stroke="#34343d" /><XAxis dataKey="name" stroke="#a9a3b8" /><YAxis stroke="#a9a3b8" /><Tooltip formatter={(v) => money(v)} /><Bar dataKey={dataKey} fill="#8b5cf6" /></BarChart></ResponsiveContainer>;
}

function DebtManager({ client, categories, debts, onChange, setStatus }) {
  const [form, setForm] = useState(emptyDebt);
  const [editingId, setEditingId] = useState(null);
  if (!client) return <EmptyState text="Selecione um cliente." />;
  async function submit(event) {
    event.preventDefault();
    try {
      const payload = {
        ...form,
        original_amount: Number(form.original_amount || 0),
        current_amount: Number(form.current_amount || 0),
        interest_rate: Number(form.interest_rate || 0),
        installments: Number(form.installments || 1),
        paid_installments: Number(form.paid_installments || 0),
      };
      editingId ? await api.updateDebt(editingId, payload) : await api.createDebt(client.id, payload);
      setForm(emptyDebt);
      setEditingId(null);
      await onChange();
      setStatus("Divida salva.");
    } catch (error) { setStatus(error.message); }
  }
  function editDebt(debt) {
    setEditingId(debt.id);
    setForm({
      title: debt.title || "",
      description: debt.description || "",
      original_amount: debt.original_amount || debt.total_amount || "",
      current_amount: debt.current_amount || debt.total_amount || "",
      interest_rate: debt.interest_rate || "",
      installments: debt.installments || 1,
      due_date: debt.due_date || today(),
      debt_type: debt.debt_type || "outro",
      creditor: debt.creditor || "",
      paid_installments: debt.paid_installments || 0,
      status: debt.status || "open",
    });
  }
  return <div className="grid two"><form className="panel form" onSubmit={submit}><div className="panel-heading"><h2>{editingId ? "Editar divida" : "Nova divida"}</h2></div><Input label="Titulo" value={form.title} onChange={(title) => setForm({ ...form, title })} required /><Textarea label="Descricao" value={form.description} onChange={(description) => setForm({ ...form, description })} required /><div className="form-grid"><Input label="Valor original da divida" type="number" value={form.original_amount} onChange={(original_amount) => setForm({ ...form, original_amount })} /><Input label="Valor a pagar atualmente" type="number" value={form.current_amount} onChange={(current_amount) => setForm({ ...form, current_amount })} /><Input label="Taxa de juros (%)" type="number" value={form.interest_rate} onChange={(interest_rate) => setForm({ ...form, interest_rate })} /><Input label="Parcelas" type="number" value={form.installments} onChange={(installments) => setForm({ ...form, installments })} /><Input label="Primeiro vencimento" type="date" value={form.due_date} onChange={(due_date) => setForm({ ...form, due_date })} /><Input label="Parcelas pagas" type="number" value={form.paid_installments} onChange={(paid_installments) => setForm({ ...form, paid_installments })} /></div><Select label="Tipo de divida" value={form.debt_type} onChange={(debt_type) => setForm({ ...form, debt_type })} options={debtTypeOptions()} /><Input label="Credor" value={form.creditor} onChange={(creditor) => setForm({ ...form, creditor })} /><Select label="Status" value={form.status} onChange={(status) => setForm({ ...form, status })} options={[["open", "Aberta"], ["paid", "Paga"], ["late", "Atrasada"]]} /><div className="button-row"><button className="primary"><Save />Salvar divida</button>{editingId && <button className="ghost" type="button" onClick={() => { setEditingId(null); setForm(emptyDebt); }}>Cancelar</button>}</div></form><section className="panel stack"><div className="panel-heading"><h2>Dividas do mes</h2></div>{debts.map((debt) => <article className="row-card" key={debt.installment_id || debt.id}><div><strong>{debt.title || debt.description}</strong><span>{debtTypeLabel(debt.debt_type)} · {money(debt.installment_amount || debt.current_amount || debt.total_amount)} · parcela {debt.installment_number || 1}/{debt.installments_total || debt.installments}</span><small>{debt.creditor ? `${debt.creditor} · ` : ""}{debt.installment_due_date || debt.due_date}</small></div><button className="icon-button" onClick={() => editDebt(debt)}><Save /></button></article>)}</section></div>;
}

function ClientProfileForm({ form, setForm, onSubmit }) {
  return <form className="panel form" onSubmit={onSubmit}><div className="panel-heading"><h2>Dados do cliente</h2></div><Input label="Nome" value={form.name} onChange={(name) => setForm({ ...form, name })} required /><div className="form-grid"><Input label="E-mail" value={form.email} onChange={(email) => setForm({ ...form, email })} /><Input label="Telefone" value={form.phone} onChange={(phone) => setForm({ ...form, phone })} /></div><Textarea label="Observacoes" value={form.notes} onChange={(notes) => setForm({ ...form, notes })} /><button className="primary"><Save />Salvar cliente</button></form>;
}

function Metrics({ dashboard }) {
  const categories = dashboard?.categories || [];
  const totalLimit = categories.reduce((sum, item) => sum + item.limit, 0);
  const totalRemaining = categories.reduce((sum, item) => sum + item.remaining, 0);
  return <section className="metrics"><Metric icon={<WalletCards />} label="Ganhos do mes" value={money(dashboard?.total_income || 0)} /><Metric icon={<Goal />} label="Limite planejado" value={money(totalLimit)} /><Metric icon={<CreditCard />} label="Gasto no mes" value={money(dashboard?.total_spent || 0)} /><Metric icon={<BarChart3 />} label="Disponivel" value={money(totalRemaining)} /></section>;
}

createRoot(document.getElementById("root")).render(<App />);
