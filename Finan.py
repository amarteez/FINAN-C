import json
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from streamlit_js_eval import streamlit_js_eval

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
STORAGE_KEY = "flujo_quincenal_v1"
TZ = timezone(timedelta(hours=-5))  # Panamá (Render corre en UTC)

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

COLORS = [
    "#38bdf8", "#818cf8", "#34d399", "#fbbf24", "#fb7185",
    "#c084fc", "#2dd4bf", "#f97316", "#a3e635", "#e879f9",
]

DEFAULT_INCOME = 350.0
DEFAULT_EXPENSES = [
    {"paid": False, "name": "Alquiler", "amount": 100.0},
    {"paid": False, "name": "Comida", "amount": 60.0},
    {"paid": False, "name": "Transporte", "amount": 40.0},
    {"paid": False, "name": "Luz y agua", "amount": 25.0},
    {"paid": False, "name": "Internet", "amount": 20.0},
    {"paid": False, "name": "Celular", "amount": 15.0},
    {"paid": False, "name": "Ahorro", "amount": 30.0},
]

st.set_page_config(page_title="Flujo Quincenal", page_icon="💰", layout="centered")

st.markdown("""
<style>
.block-container { padding-top: 2rem; padding-bottom: 3rem; }
[data-testid="stMetric"] {
    background: #1b2940;
    padding: 14px 16px;
    border-radius: 12px;
    border: 1px solid #33445f;
}
[data-testid="stMetricLabel"] { color: #aab8cc; }
.stButton button, .stDownloadButton button, .stFormSubmitButton button {
    min-height: 44px;
}
.row {
    display: flex; justify-content: space-between; align-items: center;
    gap: 12px; padding: 9px 0; border-bottom: 1px solid #22314a;
}
.row span:last-child { color: #cbd5e1; white-space: nowrap; }

/* En celular: mantener 2 columnas lado a lado en vez de apilarlas */
@media (max-width: 640px) {
    .block-container { padding-left: 1rem; padding-right: 1rem; padding-top: 1rem; }
    [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 0.5rem; }
    [data-testid="stColumn"], [data-testid="column"] {
        min-width: 0 !important; width: 50% !important; flex: 1 1 0 !important;
    }
    [data-testid="stMetric"] { padding: 10px 12px; }
    [data-testid="stMetricValue"] { font-size: 1.35rem; }
    h1 { font-size: 1.8rem; }
}

/* Barra de herramientas de la tabla siempre visible (en celular no hay "hover") */
[data-testid="stElementToolbar"] { opacity: 1 !important; }
[data-testid="stElementToolbarButton"] button {
    min-width: 36px; min-height: 36px; border-radius: 8px;
}
/* Botón de borrar: rojo y llamativo cuando hay filas seleccionadas */
[data-testid="stElementToolbarButton"] button[aria-label="Delete row(s)"] {
    background: #ef4444 !important; color: #ffffff !important;
    box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.35);
    animation: trash-pulse 1.4s ease-in-out infinite;
}
[data-testid="stElementToolbarButton"] button[aria-label="Delete row(s)"]:hover {
    background: #dc2626 !important;
}
/* Botón de añadir fila: verde */
[data-testid="stElementToolbarButton"] button[aria-label="Add row"] {
    background: #16a34a !important; color: #ffffff !important;
}
@keyframes trash-pulse {
    0%, 100% { box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.35); }
    50% { box-shadow: 0 0 0 6px rgba(239, 68, 68, 0.15); }
}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def current_period():
    now = datetime.now(TZ)
    return f"{now.year}-{now.month:02d}-{1 if now.day <= 15 else 2}"


def next_period(pid):
    year, month, half = map(int, pid.split("-"))
    if half == 1:
        return f"{year}-{month:02d}-2"
    month += 1
    if month > 12:
        year, month = year + 1, 1
    return f"{year}-{month:02d}-1"


def period_label(pid):
    try:
        year, month, half = map(int, pid.split("-"))
        return f"{'1ª' if half == 1 else '2ª'} quincena de {MESES[month - 1]} {year}"
    except (ValueError, IndexError, AttributeError):
        return str(pid)


def period_short(pid):
    try:
        year, month, half = map(int, pid.split("-"))
        return f"{year}-{month:02d} Q{half}"
    except (ValueError, AttributeError):
        return str(pid)


def to_float(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if pd.isna(number) or number < 0:
        return 0.0
    return round(number, 2)


def clean_expenses(rows):
    result = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        name = "" if name is None or (isinstance(name, float) and pd.isna(name)) else str(name).strip()
        if not name:
            continue
        paid = str(row.get("paid")).lower() == "true"
        result.append({"paid": paid, "name": name, "amount": to_float(row.get("amount"))})
    return result


def normalize(raw):
    """Convierte lo que venga de localStorage / un respaldo en datos válidos."""
    if not isinstance(raw, dict):
        raw = {}

    expenses = raw.get("expenses")
    expenses = clean_expenses(expenses) if isinstance(expenses, list) else [dict(e) for e in DEFAULT_EXPENSES]

    history = raw.get("history")
    history = [h for h in history if isinstance(h, dict)] if isinstance(history, list) else []

    period = raw.get("period")
    try:
        next_period(period)
    except (ValueError, AttributeError):
        period = current_period()

    return {
        "version": 1,
        "income": to_float(raw.get("income", DEFAULT_INCOME)),
        "period": period,
        "expenses": expenses,
        "history": history,
    }


def apply_data(data):
    """Carga datos en la sesión. Llamar SIEMPRE antes de dibujar widgets."""
    st.session_state.data = data
    st.session_state.income = data["income"]
    st.session_state.editor_base = [dict(e) for e in data["expenses"]]
    st.session_state.editor_ver = st.session_state.get("editor_ver", 0) + 1
    st.session_state.pop("confirm_close", None)
    st.session_state.pop("confirm_reset", None)


def money(value):
    return f"${value:,.2f}"


def build_message(period, income, total, paid_total, pending_total, balance, commitment, expenses):
    """Texto del resumen para WhatsApp (usa *negritas* de WhatsApp)."""
    lines = [
        f"💰 *Resumen – {period_label(period)}*",
        "",
        f"Ingreso: {money(income)}",
        f"Gastos: {money(total)} ({commitment:.0f}% del ingreso)",
        f"Pagado: {money(paid_total)} · Pendiente: {money(pending_total)}",
        f"*Disponible: {money(balance)}*",
    ]
    items = [e for e in expenses if e["amount"] > 0]
    if items:
        lines += ["", "*Gastos:*"]
        lines += [
            f"{'✅' if e['paid'] else '⏳'} {e['name']}: {money(e['amount'])}"
            for e in sorted(items, key=lambda e: e["amount"], reverse=True)
        ]
    return "\n".join(lines)


def share_card(period, income, total, paid_total, pending_total, balance, commitment,
               expenses, message):
    """Dibuja una imagen de resumen (con el gráfico) y permite compartirla o descargarla."""
    items = [e for e in expenses if e["amount"] > 0]
    payload = {
        "title": "Resumen de la quincena",
        "period": period_label(period),
        "income": money(income),
        "total": money(total),
        "paid": money(paid_total),
        "pending": money(pending_total),
        "balance": money(balance),
        "balanceNeg": balance < 0,
        "commitment": f"{commitment:.0f}%",
        "items": [
            {
                "name": e["name"],
                "amount": money(e["amount"]),
                "pct": e["amount"] / total if total > 0 else 0,
                "paid": e["paid"],
                "color": COLORS[i % len(COLORS)],
            }
            for i, e in enumerate(items)
        ],
        "message": message,
        "filename": f"resumen-{period}.png",
    }
    js_data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    components.html(f"""
<style>
  body {{ margin: 0; font-family: "Source Sans Pro", sans-serif; }}
  .btns {{ display: flex; gap: 8px; margin-bottom: 10px; }}
  .btns button {{
    flex: 1; min-height: 44px; border-radius: 8px; cursor: pointer; font-size: 15px;
    border: 1px solid #33445f; background: #1b2940; color: #ffffff;
  }}
  .btns button:hover {{ border-color: #38bdf8; color: #38bdf8; }}
  img {{ display: block; width: 100%; max-height: 430px; object-fit: contain;
         border-radius: 12px; }}
</style>
<div class="btns">
  <button id="share">📤 Compartir imagen</button>
  <button id="download">⬇️ Descargar</button>
</div>
<img id="preview" alt="Vista previa del resumen">
<script>
const D = {js_data};
const W = 720, PAD = 40, ROW = 44;
const H = 150 + 2 * 104 + 300 + D.items.length * ROW + 110;
const canvas = document.createElement("canvas");
canvas.width = W; canvas.height = H;
const c = canvas.getContext("2d");
const FONT = '"Segoe UI", Roboto, Helvetica, Arial, sans-serif';

function roundRect(x, y, w, h, r, fill, stroke) {{
  c.beginPath();
  c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r);
  c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath();
  if (fill) {{ c.fillStyle = fill; c.fill(); }}
  if (stroke) {{ c.strokeStyle = stroke; c.lineWidth = 2; c.stroke(); }}
}}
function fit(text, maxW) {{
  if (c.measureText(text).width <= maxW) return text;
  while (text.length > 1 && c.measureText(text + "…").width > maxW) text = text.slice(0, -1);
  return text + "…";
}}

// Fondo y encabezado
c.fillStyle = "#0e1525"; c.fillRect(0, 0, W, H);
c.fillStyle = "#ffffff"; c.font = "bold 36px " + FONT;
c.fillText("💰 " + D.title, PAD, 70);
c.fillStyle = "#94a3b8"; c.font = "24px " + FONT;
c.fillText(D.period, PAD, 110);

// Tarjetas 2x2
const stats = [["Ingreso", D.income], ["Gastos", D.total],
               ["Disponible", D.balance], ["Comprometido", D.commitment]];
const bw = (W - PAD * 2 - 16) / 2;
stats.forEach(([label, value], i) => {{
  const x = PAD + (i % 2) * (bw + 16), y = 140 + Math.floor(i / 2) * 104;
  roundRect(x, y, bw, 90, 14, "#1b2940", "#33445f");
  c.fillStyle = "#aab8cc"; c.font = "20px " + FONT; c.fillText(label, x + 18, y + 32);
  c.fillStyle = (label === "Disponible" && D.balanceNeg) ? "#fb7185" : "#ffffff";
  c.font = "bold 30px " + FONT; c.fillText(value, x + 18, y + 72);
}});

// Gráfico de dona
let y0 = 140 + 2 * 104 + 10;
const cx = W / 2, cy = y0 + 140, r = 125, inner = 78;
if (D.items.length) {{
  let a = -Math.PI / 2;
  D.items.forEach(it => {{
    const b = a + it.pct * Math.PI * 2;
    c.beginPath(); c.moveTo(cx, cy); c.arc(cx, cy, r, a, b); c.closePath();
    c.fillStyle = it.color; c.fill(); a = b;
  }});
}} else {{
  c.beginPath(); c.arc(cx, cy, r, 0, Math.PI * 2); c.fillStyle = "#22314a"; c.fill();
}}
c.beginPath(); c.arc(cx, cy, inner, 0, Math.PI * 2); c.fillStyle = "#0e1525"; c.fill();
c.textAlign = "center";
c.fillStyle = "#94a3b8"; c.font = "18px " + FONT; c.fillText("Total gastos", cx, cy - 6);
c.fillStyle = "#ffffff"; c.font = "bold 26px " + FONT; c.fillText(D.total, cx, cy + 26);
c.textAlign = "left";

// Lista de gastos
let y = y0 + 300;
D.items.forEach(it => {{
  c.beginPath(); c.arc(PAD + 9, y + 20, 8, 0, Math.PI * 2); c.fillStyle = it.color; c.fill();
  c.fillStyle = "#ffffff"; c.font = "22px " + FONT;
  c.fillText(fit(it.name, W - PAD * 2 - 330), PAD + 28, y + 28);
  c.fillStyle = it.paid ? "#34d399" : "#fbbf24"; c.font = "18px " + FONT;
  c.textAlign = "right";
  c.fillText(it.paid ? "Pagado" : "Pendiente", W - PAD - 150, y + 28);
  c.fillStyle = "#cbd5e1"; c.font = "bold 22px " + FONT;
  c.fillText(it.amount, W - PAD, y + 28);
  c.textAlign = "left";
  c.fillStyle = "#22314a"; c.fillRect(PAD, y + ROW - 2, W - PAD * 2, 1);
  y += ROW;
}});

// Pie: pagado / pendiente
y += 24;
roundRect(PAD, y, W - PAD * 2, 64, 14, D.balanceNeg ? "#3b1d2a" : "#12332b", null);
c.fillStyle = D.balanceNeg ? "#fb7185" : "#34d399"; c.font = "bold 22px " + FONT;
c.fillText(`Pagado ${{D.paid}}  ·  Pendiente ${{D.pending}}`, PAD + 20, y + 41);

document.getElementById("preview").src = canvas.toDataURL("image/png");
let blob = null;
canvas.toBlob(b => {{ blob = b; }}, "image/png");

function download() {{
  const a = document.createElement("a");
  a.href = canvas.toDataURL("image/png"); a.download = D.filename;
  document.body.appendChild(a); a.click(); a.remove();
}}
document.getElementById("download").onclick = download;
document.getElementById("share").onclick = async () => {{
  // El iframe no tiene permiso "web-share"; se usa el navigator de la página principal.
  let nav = navigator;
  try {{ if (window.parent.navigator.share) nav = window.parent.navigator; }} catch (e) {{}}
  if (blob && nav.canShare) {{
    const file = new File([blob], D.filename, {{ type: "image/png" }});
    if (nav.canShare({{ files: [file] }})) {{
      try {{ await nav.share({{ files: [file], text: D.message }}); return; }}
      catch (e) {{ if (e.name === "AbortError") return; }}
    }}
  }}
  download();
}};
</script>
""", height=500)


# ---------------------------------------------------------------------------
# Carga desde localStorage (solo la primera vez en cada sesión)
# ---------------------------------------------------------------------------
if "data" not in st.session_state:
    raw = streamlit_js_eval(
        js_expressions=f"localStorage.getItem('{STORAGE_KEY}') || ''",
        key="ls_load",
    )
    if raw is None:  # el componente aún no respondió
        st.info("Cargando tus datos…")
        st.stop()
    try:
        parsed = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        parsed = {}
    apply_data(normalize(parsed))

# Cambios grandes (cerrar quincena, restaurar, reiniciar) se aplican aquí
if "pending" in st.session_state:
    apply_data(st.session_state.pop("pending"))

data = st.session_state.data

# ---------------------------------------------------------------------------
# Interfaz
# ---------------------------------------------------------------------------
st.title("💰 Flujo")
st.caption(period_label(data["period"]))

tab_resumen, tab_gastos, tab_historial, tab_ajustes = st.tabs(
    ["📊 Resumen", "📝 Gastos", "🗂️ Historial", "⚙️ Ajustes"]
)

# --- Gastos (se dibuja primero porque el resumen depende de él) ------------
with tab_gastos:
    st.number_input("Ingreso de la quincena ($)", min_value=0.0, step=1.0, format="%.2f", key="income")

    st.caption("Marca ✅ lo que ya pagaste. Usa el botón verde **+** para añadir una fila. "
               "Para borrar, toca el borde izquierdo de la fila para seleccionarla y "
               "luego el botón rojo 🗑️ que aparece arriba de la tabla.")

    base = pd.DataFrame(st.session_state.editor_base, columns=["paid", "name", "amount"])
    base = base.astype({"paid": bool, "name": str, "amount": float})

    edited = st.data_editor(
        base,
        key=f"editor_{st.session_state.editor_ver}",
        num_rows="dynamic",
        hide_index=True,
        use_container_width=True,
        column_order=["paid", "name", "amount"],
        column_config={
            "paid": st.column_config.CheckboxColumn("✅", default=False, width="small"),
            "name": st.column_config.TextColumn("Compromiso", required=True),
            "amount": st.column_config.NumberColumn(
                "Monto", min_value=0.0, step=0.01, format="$%.2f", default=0.0
            ),
        },
    )

expenses = clean_expenses(edited.to_dict("records"))
income = to_float(st.session_state.income)
data["income"] = income
data["expenses"] = expenses

total = sum(e["amount"] for e in expenses)
paid_total = sum(e["amount"] for e in expenses if e["paid"])
pending = [e for e in expenses if not e["paid"] and e["amount"] > 0]
pending_total = total - paid_total
balance = income - total
commitment = total / income * 100 if income > 0 else 0

# --- Resumen ---------------------------------------------------------------
with tab_resumen:
    c1, c2 = st.columns(2)
    c1.metric("Ingreso", money(income))
    c2.metric("Compromisos", money(total))
    c3, c4 = st.columns(2)
    c3.metric("Disponible", money(balance))
    c4.metric("Comprometido", f"{commitment:.0f}%")

    st.write("")
    if balance >= 0:
        st.success(f"Después de pagar todo te quedan **{money(balance)}** libres.")
    else:
        st.error(f"Te faltan **{money(abs(balance))}** para cubrir todos tus compromisos.")

    st.subheader("Pagos de la quincena")
    n_with_amount = sum(1 for e in expenses if e["amount"] > 0)
    n_paid = sum(1 for e in expenses if e["paid"] and e["amount"] > 0)
    st.progress(
        min(paid_total / total, 1.0) if total > 0 else 0.0,
        text=f"Pagado {money(paid_total)} de {money(total)} · {n_paid}/{n_with_amount} compromisos",
    )

    if pending:
        st.markdown(f"**Pendiente por pagar: {money(pending_total)}**")
        rows = "".join(
            f'<div class="row"><span>⏳ {e["name"]}</span><span>{money(e["amount"])}</span></div>'
            for e in sorted(pending, key=lambda e: e["amount"], reverse=True)
        )
        st.markdown(rows, unsafe_allow_html=True)
    elif total > 0:
        st.success("🎉 ¡Todo pagado esta quincena!")

    st.subheader("¿En qué se va tu dinero?")
    positive = [e for e in expenses if e["amount"] > 0]
    if positive:
        parts, current = [], 0.0
        for i, e in enumerate(positive):
            start = current
            current += e["amount"] / total * 100
            parts.append(f"{COLORS[i % len(COLORS)]} {start:.2f}% {current:.2f}%")

        st.markdown(f"""
        <div style="display:flex;justify-content:center;margin:20px 0;">
          <div style="width:210px;height:210px;border-radius:50%;
                      background:conic-gradient({', '.join(parts)});
                      display:flex;align-items:center;justify-content:center;">
            <div style="width:125px;height:125px;border-radius:50%;background:#0e1525;
                        display:flex;flex-direction:column;align-items:center;justify-content:center;">
              <span style="color:#94a3b8;font-size:13px;">Total gastos</span>
              <span style="color:white;font-size:21px;font-weight:bold;">{money(total)}</span>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        legend = "".join(
            f'<div class="row"><span><span style="color:{COLORS[i % len(COLORS)]};">●</span> '
            f'{e["name"]}</span><span>{money(e["amount"])} ({e["amount"] / total * 100:.0f}%)</span></div>'
            for i, e in enumerate(positive)
        )
        st.markdown(legend, unsafe_allow_html=True)
    else:
        st.info("Todavía no hay gastos registrados.")

    # --- Compartir ---------------------------------------------------------
    st.subheader("📤 Compartir resumen")
    message = build_message(data["period"], income, total, paid_total, pending_total,
                            balance, commitment, expenses)
    st.link_button(
        "💬 Enviar resumen por WhatsApp",
        f"https://wa.me/?text={quote(message)}",
        type="primary",
        use_container_width=True,
    )
    st.caption("Abre WhatsApp con el resumen escrito; tú eliges a quién enviarlo. "
               "Para mandar el gráfico, usa **Compartir imagen** (en celular se abre el menú "
               "para compartir; en computadora se descarga la imagen para que la adjuntes).")
    share_card(data["period"], income, total, paid_total, pending_total,
               balance, commitment, expenses, message)
    with st.expander("Ver o copiar el texto"):
        st.code(message, language=None)

# --- Historial -------------------------------------------------------------
with tab_historial:
    st.write(f"Quincena actual: **{period_label(data['period'])}**")

    with st.expander("✔️ Cerrar quincena y empezar la siguiente"):
        st.write(
            "Se guarda un resumen de esta quincena en el historial y tus compromisos "
            f"pasan a la **{period_label(next_period(data['period']))}**, desmarcados como pagados."
        )
        confirm = st.checkbox("Sí, quiero cerrar la quincena", key="confirm_close")
        if st.button("Cerrar quincena", type="primary", disabled=not confirm, use_container_width=True):
            snapshot = {
                "period": data["period"],
                "closed_at": datetime.now(TZ).strftime("%Y-%m-%d %H:%M"),
                "income": income,
                "total": round(total, 2),
                "paid": round(paid_total, 2),
                "balance": round(balance, 2),
                "expenses": expenses,
            }
            st.session_state.pending = {
                **data,
                "history": data["history"] + [snapshot],
                "period": next_period(data["period"]),
                "expenses": [{**e, "paid": False} for e in expenses],
            }
            st.rerun()

    history = data["history"]
    if history:
        table = pd.DataFrame([
            {
                "Quincena": period_short(h.get("period")),
                "Ingreso": to_float(h.get("income")),
                "Gastos": to_float(h.get("total")),
                "Disponible": float(h.get("balance") or 0),
            }
            for h in reversed(history)
        ])
        st.dataframe(
            table,
            hide_index=True,
            use_container_width=True,
            column_config={
                col: st.column_config.NumberColumn(format="$%.2f")
                for col in ["Ingreso", "Gastos", "Disponible"]
            },
        )

        if len(history) >= 2:
            st.markdown("**Disponible por quincena**")
            st.bar_chart(
                pd.DataFrame(
                    {"Disponible": [float(h.get("balance") or 0) for h in history]},
                    index=[period_short(h.get("period")) for h in history],
                ),
                color="#38bdf8",
            )

        with st.expander("Ver detalle de una quincena"):
            options = list(range(len(history)))[::-1]
            idx = st.selectbox(
                "Quincena",
                options,
                format_func=lambda i: period_label(history[i].get("period")),
            )
            chosen = history[idx]
            st.caption(f"Cerrada el {chosen.get('closed_at', '—')}")
            detail = "".join(
                f'<div class="row"><span>{"✅" if e.get("paid") else "⏳"} {e.get("name")}</span>'
                f'<span>{money(to_float(e.get("amount")))}</span></div>'
                for e in clean_expenses(chosen.get("expenses", []))
            )
            st.markdown(detail, unsafe_allow_html=True)
    else:
        st.info("Aún no has cerrado ninguna quincena. Cuando la cierres, aparecerá aquí.")

# --- Ajustes ---------------------------------------------------------------
with tab_ajustes:
    st.subheader("💾 Respaldo")
    st.caption("Tus datos se guardan en este navegador. Descarga un respaldo de vez en cuando "
               "o para pasar tus datos a otro dispositivo.")

    st.download_button(
        "Descargar respaldo (.json)",
        data=json.dumps(data, ensure_ascii=False, indent=2),
        file_name=f"flujo-respaldo-{datetime.now(TZ):%Y-%m-%d}.json",
        mime="application/json",
        use_container_width=True,
    )

    uploaded = st.file_uploader(
        "Restaurar desde un respaldo", type=["json"],
        key=f"upload_{st.session_state.editor_ver}",
    )
    if uploaded is not None:
        try:
            restored = normalize(json.loads(uploaded.getvalue().decode("utf-8")))
        except (ValueError, UnicodeDecodeError):
            st.error("Ese archivo no es un respaldo válido.")
        else:
            st.warning(f"Esto reemplaza tus datos actuales por los del respaldo "
                       f"({len(restored['expenses'])} compromisos, "
                       f"{len(restored['history'])} quincenas en historial).")
            if st.button("Restaurar este respaldo", type="primary", use_container_width=True):
                st.session_state.pending = restored
                st.rerun()

    st.divider()
    with st.expander("🧮 Calculadora rápida"):
        with st.form("calculator_form"):
            col_a, col_b = st.columns(2)
            number1 = col_a.number_input("Valor 1", value=0.0, step=1.0)
            number2 = col_b.number_input("Valor 2", value=0.0, step=1.0)
            operation = st.selectbox("Operación", ["Sumar (+)", "Restar (-)", "Multiplicar (×)", "Dividir (÷)"])
            if st.form_submit_button("Calcular", use_container_width=True):
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
                    st.success(f"Resultado: {result:,.2f}")

    st.divider()
    with st.expander("🗑️ Borrar todos los datos"):
        st.write("Vuelve a los gastos de ejemplo y borra el historial de este navegador.")
        sure = st.checkbox("Sí, borrar todo", key="confirm_reset")
        if st.button("Borrar todo", disabled=not sure, use_container_width=True):
            st.session_state.pending = normalize({})
            st.rerun()

# ---------------------------------------------------------------------------
# Guardado automático en localStorage
# ---------------------------------------------------------------------------
payload = json.dumps(data, ensure_ascii=False)
js_value = json.dumps(payload).replace("</", "<\\/")
components.html(
    f"<script>try {{ localStorage.setItem('{STORAGE_KEY}', {js_value}); }} catch (e) {{}}</script>",
    height=0,
)
