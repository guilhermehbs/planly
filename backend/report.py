from core.formatters import br_money


def build_client_report(client, meetings, goals):
    total_target = sum(goal["target_amount"] for goal in goals)
    total_current = sum(goal["current_amount"] for goal in goals)
    total_monthly = sum(goal["monthly_contribution"] for goal in goals)
    total_percent = sum(goal["allocation_percent"] for goal in goals)

    lines = [
        f"Cliente: {client['name']}",
        f"E-mail: {client['email'] or '-'}",
        f"Telefone: {client['phone'] or '-'}",
        "",
        "Observacoes gerais:",
        client["notes"] or "-",
        "",
        "Resumo financeiro:",
        f"Valor total planejado: {br_money(total_target)}",
        f"Valor ja acumulado: {br_money(total_current)}",
        f"Aporte mensal planejado: {br_money(total_monthly)}",
        f"Percentual total alocado: {total_percent:.2f}%",
        "",
        "Metas e onde guardar:",
    ]

    if not goals:
        lines.append("- Nenhuma meta cadastrada.")

    for goal in goals:
        progress = 0 if goal["target_amount"] <= 0 else min(goal["current_amount"] / goal["target_amount"] * 100, 100)
        lines.extend(
            [
                f"- {goal['name']}",
                f"  Alvo: {br_money(goal['target_amount'])}",
                f"  Atual: {br_money(goal['current_amount'])} ({progress:.1f}%)",
                f"  Aporte mensal: {br_money(goal['monthly_contribution'])}",
                f"  Percentual: {goal['allocation_percent']:.2f}%",
                f"  Onde guardar: {goal['money_place'] or '-'}",
                f"  Prazo: {goal['deadline'] or '-'}",
                f"  Observacoes: {goal['notes'] or '-'}",
            ]
        )

    lines.extend(["", "Historico de reunioes:"])
    if not meetings:
        lines.append("- Nenhuma reuniao cadastrada.")

    for meeting in meetings:
        lines.extend(
            [
                f"- {meeting['meeting_date']}",
                f"  Resumo: {meeting['summary']}",
                f"  Avancos: {meeting['progress'] or '-'}",
                f"  Proximos passos: {meeting['next_steps'] or '-'}",
            ]
        )

    return "\n".join(lines)
