const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api";
let csrfToken = "";

async function request(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const headers = {
    "Content-Type": "application/json",
    ...(csrfToken && method !== "GET" ? { "X-CSRF-Token": csrfToken } : {}),
    ...(options.headers || {}),
  };
  const response = await fetch(`${API_URL}${path}`, {
    credentials: "include",
    headers,
    ...options,
  });

  const data = await response.json().catch(() => ({}));
  if (data.csrfToken) {
    csrfToken = data.csrfToken;
  }
  if (!response.ok) {
    throw new Error(data.error || "Erro ao comunicar com a API.");
  }
  return data;
}

function unwrapAuth(data) {
  return data.user || data;
}

export const api = {
  login: (payload) => request("/auth/login", { method: "POST", body: JSON.stringify(payload) }),
  register: (payload) => request("/auth/register", { method: "POST", body: JSON.stringify(payload) }),
  logout: () => request("/auth/logout", { method: "POST" }),
  me: () => request("/me").then(unwrapAuth),
  listUsers: () => request("/admin/users"),
  updateUserRole: (id, role) => request(`/admin/users/${id}/role`, { method: "PUT", body: JSON.stringify({ role }) }),
  deleteUser: (id) => request(`/admin/users/${id}`, { method: "DELETE" }),
  listGlobalCategories: (type) => request(`/categories${type ? `?type=${type}` : ""}`),
  createGlobalCategory: (payload) => request("/categories", { method: "POST", body: JSON.stringify(payload) }),
  updateGlobalCategory: (id, payload) => request(`/categories/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteGlobalCategory: (id) => request(`/categories/${id}`, { method: "DELETE" }),
  plannerClients: () => request("/planner/clients"),
  assignClient: (id) => request(`/planner/clients/${id}/assign`, { method: "POST" }),
  listClients: () => request("/clients"),
  createClient: (payload) => request("/clients", { method: "POST", body: JSON.stringify(payload) }),
  updateClient: (id, payload) => request(`/clients/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteClient: (id) => request(`/clients/${id}`, { method: "DELETE" }),
  listMeetings: (clientId) => request(`/clients/${clientId}/meetings`),
  createMeeting: (clientId, payload) =>
    request(`/clients/${clientId}/meetings`, { method: "POST", body: JSON.stringify(payload) }),
  deleteMeeting: (id) => request(`/meetings/${id}`, { method: "DELETE" }),
  listGoals: (clientId) => request(`/clients/${clientId}/goals`),
  createGoal: (clientId, payload) => request(`/clients/${clientId}/goals`, { method: "POST", body: JSON.stringify(payload) }),
  updateGoal: (id, payload) => request(`/goals/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteGoal: (id) => request(`/goals/${id}`, { method: "DELETE" }),
  getReport: (clientId) => request(`/clients/${clientId}/report`),
  getReportFile: (clientId) => request(`/clients/${clientId}/report?format=text`),
  listCategories: (clientId) => request(`/clients/${clientId}/budgets`),
  createCategory: (clientId, payload) =>
    request(`/clients/${clientId}/budgets`, { method: "POST", body: JSON.stringify(payload) }),
  updateCategory: (id, payload) => request(`/client-budgets/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteCategory: (id) => request(`/client-budgets/${id}`, { method: "DELETE" }),
  listIncomes: (clientId, month) => request(`/clients/${clientId}/incomes${month ? `?month=${month}` : ""}`),
  createIncome: (clientId, payload) => request(`/clients/${clientId}/incomes`, { method: "POST", body: JSON.stringify(payload) }),
  updateIncome: (id, payload) => request(`/incomes/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteIncome: (id) => request(`/incomes/${id}`, { method: "DELETE" }),
  listExpenses: (clientId, month) => request(`/clients/${clientId}/expenses${month ? `?month=${month}` : ""}`),
  createExpense: (clientId, payload) =>
    request(`/clients/${clientId}/expenses`, { method: "POST", body: JSON.stringify(payload) }),
  updateExpense: (id, payload) => request(`/expenses/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteExpense: (id) => request(`/expenses/${id}`, { method: "DELETE" }),
  listDebts: (clientId, month) => request(`/clients/${clientId}/debts${month ? `?month=${month}` : ""}`),
  createDebt: (clientId, payload) => request(`/clients/${clientId}/debts`, { method: "POST", body: JSON.stringify(payload) }),
  updateDebt: (id, payload) => request(`/debts/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteDebt: (id) => request(`/debts/${id}`, { method: "DELETE" }),
  dashboard: (clientId, month) => request(`/clients/${clientId}/dashboard${month ? `?month=${month}` : ""}`),
  updateSalary: (salary) => request("/client/salary", { method: "PUT", body: JSON.stringify({ salary }) }),
};
