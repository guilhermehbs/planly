import { today } from "./formatters";

export const chartColors = ["#8b5cf6", "#c084fc", "#22d3ee", "#34d399", "#f59e0b", "#f472b6", "#a3e635"];
export const currentMonth = () => today().slice(0, 7);

export const emptyClient = { name: "", email: "", phone: "", salary: "", notes: "" };
export const emptyCategory = { name: "", type: "expense", active: true };
export const emptyBudget = { category_id: "", allocation_percent: "", active: true };
export const emptyIncome = { income_date: today(), amount: "", category_id: "", description: "" };
export const emptyExpense = { expense_date: today(), amount: "", category_id: "", payment_method: "pix", installments: 1, description: "" };
export const emptyDebt = {
  title: "",
  description: "",
  original_amount: "",
  current_amount: "",
  interest_rate: "",
  installments: 1,
  due_date: today(),
  debt_type: "cartao_credito",
  creditor: "",
  paid_installments: 0,
  status: "open",
};

export function debtTypeOptions() {
  return [
    ["cartao_credito", "Cartao de credito"],
    ["financiamento", "Financiamento"],
    ["emprestimo", "Emprestimo"],
    ["cheque_especial", "Cheque especial"],
    ["parcelamento", "Parcelamento"],
    ["consignado", "Consignado"],
    ["outro", "Outro"],
  ];
}

export function debtTypeLabel(value) {
  return Object.fromEntries(debtTypeOptions())[value] || "Outro";
}
