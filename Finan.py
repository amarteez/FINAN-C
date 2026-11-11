
import streamlit as st

st.set_page_config(
    page_title="Flujo Quincenal",
    page_icon="💰",
    layout="wide"
)

# Custom CSS styling
st.markdown("""
<style>
.stApp {
    background: #0e1525;
    color: #ffffff;
}
[data-testid="stSidebar"] {
    background: #172033;
}
[data-testid="stMetric"] {
    background: #1b2940;
    padding: 18px;
    border-radius: 12px;
    border: 1px solid #33445f;
}
[data-testid="stMetricLabel"] {
    color: #aab8cc;
}
[data-testid="stMetricValue"] {
    color: #ffffff;
}
h1, h2, h3 {
    color: #ffffff;
}
</style>
""", unsafe_allow_html=True)

# Initialize session data
if "expenses" not in st.session_state:
    defaults = {
        "Universidad": 100.0,
        "Pasaje": 75.0,
        "Comida": 25.0,
        "Préstamo BG": 80.0,
        "TC BAC (PS5 + Cámara)": 60.0,
        "TC Banistmo": 30.0,
        "Internet": 20.0,
        "Data": 20.0,
        "Spotify": 13.0,
    }

    st.session_state.expenses = [
        {"id": i, "name": name, "amount": amount}
        for i, (name, amount) in enumerate(defaults.items())
    ]

    st.session_state.next_id = len(defaults)

if "income" not in st.session_state:
    st.session_state.income = 618.0

st.title("💰 Flujo Quincenal")
st.caption("Panel financiero | 13 de noviembre")

# Sidebar configuration
with st.sidebar:
    st.header("⚙️ Configuración")

    income = st.number_input(
        "Ingreso quincenal ($)",
        min_value=0.0,
        value=618.0,
        step=10.0,
        key="income_input"
    )

    st.divider()
    st.subheader("✏️ Administrar compromisos")

    updated_expenses = []

    # Edit and remove existing expenses
    for expense in st.session_state.expenses:
        expense_id = expense["id"]

        col_name, col_amount, col_delete = st.columns([1.5, 1, 0.45])

        with col_name:
            new_name = st.text_input(
                "Nombre",
                value=expense["name"],
                key=f"name_{expense_id}"
            )

        with col_amount:
            new_amount = st.number_input(
                "Monto ($)",
                min_value=0.0,
                value=float(expense["amount"]),
                step=5.0,
                key=f"amount_{expense_id}"
            )

        with col_delete:
            st.write("")
            if st.button("🗑️", key=f"delete_{expense_id}"):
                st.session_state.expenses = [
                    item for item in st.session_state.expenses
                    if item["id"] != expense_id
                ]
                st.rerun()

        updated_expenses.append({
            "id": expense_id,
            "name": new_name.strip(),
            "amount": new_amount
        })

    st.session_state.expenses = updated_expenses

    # Add new expense
    st.divider()
    st.subheader("➕ Añadir compromiso")

    with st.form("add_expense_form", clear_on_submit=True):
        new_expense_name = st.text_input(
            "Nombre del gasto",
            placeholder="Ej. Seguro del carro"
        )

        new_expense_amount = st.number_input(
            "Monto ($)",
            min_value=0.0,
            value=0.0,
            step=5.0
        )

        add_expense = st.form_submit_button(
            "Añadir gasto",
            use_container_width=True
        )

        if add_expense:
            clean_name = new_expense_name.strip()

            existing_names = [
                item["name"].lower()
                for item in st.session_state.expenses
            ]

            if not clean_name:
                st.error("Debes escribir un nombre.")

            elif clean_name.lower() in existing_names:
                st.error("Ya existe un gasto con ese nombre.")

            else:
                st.session_state.expenses.append({
                    "id": st.session_state.next_id,
                    "name": clean_name,
                    "amount": new_expense_amount
                })

                st.session_state.next_id += 1
                st.rerun()

    # Quick calculator
    st.divider()
    st.subheader("🧮 Calculadora rápida")

    with st.form("calculator_form"):
        calc_col1, calc_col2 = st.columns(2)

        with calc_col1:
            number1 = st.number_input(
                "Valor 1",
                value=0.0,
                step=1.0
            )

        with calc_col2:
            number2 = st.number_input(
                "Valor 2",
                value=0.0,
                step=1.0
            )

        operation = st.selectbox(
            "Operación",
            ["Sumar (+)", "Restar (-)", "Multiplicar (×)", "Dividir (÷)"]
        )

        calculate = st.form_submit_button(
            "Calcular",
            use_container_width=True
        )

        if calculate:
            if operation == "Sumar (+)":
                result = number1 + number2

            elif operation == "Restar (-)":
                result = number1 - number2

            elif operation == "Multiplicar (×)":
                result = number1 * number2

            else:
                result = None if number2 == 0 else number1 / number2

            if result is None:
                st.error("No se puede dividir entre cero.")
            else:
                st.success(f"Resultado: ${result:,.2f}")

# Financial calculations
income = income
amounts = {
    item["name"]: item["amount"]
    for item in st.session_state.expenses
    if item["name"]
}

total_expenses = sum(amounts.values())
balance = income - total_expenses

commitment = (
    total_expenses / income * 100
    if income > 0 else 0
)

# Main indicators
st.subheader("Resumen financiero")

col1, col2, col3, col4 = st.columns(4)

col1.metric("Ingresos", f"${income:,.2f}")
col2.metric("Compromisos", f"${total_expenses:,.2f}")
col3.metric("Disponible", f"${balance:,.2f}")
col4.metric("Comprometido", f"{commitment:.1f}%")

st.divider()

# Income and expense visualization
st.subheader("📊 Distribución de tu dinero")

chart_col, stats_col = st.columns([1.3, 1])

with chart_col:
    st.markdown("**Ingresos vs. gastos**")

    st.bar_chart(
        {
            "Monto ($)": {
                "Ingresos": income,
                "Compromisos": total_expenses,
                "Disponible": max(balance, 0)
            }
        },
        color="#38bdf8"
    )

with stats_col:
    st.markdown("**Estado de la quincena**")

    if balance >= 0:
        st.success(f"Disponible libre: ${balance:,.2f}")
    else:
        st.error(f"Déficit: ${abs(balance):,.2f}")

    st.write(f"Total comprometido: {commitment:.1f}%")

    st.progress(min(commitment / 100, 1.0))

st.divider()

# CSS-based donut chart
st.subheader("🍩 ¿En qué se va tu dinero?")

positive_expenses = {
    name: value
    for name, value in amounts.items()
    if value > 0
}

total_for_pie = sum(positive_expenses.values())

if total_for_pie > 0:
    colors = [
        "#38bdf8", "#818cf8", "#34d399",
        "#fbbf24", "#fb7185", "#c084fc",
        "#2dd4bf", "#f97316", "#a3e635",
        "#e879f9"
    ]

    gradient_parts = []
    current = 0

    for index, (name, value) in enumerate(positive_expenses.items()):
        start = current
        current += value / total_for_pie * 100

        gradient_parts.append(
            f"{colors[index % len(colors)]} "
            f"{start:.2f}% {current:.2f}%"
        )

    gradient = ", ".join(gradient_parts)

    st.markdown(f"""
    <div style="display:flex; justify-content:center; margin:25px 0;">
        <div style="
            width:230px;
            height:230px;
            border-radius:50%;
            background:conic-gradient({gradient});
            display:flex;
            align-items:center;
            justify-content:center;">
            <div style="
                width:135px;
                height:135px;
                border-radius:50%;
                background:#0e1525;
                display:flex;
                flex-direction:column;
                align-items:center;
                justify-content:center;">
                <span style="color:#94a3b8;font-size:13px;">Total gastos</span>
                <span style="color:white;font-size:23px;font-weight:bold;">
                    ${total_for_pie:,.2f}
                </span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    for index, (name, value) in enumerate(positive_expenses.items()):
        percentage = value / total_for_pie * 100

        st.markdown(
            f"""
            <div style="display:flex;justify-content:space-between;
                        align-items:center;margin:9px 0;">
                <span>
                    <span style="color:{colors[index % len(colors)]};">●</span>
                    {name}
                </span>
                <span style="color:#cbd5e1;">
                    ${value:,.2f} ({percentage:.1f}%)
                </span>
            </div>
            """,
            unsafe_allow_html=True
        )
else:
    st.info("Todavía no hay gastos registrados.")

st.divider()

# Expense details
st.subheader("📋 Detalle de compromisos")

if amounts:
    for name, value in sorted(
        amounts.items(),
        key=lambda item: item[1],
        reverse=True
    ):
        percentage = value / income * 100 if income > 0 else 0

        st.write(f"**{name}** — ${value:,.2f}")
        st.progress(min(percentage / 100, 1.0))
else:
    st.info("No tienes compromisos registrados.")

st.divider()

# Final balance
st.subheader("💵 Resultado de la quincena")

if balance >= 0:
    st.success(
        f"Después de pagar todos tus compromisos, "
        f"te quedan ${balance:,.2f} disponibles."
    )
else:
    st.error(
        f"Te faltan ${abs(balance):,.2f} "
        f"para cubrir todos tus compromisos."
    )

st.caption(
    "Administra tus gastos y utiliza la calculadora desde el menú lateral."
)
