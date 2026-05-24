from backend.serializers import rows_to_dicts


def build_dashboard(db, client_id, month):
    categories = rows_to_dicts(db.list_categories(client_id, include_inactive=False))
    expenses = rows_to_dicts(db.list_expenses(client_id, month))
    incomes = rows_to_dicts(db.list_incomes(client_id, month))
    debts = rows_to_dicts(db.list_debts(client_id, month))
    total_income = sum(income["amount"] for income in incomes)

    spent_by_category = {}
    spent_by_payment = {}
    for expense in expenses:
        category_id = expense["global_category_id"] or expense["category_id"]
        spent_by_category[category_id] = spent_by_category.get(category_id, 0) + expense["installment_amount"]
        spent_by_payment[expense["payment_method"]] = spent_by_payment.get(expense["payment_method"], 0) + expense["installment_amount"]

    income_by_category = {}
    for income in incomes:
        income_by_category[income["category_name"]] = income_by_category.get(income["category_name"], 0) + income["amount"]

    debts_by_type = {}
    debts_by_status = {}
    for debt in debts:
        debt_type = debt["debt_type"] or "outro"
        debts_by_type[debt_type] = debts_by_type.get(debt_type, 0) + debt["installment_amount"]
        status = debt["installment_status"] or debt["status"]
        debts_by_status[status] = debts_by_status.get(status, 0) + debt["installment_amount"]

    items = []
    for category in categories:
        limit = total_income * category["allocation_percent"] / 100
        spent = spent_by_category.get(category["category_id"], 0)
        items.append(
            {
                **category,
                "limit": limit,
                "spent": spent,
                "remaining": limit - spent,
                "used_percent": min(spent / limit * 100, 100) if limit > 0 else 0,
                "over_limit": spent > limit if limit > 0 else spent > 0,
            }
        )

    daily = {}
    for expense in expenses:
        day = expense["installment_date"]
        daily[day] = daily.get(day, 0) + expense["installment_amount"]

    return {
        "month": month,
        "salary": total_income,
        "total_income": total_income,
        "categories": items,
        "total_spent": sum(expense["installment_amount"] for expense in expenses),
        "total_debts": sum(debt["installment_amount"] for debt in debts if debt["installment_status"] != "paid"),
        "total_available": sum(item["remaining"] for item in items),
        "over_limit_categories": [item for item in items if item["over_limit"]],
        "income_by_category": [{"name": key, "amount": value} for key, value in sorted(income_by_category.items())],
        "spending_by_payment_method": [{"name": key, "amount": value} for key, value in sorted(spent_by_payment.items())],
        "debts_by_category": [{"name": key, "amount": value} for key, value in sorted(debts_by_type.items())],
        "debts_by_type": [{"name": key, "amount": value} for key, value in sorted(debts_by_type.items())],
        "debts_by_status": [{"name": key, "amount": value} for key, value in sorted(debts_by_status.items())],
        "daily_expenses": [{"date": key, "amount": daily[key]} for key in sorted(daily)],
    }
