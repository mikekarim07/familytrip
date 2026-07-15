import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, date, timedelta
import json
import re

# ═══════════════════════════════════════════════════════════════
#  CONSTANTES BASE
# ═══════════════════════════════════════════════════════════════

SHEET_NAME   = "Karim Family Trip Europe 2026"
MONEDAS      = ["MXN", "EUR", "USD"]
RUBROS       = ["🏨 Hospedaje", "✈️ Vuelos", "🚆 Trenes", "🚗 Transporte local",
                "🍽️ Comida", "🎭 Actividades", "🛍️ Compras", "💊 Farmacia", "🔧 Otros"]
TIPOS_TRANSP = ["✈️ Vuelo", "🚄 Tren AVE", "🚆 Tren regional", "🚌 Autobús",
                "⛴️ Ferry", "🚗 Renta de auto", "🚕 Uber/Taxi", "🚇 Metro/Bus ciudad"]

FECHA_INICIO = date(2026, 7, 13)
FECHA_FIN    = date(2026, 8, 15)

# ═══════════════════════════════════════════════════════════════
#  SECRETS
# ═══════════════════════════════════════════════════════════════

def load_pins() -> dict:
    """
    [PINS]
    "1234" = "Papá|admin|👨"
    "5678" = "Mamá|coeditor|👩"
    "1111" = "Analu|viewer|👧"
    "2222" = "Sebas|viewer|🧒"
    """
    pins = {}
    try:
        raw = st.secrets.get("PINS", {})
        for pin, value in raw.items():
            parts = str(value).split("|")
            if len(parts) == 3:
                pins[str(pin)] = {
                    "nombre": parts[0].strip(),
                    "rol":    parts[1].strip(),
                    "emoji":  parts[2].strip(),
                }
    except Exception:
        pass
    return pins

def load_presupuestos() -> dict:
    """
    [PRESUPUESTOS]
    total   = "300000"
    Papa    = "120000"
    Mama    = "100000"
    Analu   = "40000"
    Sebas   = "40000"
    """
    defaults = {"total": 300_000, "Papa": 120_000, "Mama": 100_000,
                "Analu": 40_000, "Sebas": 40_000}
    try:
        raw = st.secrets.get("PRESUPUESTOS", {})
        result = {}
        for k, v in raw.items():
            try:
                result[k] = float(v)
            except Exception:
                result[k] = defaults.get(k, 0)
        # fallback para claves faltantes
        for k, v in defaults.items():
            if k not in result:
                result[k] = v
        return result
    except Exception:
        return defaults

def get_pagadores() -> list:
    """Pagadores dinámicos desde Secrets."""
    presup = load_presupuestos()
    order  = ["Papa", "Mama", "Analu", "Sebas"]
    return [p for p in order if p in presup and p != "total"]

# ═══════════════════════════════════════════════════════════════
#  CONEXIÓN A GOOGLE SHEETS
# ═══════════════════════════════════════════════════════════════

@st.cache_resource
def get_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

@st.cache_data(ttl=60)
def get_df(sheet_name: str) -> pd.DataFrame:
    try:
        ws   = get_client().open(SHEET_NAME).worksheet(sheet_name)
        data = ws.get_all_records()
        return pd.DataFrame(data) if data else pd.DataFrame()
    except Exception as e:
        st.error(f"Error leyendo '{sheet_name}': {e}")
        return pd.DataFrame()

def save_row(sheet_name: str, row: list) -> bool:
    try:
        ws = get_client().open(SHEET_NAME).worksheet(sheet_name)
        ws.append_row(row, value_input_option="USER_ENTERED")
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Error guardando en '{sheet_name}': {e}")
        return False

# ═══════════════════════════════════════════════════════════════
#  CATÁLOGOS DESDE SHEETS
# ═══════════════════════════════════════════════════════════════

@st.cache_data(ttl=120)
def get_config() -> dict:
    defaults = {
        "ciudades": ["Mexico", "Madrid", "Barcelona", "París", "Strasburgo",
                     "Chur", "Milan", "Venecia", "Florencia", "Roma",
                     "Pisa", "Capri", "Otra"],
    }
    try:
        ws   = get_client().open(SHEET_NAME).worksheet("config")
        rows = ws.get_all_values()
        cfg  = {}
        for row in rows:
            if len(row) >= 2 and row[0].strip() and row[1].strip():
                key = row[0].strip().lower()
                cfg.setdefault(key, []).append(row[1].strip())
        for k, v in defaults.items():
            if k not in cfg or not cfg[k]:
                cfg[k] = v
        return cfg
    except Exception:
        return defaults

def get_ciudades() -> list:
    return get_config().get("ciudades", ["Otra"])

# ═══════════════════════════════════════════════════════════════
#  IDs RELACIONALES
# ═══════════════════════════════════════════════════════════════

def _slug(text: str) -> str:
    abrevs = {
        "MEXICO": "MEX", "MADRID": "MAD", "STRASBURGO": "STS", "MILAN": "MIL",
        "VENECIA": "VEN", "FLORENCIA": "FLO", "BARCELONA": "BCN",
        "PARÍS": "PAR", "PARIS": "PAR", "ROMA": "ROM", "CHUR": "CHR",
        "CAPRI": "CAP", "PISA": "PIS",
    }
    upper = text.upper().strip()
    for k, v in abrevs.items():
        if k in upper:
            return v
    clean = re.sub(r'[^A-Z0-9 ]', '', upper).split()
    return "".join(w[0] for w in clean[:4]) if len(clean) >= 2 else upper[:6]

def gen_id(prefix: str, fecha: date, extra: str = "") -> str:
    date_str = fecha.strftime("%Y%m%d")
    suffix   = _slug(extra)[:8] if extra else datetime.now().strftime("%H%M%S")
    return f"{prefix}-{date_str}-{suffix}"

# ═══════════════════════════════════════════════════════════════
#  UTILIDADES
# ═══════════════════════════════════════════════════════════════

def fmt_mxn(v) -> str:
    try:    return f"${float(v):,.0f} MXN"
    except: return "—"

def fmt_orig(monto, moneda) -> str:
    try:
        s = {"MXN": "$", "EUR": "€", "USD": "USD $"}.get(str(moneda), "")
        return f"{s}{float(monto):,.2f} {moneda}"
    except: return "—"

def calc_tc(monto_orig: float, monto_mxn: float, moneda: str) -> str:
    if moneda == "MXN" or monto_orig <= 0 or monto_mxn <= 0:
        return ""
    return f"TC implícito: {monto_mxn/monto_orig:.4f} MXN/{moneda}"

def widget_monto(key_prefix: str):
    c1, c2 = st.columns(2)
    with c1:
        moneda     = st.selectbox("Moneda", MONEDAS, key=f"{key_prefix}_moneda")
        monto_orig = st.number_input(f"Monto ({moneda})", min_value=0.0,
                                      step=1.0, format="%.2f", key=f"{key_prefix}_monto")
    with c2:
        if moneda == "MXN":
            monto_mxn = monto_orig
            st.metric("Total en MXN", fmt_mxn(monto_mxn))
            st.caption("Moneda base.")
        else:
            monto_mxn = st.number_input("Equivalente en MXN", min_value=0.0,
                                         step=1.0, format="%.2f", key=f"{key_prefix}_mxn",
                                         help="Lo que salió de tu bolsillo en pesos.")
            if monto_orig > 0 and monto_mxn > 0:
                st.caption(calc_tc(monto_orig, monto_mxn, moneda))
            else:
                st.caption("Ingresa el MXN para ver el TC.")
    return monto_orig, moneda, monto_mxn

def gastos_preparados() -> pd.DataFrame:
    """Devuelve df de gastos con tipos numéricos listos."""
    df = get_df("gastos")
    if df.empty:
        return df
    for col in ["monto_total", "monto_mxn", "costo_por_unidad", "impuestos", "unidades"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    return df

def dias_transcurridos() -> int:
    hoy = date.today()
    if hoy < FECHA_INICIO:
        return 0
    return min((hoy - FECHA_INICIO).days + 1, (FECHA_FIN - FECHA_INICIO).days + 1)

def dias_totales() -> int:
    return (FECHA_FIN - FECHA_INICIO).days + 1

# ═══════════════════════════════════════════════════════════════
#  AUTENTICACIÓN
# ═══════════════════════════════════════════════════════════════

def login_screen():
    st.markdown("""
        <div style='text-align:center;padding:2.5rem 0 1.5rem'>
            <div style='font-size:56px'>🌍</div>
            <h1 style='margin:0.4rem 0 0.2rem;font-size:1.9rem;font-weight:500'>
                FamilyTrip Europe 2026
            </h1>
            <p style='color:#888;margin:0'>13 Jul – 15 Ago · ¡Nos vamos!</p>
        </div>
    """, unsafe_allow_html=True)
    _, col, _ = st.columns([1, 2, 1])
    with col:
        pin = st.text_input("PIN", type="password", max_chars=4,
                            placeholder="Ingresa tu PIN de 4 dígitos",
                            label_visibility="collapsed")
        if st.button("Entrar →", use_container_width=True, type="primary"):
            pins = load_pins()
            if pin in pins:
                st.session_state.usuario  = pins[pin]
                st.session_state.logueado = True
                st.rerun()
            else:
                st.error("PIN incorrecto.")

def logout():
    st.session_state.clear()
    st.rerun()

# ═══════════════════════════════════════════════════════════════
#  MÓDULO: DASHBOARD "BUENOS DÍAS"
# ═══════════════════════════════════════════════════════════════

def modulo_dashboard(usuario: dict):
    nombre    = usuario["nombre"]
    emoji_u   = usuario["emoji"]
    hoy       = date.today()
    presupuestos = load_presupuestos()
    pagadores    = get_pagadores()

    # Saludo dinámico
    hora = datetime.now().hour
    saludo = "🌅 Buenos días" if hora < 12 else ("☀️ Buenas tardes" if hora < 19 else "🌙 Buenas noches")
    st.markdown(
        f"<h1 style='margin-bottom:0'>{saludo}, {emoji_u} {nombre}</h1>"
        f"<p style='color:#888;margin-top:4px'>{hoy.strftime('%A %d de %B de %Y').capitalize()}</p>",
        unsafe_allow_html=True
    )
    st.divider()

    # ── Ciudad actual y hotel ────────────────────────────────────
    df_itin  = get_df("itinerario")
    df_aloj  = get_df("alojamiento")
    df_transp = get_df("transportes")

    ciudad_hoy = "—"
    hotel_hoy  = None
    if not df_itin.empty:
        df_itin["fecha"] = pd.to_datetime(df_itin["fecha"], errors="coerce")
        eventos_hoy = df_itin[df_itin["fecha"].dt.date == hoy]
        if not eventos_hoy.empty:
            ciudad_hoy = eventos_hoy["ciudad"].dropna().iloc[0]
        else:
            # Ciudad más reciente antes de hoy
            pasados = df_itin[df_itin["fecha"].dt.date <= hoy].sort_values("fecha")
            if not pasados.empty:
                ciudad_hoy = pasados["ciudad"].dropna().iloc[-1]

    if not df_aloj.empty:
        df_aloj["checkin"]  = pd.to_datetime(df_aloj["checkin"],  errors="coerce")
        df_aloj["checkout"] = pd.to_datetime(df_aloj["checkout"], errors="coerce")
        hoteles_activos = df_aloj[
            (df_aloj["checkin"].dt.date  <= hoy) &
            (df_aloj["checkout"].dt.date >= hoy)
        ]
        if not hoteles_activos.empty:
            hotel_hoy = hoteles_activos.iloc[0]

    # ── Gastos de hoy ────────────────────────────────────────────
    df_gst = gastos_preparados()
    gasto_hoy_total = 0.0
    promedio_diario = 0.0
    proyeccion      = 0.0
    dias_trans      = dias_transcurridos()
    dias_tot        = dias_totales()

    if not df_gst.empty:
        mask_hoy       = df_gst["fecha"].dt.date == hoy
        gasto_hoy_total = df_gst[mask_hoy]["monto_mxn"].sum()
        total_gastado  = df_gst["monto_mxn"].sum()
        promedio_diario = total_gastado / dias_trans if dias_trans > 0 else 0
        proyeccion      = total_gastado + promedio_diario * (dias_tot - dias_trans)

    # ── Próximo transporte ────────────────────────────────────────
    proximo_transp = None
    if not df_transp.empty:
        df_transp["fecha"] = pd.to_datetime(df_transp["fecha"], errors="coerce")
        futuros = df_transp[df_transp["fecha"].dt.date >= hoy].sort_values("fecha")
        if not futuros.empty:
            proximo_transp = futuros.iloc[0]

    # ── FILA 1: Ubicación ─────────────────────────────────────────
    st.markdown("### 📍 Hoy estamos en")
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.markdown(f"## {ciudad_hoy}")
            if hotel_hoy is not None:
                st.markdown(f"🏨 **{hotel_hoy.get('hotel', '')}**")
                st.caption(f"📞 {hotel_hoy.get('telefono', '')} · Check-out: {hotel_hoy.get('checkout', '')[:10]}")
                if hotel_hoy.get("maps_url"):
                    st.link_button("🗺️ Ver en Maps", hotel_hoy.get("maps_url", ""))
            else:
                st.caption("Sin hotel registrado para hoy.")

    with col2:
        if proximo_transp is not None:
            with st.container(border=True):
                st.markdown("### 🚌 Próximo transporte")
                st.markdown(
                    f"**{proximo_transp.get('tipo','')}** "
                    f"{proximo_transp.get('proveedor','')} "
                    f"`{proximo_transp.get('numero','')}`"
                )
                st.markdown(
                    f"📅 {str(proximo_transp.get('fecha',''))[:10]} &nbsp; "
                    f"🛫 {proximo_transp.get('hora_salida','')} → "
                    f"🛬 {proximo_transp.get('hora_llegada','')}"
                )
                st.markdown(
                    f"{proximo_transp.get('origen_ciudad','')} → "
                    f"**{proximo_transp.get('destino_ciudad','')}**"
                )
                hora_lim = proximo_transp.get("hora_limite", "")
                if hora_lim:
                    st.warning(f"⏰ Estar en {proximo_transp.get('origen_lugar','')} a las **{hora_lim}**")

    st.divider()

    # ── FILA 2: Gastos del día e indicadores ─────────────────────
    st.markdown("### 💰 Indicadores financieros")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("💸 Gasto de hoy",    fmt_mxn(gasto_hoy_total))
    k2.metric("📊 Promedio diario", fmt_mxn(promedio_diario))
    k3.metric("🔮 Proyección final", fmt_mxn(proyeccion),
              delta=fmt_mxn(proyeccion - presupuestos.get("total", 0)),
              delta_color="inverse")
    dias_restantes = max(dias_tot - dias_trans, 0)
    k4.metric("📅 Días restantes",  f"{dias_restantes} de {dias_tot}")

    st.divider()

    # ── FILA 3: Actividades del día ───────────────────────────────
    st.markdown("### 📅 Actividades de hoy")
    if not df_itin.empty:
        eventos_hoy_df = df_itin[df_itin["fecha"].dt.date == hoy].sort_values("hora")
        if eventos_hoy_df.empty:
            st.info("Sin eventos registrados para hoy.")
        else:
            for _, ev in eventos_hoy_df.iterrows():
                with st.container(border=True):
                    ca, cb = st.columns([1, 7])
                    with ca:
                        st.markdown(f"**{str(ev.get('hora',''))[:5]}**")
                    with cb:
                        st.markdown(f"{ev.get('tipo','ℹ️')} **{ev.get('titulo','')}**")
                        if ev.get("descripcion"):
                            st.caption(ev.get("descripcion",""))
    else:
        st.info("Sin eventos en el itinerario.")

    st.divider()

    # ── FILA 4: Estado presupuesto familiar ───────────────────────
    st.markdown("### 👨‍👩‍👧‍👦 Estado del presupuesto familiar")
    emojis_persona = {"Papa": "👨", "Mama": "👩", "Analu": "👧", "Sebas": "🧒"}
    cols = st.columns(len(pagadores))

    alertas = []
    for i, persona in enumerate(pagadores):
        presup_p = presupuestos.get(persona, 0)
        gasto_p  = 0.0
        if not df_gst.empty and "pagado_por" in df_gst.columns:
            gasto_p = df_gst[df_gst["pagado_por"] == persona]["monto_mxn"].sum()
        resto_p  = presup_p - gasto_p
        pct_p    = min(gasto_p / presup_p, 1.0) if presup_p > 0 else 0
        color_p  = "#22c55e" if pct_p < 0.70 else ("#f59e0b" if pct_p < 0.90 else "#ef4444")

        with cols[i]:
            with st.container(border=True):
                st.markdown(
                    f"<div style='text-align:center;font-size:1.8rem'>"
                    f"{emojis_persona.get(persona,'👤')}</div>",
                    unsafe_allow_html=True
                )
                st.markdown(f"**{persona}**")
                st.caption(f"Presupuesto: {fmt_mxn(presup_p)}")
                st.markdown(f"""
                    <div style='background:#e5e7eb;border-radius:6px;height:10px;margin:4px 0'>
                        <div style='background:{color_p};width:{pct_p*100:.0f}%;
                                    height:10px;border-radius:6px'></div>
                    </div>
                    <p style='font-size:0.78rem;margin:2px 0 4px'>{pct_p*100:.0f}% usado</p>
                """, unsafe_allow_html=True)
                st.metric("Disponible", fmt_mxn(resto_p))

        if pct_p >= 0.80:
            alertas.append((persona, pct_p, presup_p, gasto_p))

    # ── ALERTAS ───────────────────────────────────────────────────
    if alertas:
        st.divider()
        st.markdown("### ⚠️ Alertas")
        for persona, pct, presup, gasto in alertas:
            nivel = "🔴 **Presupuesto agotado**" if pct >= 1.0 else "🟡 **Alerta: más del 80% consumido**"
            st.warning(
                f"{nivel} · {emojis_persona.get(persona,'👤')} **{persona}**: "
                f"{fmt_mxn(gasto)} de {fmt_mxn(presup)} ({pct*100:.0f}%)"
            )

# ═══════════════════════════════════════════════════════════════
#  MÓDULO: REGISTRO RÁPIDO (para usar sobre la marcha)
# ═══════════════════════════════════════════════════════════════

def modulo_registro_rapido(rol: str):
    if rol not in ["admin", "coeditor"]:
        st.warning("🔒 Solo administradores pueden registrar gastos.")
        return

    pagadores = get_pagadores()
    ciudades  = get_ciudades()

    st.header("⚡ Registro rápido")
    st.caption("Para capturar gastos sobre la marcha, sin formularios complejos.")

    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            rq_quien  = st.selectbox("¿Quién gastó?", pagadores, key="rq_quien")
            rq_rubro  = st.selectbox("Rubro", [r for r in RUBROS if r not in
                                               ("🏨 Hospedaje", "✈️ Vuelos", "🚆 Trenes")],
                                     key="rq_rubro")
        with c2:
            rq_desc   = st.text_input("¿En qué?", placeholder="ej: Helado en el Vaticano",
                                       key="rq_desc")
            rq_ciudad = st.selectbox("Ciudad", ciudades, key="rq_ciudad")
        with c3:
            rq_moneda = st.selectbox("Moneda", MONEDAS, key="rq_moneda")
            rq_monto  = st.number_input("Monto", min_value=0.0, step=1.0,
                                         format="%.2f", key="rq_monto")
            if rq_moneda != "MXN":
                rq_mxn = st.number_input("= MXN", min_value=0.0, step=1.0,
                                          format="%.2f", key="rq_mxn")
            else:
                rq_mxn = rq_monto

        if st.button("⚡ Guardar gasto rápido", type="primary", use_container_width=True):
            if not rq_desc or rq_monto <= 0:
                st.warning("Descripción y monto son obligatorios.")
                return
            hoy    = date.today()
            id_gst = gen_id("GST", hoy, rq_desc)
            id_evt = gen_id("EVT", hoy, rq_desc)
            ok1 = save_row("gastos", [
                id_gst, "", "", id_evt,
                str(hoy), rq_rubro, rq_desc,
                1, rq_monto, 0, rq_monto, rq_monto,
                rq_moneda, rq_mxn, rq_quien, ""
            ])
            ok2 = save_row("itinerario", [
                id_evt, str(hoy),
                datetime.now().strftime("%H:%M"),
                rq_rubro, rq_desc, "", rq_ciudad, "", "", ""
            ])
            if ok1 and ok2:
                st.success(f"✅ {rq_quien} · {rq_desc} · {fmt_mxn(rq_mxn)}")
                if rq_moneda != "MXN" and rq_monto > 0 and rq_mxn > 0:
                    st.caption(calc_tc(rq_monto, rq_mxn, rq_moneda))

# ═══════════════════════════════════════════════════════════════
#  MÓDULO: FAMILIA  (dashboard individual por persona)
# ═══════════════════════════════════════════════════════════════

def modulo_familia():
    st.header("👨‍👩‍👧‍👦 Presupuesto Familiar")

    presupuestos = load_presupuestos()
    pagadores    = get_pagadores()
    df           = gastos_preparados()
    emojis       = {"Papa": "👨", "Mama": "👩", "Analu": "👧", "Sebas": "🧒"}

    # Selector de persona
    persona_sel = st.segmented_control(
        "Ver detalle de:", options=pagadores,
        format_func=lambda p: f"{emojis.get(p,'👤')} {p}",
        default=pagadores[0]
    )
    st.divider()

    presup_p = presupuestos.get(persona_sel, 0)
    df_p = df[df["pagado_por"] == persona_sel] if (not df.empty and "pagado_por" in df.columns) else pd.DataFrame()

    total_p  = df_p["monto_mxn"].sum() if not df_p.empty else 0
    resto_p  = presup_p - total_p
    pct_p    = min(total_p / presup_p, 1.0) if presup_p > 0 else 0
    color_p  = "#22c55e" if pct_p < 0.70 else ("#f59e0b" if pct_p < 0.90 else "#ef4444")

    # KPIs
    k1, k2, k3, k4 = st.columns(4)
    k1.metric(f"{emojis.get(persona_sel,'👤')} Presupuesto", fmt_mxn(presup_p))
    k2.metric("Gastado",     fmt_mxn(total_p))
    k3.metric("Disponible",  fmt_mxn(resto_p))
    k4.metric("% Utilizado", f"{pct_p*100:.1f}%")

    st.markdown(f"""
        <div style='background:#e5e7eb;border-radius:8px;height:16px;margin:4px 0 20px'>
            <div style='background:{color_p};width:{pct_p*100:.1f}%;
                        height:16px;border-radius:8px'></div>
        </div>
    """, unsafe_allow_html=True)

    if pct_p >= 0.80:
        nivel = "🔴 Presupuesto agotado" if pct_p >= 1.0 else "🟡 Más del 80% consumido"
        st.warning(f"⚠️ {nivel}")

    if df_p.empty:
        st.info(f"Aún no hay gastos registrados para {persona_sel}.")
        return

    # Indicadores de tiempo real
    hoy        = date.today()
    dias_trans = dias_transcurridos()
    dias_tot   = dias_totales()

    gasto_hoy_p  = df_p[df_p["fecha"].dt.date == hoy]["monto_mxn"].sum() if not df_p.empty else 0
    prom_diario_p = total_p / dias_trans if dias_trans > 0 else 0
    proyeccion_p  = total_p + prom_diario_p * (dias_tot - dias_trans)

    st.subheader("📊 Indicadores en tiempo real")
    i1, i2, i3 = st.columns(3)
    i1.metric("Hoy",             fmt_mxn(gasto_hoy_p))
    i2.metric("Promedio diario", fmt_mxn(prom_diario_p))
    i3.metric("Proyección final", fmt_mxn(proyeccion_p),
              delta=fmt_mxn(proyeccion_p - presup_p), delta_color="inverse")

    # Gráfica por rubro
    st.subheader("Gastos por rubro")
    por_rubro = df_p.groupby("rubro")["monto_mxn"].sum().reset_index()
    por_rubro.columns = ["Rubro", "MXN"]
    st.bar_chart(por_rubro.set_index("Rubro"))

    # Historial de gastos
    st.subheader(f"Historial de {persona_sel}")
    cols_show = ["fecha", "rubro", "descripcion", "monto_total", "moneda", "monto_mxn"]
    cols_ok   = [c for c in cols_show if c in df_p.columns]
    rename_map = {"fecha": "Fecha", "rubro": "Rubro", "descripcion": "Descripción",
                  "monto_total": "Orig.", "moneda": "Mon.", "monto_mxn": "MXN"}
    df_show = (df_p[cols_ok].rename(columns=rename_map)
               .sort_values("Fecha", ascending=False))
    st.dataframe(df_show, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════════════════════
#  MÓDULO: NUEVO REGISTRO (formulario completo)
# ═══════════════════════════════════════════════════════════════

def formulario_nuevo_registro(rol: str):
    if rol not in ["admin", "coeditor"]:
        return

    ciudades  = get_ciudades()
    pagadores = get_pagadores()

    st.header("➕ Nuevo registro")
    st.caption("Un formulario → datos guardados en todas las hojas relacionadas.")

    tipo = st.segmented_control(
        "¿Qué vas a registrar?",
        options=["🏨 Hospedaje", "🚌 Transporte", "🎭 Actividad / Gasto"],
        default="🏨 Hospedaje"
    )
    st.divider()

    # ── HOSPEDAJE ────────────────────────────────────────────────
    if tipo == "🏨 Hospedaje":
        st.subheader("🏨 Hospedaje")
        c1, c2 = st.columns(2)
        with c1:
            h_ciudad  = st.selectbox("Ciudad", ciudades, key="h_ciudad")
            h_hotel   = st.text_input("Nombre del hotel / alojamiento")
            h_dir     = st.text_input("Dirección")
            h_tel     = st.text_input("Teléfono")
            h_maps    = st.text_input("Link Google Maps")
        with c2:
            h_conf    = st.text_input("Nº de confirmación")
            h_cin     = st.date_input("Check-in",  value=date(2026, 7, 13))
            h_cout    = st.date_input("Check-out", value=date(2026, 7, 16))
            h_pagador = st.selectbox("Pagado por", pagadores)

        noches = max((h_cout - h_cin).days, 1)
        st.info(f"📅 {noches} noche(s)")

        st.subheader("💰 Costo")
        h_modo = st.radio("Ingreso de monto", ["Total de la estadía", "Por noche"], horizontal=True)
        monto_orig_h, moneda_h, monto_mxn_h = widget_monto("h")

        if h_modo == "Total de la estadía":
            h_total = monto_orig_h
            h_x_n   = round(h_total / noches, 2) if noches else 0
        else:
            h_x_n   = monto_orig_h
            h_total = round(h_x_n * noches, 2)
        if moneda_h == "MXN":
            monto_mxn_h = h_total

        imp_h   = st.number_input("Impuestos incluidos",
                                   min_value=0.0, step=1.0, format="%.2f", key="h_imp",
                                   help="0 si el monto ya es todo incluido.")
        h_notas = st.text_area("Notas adicionales", height=60)

        ka, kb, kc = st.columns(3)
        ka.metric("Total estadía",   fmt_orig(h_total, moneda_h))
        kb.metric("Costo por noche", fmt_orig(h_x_n,   moneda_h))
        kc.metric("Total en MXN",    fmt_mxn(monto_mxn_h))

        if st.button("💾 Guardar hospedaje", type="primary", use_container_width=True):
            if not h_hotel:
                st.warning("El nombre del hotel es obligatorio.")
                return
            id_hsp  = gen_id("HSP", h_cin, h_ciudad)
            id_gst  = gen_id("GST", h_cin, h_ciudad + "H")
            id_cin  = gen_id("EVT", h_cin,  "CHKIN")
            id_cout = gen_id("EVT", h_cout, "CHKOUT")

            ok1 = save_row("alojamiento", [
                id_hsp, h_ciudad, h_hotel, h_dir, h_tel,
                h_conf, str(h_cin), str(h_cout), h_maps
            ])
            ok2 = save_row("gastos", [
                id_gst, id_hsp, "", "",
                str(h_cin), "🏨 Hospedaje", f"Hotel {h_hotel} – {h_ciudad}",
                noches, h_x_n, imp_h, round(h_total - imp_h, 2), h_total,
                moneda_h, monto_mxn_h, h_pagador, h_notas
            ])
            ok3 = save_row("itinerario", [
                id_cin, str(h_cin), "15:00", "🏨 Check-in",
                f"Check-in {h_hotel}", h_dir, h_ciudad, id_hsp, "", h_conf
            ])
            ok4 = save_row("itinerario", [
                id_cout, str(h_cout), "12:00", "🏨 Check-out",
                f"Check-out {h_hotel}", "", h_ciudad, id_hsp, "", ""
            ])
            if ok1 and ok2 and ok3 and ok4:
                st.success(f"✅ `{id_hsp}` → alojamiento · gastos · itinerario")
                st.balloons()

    # ── TRANSPORTE ───────────────────────────────────────────────
    elif tipo == "🚌 Transporte":
        st.subheader("🚌 Transporte / Traslado")
        c1, c2 = st.columns(2)
        with c1:
            t_tipo     = st.selectbox("Tipo", TIPOS_TRANSP)
            t_prov     = st.text_input("Proveedor / Aerolínea", placeholder="ej: Iberia, Renfe")
            t_num      = st.text_input("Nº vuelo / tren", placeholder="ej: IB3456")
            t_conf     = st.text_input("Código de confirmación")
            t_doc      = st.text_input("Link Google Drive (PDF/QR/boarding pass)")
        with c2:
            t_fecha    = st.date_input("Fecha de salida", value=date(2026, 7, 13))
            t_hora_sal = st.time_input("Hora de salida")
            t_hora_llg = st.time_input("Hora de llegada estimada")
            t_anticip  = st.number_input("Minutos de anticipación",
                                          min_value=0, max_value=300, value=90, step=15)

        st.markdown("**📍 Origen**")
        c3, c4 = st.columns(2)
        with c3:
            t_oc      = st.selectbox("Ciudad origen", ciudades, key="t_oc")
            t_ol      = st.text_input("Aeropuerto / Estación", placeholder="ej: Barajas T4")
        with c4:
            t_od      = st.text_input("Dirección origen")
            t_ins_ida = st.text_area("Cómo llegar", placeholder="ej: Uber del hotel a las 5am",
                                      height=75)

        st.markdown("**🏁 Destino**")
        c5, c6 = st.columns(2)
        with c5:
            t_dc      = st.selectbox("Ciudad destino", ciudades, key="t_dc")
            t_dl      = st.text_input("Aeropuerto / Estación destino",
                                       placeholder="ej: Barcelona Sants")
        with c6:
            t_dd      = st.text_input("Dirección destino")
            t_ins_llg = st.text_area("Instrucciones al llegar",
                                      placeholder="ej: Metro L3 dirección centro", height=75)

        st.markdown("**💰 Costo**")
        t_pagador = st.selectbox("Pagado por", pagadores, key="t_pag")
        monto_orig_t, moneda_t, monto_mxn_t = widget_monto("t")
        t_notas = st.text_input("Notas")

        dt_lim   = datetime.combine(t_fecha, t_hora_sal) - timedelta(minutes=int(t_anticip))
        hora_lim = dt_lim.strftime("%H:%M")
        st.info(f"⏰ Debes estar en **{t_ol or 'el punto de salida'}** a las **{hora_lim}**")

        if st.button("💾 Guardar transporte", type="primary", use_container_width=True):
            id_trn  = gen_id("TRN", t_fecha, t_num or t_prov)
            id_gst  = gen_id("GST", t_fecha, t_num or t_prov)
            id_evt  = gen_id("EVT", t_fecha, t_num or t_prov)
            titulo  = f"{t_tipo} {t_prov} {t_num}".strip()
            rubro_g = ("✈️ Vuelos"  if "Vuelo" in t_tipo else
                       "🚆 Trenes"  if "Tren"  in t_tipo else
                       "🚗 Transporte local")

            ok1 = save_row("transportes", [
                id_trn, str(t_fecha), str(t_hora_sal)[:5], str(t_hora_llg)[:5],
                t_tipo, t_prov, t_num, t_conf,
                t_oc, t_ol, t_od, t_dc, t_dl, t_dd,
                hora_lim, t_ins_ida, t_ins_llg,
                t_doc, monto_orig_t, moneda_t, monto_mxn_t, t_pagador, t_notas
            ])
            ok2 = save_row("gastos", [
                id_gst, "", id_trn, "",
                str(t_fecha), rubro_g, titulo,
                1, monto_orig_t, 0, monto_orig_t, monto_orig_t,
                moneda_t, monto_mxn_t, t_pagador, t_notas
            ])
            ok3 = save_row("itinerario", [
                id_evt, str(t_fecha), str(t_hora_sal)[:5], t_tipo, titulo,
                f"Sale: {t_ol} | Llega: {t_dl} | Límite: {hora_lim}",
                t_oc, "", id_trn, t_conf
            ])
            if ok1 and ok2 and ok3:
                st.success(f"✅ `{id_trn}` → transportes · gastos · itinerario")

    # ── ACTIVIDAD / GASTO ────────────────────────────────────────
    else:
        st.subheader("🎭 Actividad / Gasto general")
        c1, c2 = st.columns(2)
        with c1:
            a_fecha   = st.date_input("Fecha", value=date.today())
            a_hora    = st.time_input("Hora")
            a_ciudad  = st.selectbox("Ciudad", ciudades, key="a_ciudad")
            a_rubro   = st.selectbox("Rubro",
                                      [r for r in RUBROS if r not in
                                       ("🏨 Hospedaje", "✈️ Vuelos", "🚆 Trenes")])
        with c2:
            a_titulo  = st.text_input("Nombre / descripción")
            a_detalle = st.text_area("Detalles", height=75)
            a_pagador = st.selectbox("Pagado por", pagadores, key="a_pag")

        monto_orig_a, moneda_a, monto_mxn_a = widget_monto("a")
        a_al_itin = st.checkbox("Agregar también al itinerario", value=True)
        a_notas   = st.text_input("Notas")

        if st.button("💾 Guardar", type="primary", use_container_width=True):
            if not a_titulo:
                st.warning("La descripción es obligatoria.")
                return
            id_gst = gen_id("GST", a_fecha, a_titulo)
            id_evt = gen_id("EVT", a_fecha, a_titulo)

            ok1 = save_row("gastos", [
                id_gst, "", "", id_evt if a_al_itin else "",
                str(a_fecha), a_rubro, a_titulo,
                1, monto_orig_a, 0, monto_orig_a, monto_orig_a,
                moneda_a, monto_mxn_a, a_pagador, a_notas
            ])
            ok2 = True
            if a_al_itin:
                ok2 = save_row("itinerario", [
                    id_evt, str(a_fecha), str(a_hora)[:5],
                    a_rubro, a_titulo, a_detalle, a_ciudad, "", "", ""
                ])
            if ok1 and ok2:
                st.success(f"✅ {a_titulo} · {fmt_mxn(monto_mxn_a)}")

# ═══════════════════════════════════════════════════════════════
#  MÓDULO: ITINERARIO
# ═══════════════════════════════════════════════════════════════

def modulo_itinerario():
    st.header("📅 Itinerario")
    df = get_df("itinerario")
    if df.empty:
        st.info("Aún no hay eventos. Usa '➕ Nuevo registro' para empezar.")
        return

    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df = df.dropna(subset=["fecha"]).sort_values(["fecha", "hora"])

    ciudades_disp = ["Todas"] + sorted(df["ciudad"].dropna().unique().tolist())
    filtro = st.selectbox("Filtrar por ciudad", ciudades_disp)
    if filtro != "Todas":
        df = df[df["ciudad"] == filtro]

    for f in df["fecha"].dt.date.unique():
        eventos  = df[df["fecha"].dt.date == f]
        label    = pd.Timestamp(f).strftime("%A %d de %B").capitalize()
        ciudad_d = eventos["ciudad"].dropna().iloc[0] if not eventos.empty else ""
        es_hoy   = (f == date.today())
        prefix   = "📍 **HOY** — " if es_hoy else ""
        st.markdown(
            f"### {prefix}{label} &nbsp;"
            f"<span style='font-size:0.8rem;color:#888'>📍 {ciudad_d}</span>",
            unsafe_allow_html=True
        )
        for _, ev in eventos.iterrows():
            hora = str(ev.get("hora", ""))[:5]
            tipo = ev.get("tipo", "ℹ️")
            tit  = ev.get("titulo", "")
            desc = ev.get("descripcion", "")
            conf = ev.get("confirmacion", "")
            with st.container(border=True):
                ca, cb = st.columns([1, 7])
                with ca:
                    st.markdown(f"**{hora}**")
                with cb:
                    st.markdown(f"{tipo} &nbsp;**{tit}**")
                    if desc: st.caption(desc)
                    if conf: st.caption(f"🔖 `{conf}`")
        st.divider()

# ═══════════════════════════════════════════════════════════════
#  MÓDULO: TRANSPORTES
# ═══════════════════════════════════════════════════════════════

def modulo_transportes():
    st.header("🚌 Transportes")
    df = get_df("transportes")
    if df.empty:
        st.info("Aún no hay transportes registrados.")
        return

    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df = df.sort_values("fecha")

    for _, t in df.iterrows():
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 3, 1])
            with c1:
                st.markdown(
                    f"### {t.get('tipo','')} &nbsp; {t.get('proveedor','')} "
                    f"`{t.get('numero','')}`"
                )
                st.markdown(
                    f"📅 **{str(t.get('fecha',''))[:10]}** &nbsp;&nbsp;"
                    f"🛫 **{t.get('hora_salida','')}** → 🛬 **{t.get('hora_llegada','')}**"
                )
                st.markdown(f"**Origen:** {t.get('origen_ciudad','')} — {t.get('origen_lugar','')}")
                st.markdown(f"**Destino:** {t.get('destino_ciudad','')} — {t.get('destino_lugar','')}")
            with c2:
                st.markdown(f"⏰ **Estar ahí a las {t.get('hora_limite','')}**")
                if t.get("instrucciones_ida"):     st.caption(f"📌 {t.get('instrucciones_ida','')}")
                if t.get("instrucciones_llegada"): st.caption(f"🏁 {t.get('instrucciones_llegada','')}")
                orig_dir = t.get("origen_direccion","")
                if orig_dir:
                    st.link_button("🗺️ Maps origen",
                                   f"https://maps.google.com/?q={orig_dir.replace(' ','+')}")
            with c3:
                st.metric("Costo MXN", fmt_mxn(t.get("monto_mxn", 0)))
                st.caption(fmt_orig(t.get("monto",""), t.get("moneda","")))
                tc_s = calc_tc(float(t.get("monto",0) or 0),
                               float(t.get("monto_mxn",0) or 0),
                               str(t.get("moneda","MXN")))
                if tc_s: st.caption(tc_s)
                if t.get("confirmacion"): st.code(t.get("confirmacion",""), language=None)
                if t.get("link_documento"): st.link_button("📄 Ver doc.", t.get("link_documento",""))

# ═══════════════════════════════════════════════════════════════
#  MÓDULO: ALOJAMIENTO
# ═══════════════════════════════════════════════════════════════

def modulo_alojamiento():
    st.header("🏨 Alojamiento")
    df     = get_df("alojamiento")
    df_gst = gastos_preparados()

    if df.empty:
        st.info("Aún no hay hoteles registrados.")
        return

    hoy = date.today()
    for _, h in df.iterrows():
        id_hsp = h.get("id_hospedaje","")
        activo = False
        try:
            cin  = pd.to_datetime(h.get("checkin")).date()
            cout = pd.to_datetime(h.get("checkout")).date()
            activo = cin <= hoy <= cout
        except Exception:
            pass

        with st.container(border=True):
            if activo:
                st.markdown("🟢 **Hospedaje actual**")
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"### 🏨 {h.get('hotel','')}")
                st.markdown(f"📍 **{h.get('ciudad','')}** &nbsp; {h.get('direccion','')}")
                st.markdown(f"📞 `{h.get('telefono','')}`")
                if h.get("confirmacion"):
                    st.markdown(f"🔖 `{h.get('confirmacion','')}`")
                if h.get("maps_url"):
                    st.link_button("🗺️ Ver en Maps", h.get("maps_url",""))
            with c2:
                st.markdown(f"**Check-in:** {h.get('checkin','')}")
                st.markdown(f"**Check-out:** {h.get('checkout','')}")
                try:
                    noches = (pd.to_datetime(h.get("checkout")) -
                              pd.to_datetime(h.get("checkin"))).days
                    st.caption(f"{noches} noche(s)")
                except Exception:
                    pass
                if (not df_gst.empty and "id_hospedaje" in df_gst.columns and id_hsp):
                    g = df_gst[df_gst["id_hospedaje"] == id_hsp]
                    if not g.empty:
                        st.metric("Total pagado", fmt_mxn(g["monto_mxn"].sum()))

# ═══════════════════════════════════════════════════════════════
#  MÓDULO: PRESUPUESTO (con balance filtrado)
# ═══════════════════════════════════════════════════════════════

def modulo_presupuesto():
    st.header("💰 Presupuesto y Gastos")

    presupuestos = load_presupuestos()
    pagadores    = get_pagadores()
    df           = gastos_preparados()

    if df.empty:
        st.info("Aún no hay gastos registrados.")
        return

    df["semana"] = df["fecha"].dt.isocalendar().week.astype(str)
    presup_total = presupuestos.get("total", 0)
    total        = df["monto_mxn"].sum()
    resto        = presup_total - total
    pct          = min(total / presup_total, 1.0) if presup_total > 0 else 0
    color        = "#22c55e" if pct < 0.70 else ("#f59e0b" if pct < 0.90 else "#ef4444")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Gastado",     fmt_mxn(total))
    k2.metric("Presupuesto", fmt_mxn(presup_total))
    k3.metric("Disponible",  fmt_mxn(resto))
    k4.metric("% Utilizado", f"{pct*100:.1f}%")

    st.markdown(f"""
        <div style='background:var(--secondary-background-color);border-radius:8px;
                    height:14px;margin:4px 0 20px'>
            <div style='background:{color};width:{pct*100:.1f}%;
                        height:14px;border-radius:8px'></div>
        </div>
    """, unsafe_allow_html=True)

    # ── Filtros ───────────────────────────────────────────────────
    st.subheader("Análisis")
    cf1, cf2, cf3 = st.columns(3)
    f_agrup   = cf1.selectbox("Agrupar por", ["Rubro", "Semana", "Pagador"])
    f_pagador = cf2.selectbox("Pagador", ["Todos"] + pagadores)
    f_rubro   = cf3.selectbox("Rubro",   ["Todos"] + RUBROS)

    df_f = df.copy()
    if f_pagador != "Todos" and "pagado_por" in df_f.columns:
        df_f = df_f[df_f["pagado_por"] == f_pagador]
    if f_rubro != "Todos" and "rubro" in df_f.columns:
        df_f = df_f[df_f["rubro"] == f_rubro]

    col_agrup = {"Rubro": "rubro", "Semana": "semana", "Pagador": "pagado_por"}[f_agrup]
    if col_agrup in df_f.columns and not df_f.empty:
        agg = df_f.groupby(col_agrup)["monto_mxn"].sum().reset_index()
        agg.columns = [f_agrup, "MXN"]
        st.bar_chart(agg.set_index(f_agrup))

    # ── Tabla detalle ─────────────────────────────────────────────
    st.subheader("Detalle de gastos")
    cols_map = {
        "id_gasto": "ID", "fecha": "Fecha", "rubro": "Rubro",
        "descripcion": "Descripción", "unidades": "Nts/Uds",
        "monto_total": "Total orig.", "moneda": "Mon.",
        "monto_mxn": "Total MXN", "pagado_por": "Pagador",
        "id_hospedaje": "Ref. Hotel", "id_transporte": "Ref. Transp."
    }
    cols_ok = [c for c in cols_map if c in df_f.columns]
    df_show = (df_f[cols_ok].rename(columns=cols_map)
               .sort_values("Fecha", ascending=False))
    st.dataframe(df_show, use_container_width=True, hide_index=True)

    # ── Balance por persona (FILTRADO) ────────────────────────────
    st.subheader("Balance por persona" + (f" — {f_pagador}" if f_pagador != "Todos" else ""))
    emojis_p = {"Papa": "👨", "Mama": "👩", "Analu": "👧", "Sebas": "🧒"}
    total_filtrado = df_f["monto_mxn"].sum() if not df_f.empty else 0

    personas_bal = [f_pagador] if f_pagador != "Todos" else pagadores
    cols_bal = st.columns(len(personas_bal))
    for i, persona in enumerate(personas_bal):
        presup_p = presupuestos.get(persona, 0)
        if "pagado_por" in df_f.columns:
            gasto_p_filtrado = df_f[df_f["pagado_por"] == persona]["monto_mxn"].sum()
        else:
            gasto_p_filtrado = 0
        pct_p    = min(gasto_p_filtrado / presup_p, 1.0) if presup_p > 0 else 0
        pct_del  = gasto_p_filtrado / total_filtrado * 100 if total_filtrado > 0 else 0
        color_p  = "#22c55e" if pct_p < 0.70 else ("#f59e0b" if pct_p < 0.90 else "#ef4444")

        with cols_bal[i]:
            with st.container(border=True):
                st.markdown(f"**{emojis_p.get(persona,'👤')} {persona}**")
                st.metric("Gastado (filtro)", fmt_mxn(gasto_p_filtrado))
                st.caption(f"{pct_del:.1f}% del total filtrado")
                st.markdown(f"""
                    <div style='background:#e5e7eb;border-radius:6px;height:8px;margin:4px 0'>
                        <div style='background:{color_p};width:{pct_p*100:.0f}%;
                                    height:8px;border-radius:6px'></div>
                    </div>
                    <p style='font-size:0.75rem;margin:0;color:#888'>{pct_p*100:.0f}% de su presupuesto</p>
                """, unsafe_allow_html=True)

    # ── Detalle por hospedaje ─────────────────────────────────────
    st.subheader("Detalle por hospedaje")
    df_hsp = get_df("alojamiento")
    if not df_hsp.empty and "id_hospedaje" in df.columns:
        for _, h in df_hsp.iterrows():
            id_h     = h.get("id_hospedaje","")
            gastos_h = df_f[df_f.get("id_hospedaje","") == id_h] if "id_hospedaje" in df_f.columns else pd.DataFrame()
            if not gastos_h.empty:
                total_h = gastos_h["monto_mxn"].sum()
                with st.expander(f"🏨 {h.get('hotel','')} — {fmt_mxn(total_h)}"):
                    st.dataframe(
                        gastos_h[["fecha","descripcion","unidades","monto_total","moneda","monto_mxn"]],
                        use_container_width=True, hide_index=True
                    )

# ═══════════════════════════════════════════════════════════════
#  MÓDULO: DOCUMENTOS
# ═══════════════════════════════════════════════════════════════

def modulo_documentos(rol: str):
    if rol not in ["admin", "coeditor"]:
        st.warning("🔒 Esta sección es solo para administradores.")
        return

    st.header("📄 Documentos Importantes")
    df = get_df("documentos")

    with st.expander("➕ Agregar documento"):
        c1, c2 = st.columns(2)
        with c1:
            d_tipo = st.selectbox("Tipo", ["Pasaporte","Visa","Seguro de viaje",
                                           "Tarjeta de crédito","Otro"])
            d_desc = st.text_input("Descripción (ej: Pasaporte Papá)")
            d_num  = st.text_input("Número / código")
        with c2:
            d_venc  = st.date_input("Vencimiento", value=date(2027, 1, 1))
            d_notas = st.text_area("Notas", height=70)
        if st.button("💾 Guardar documento", type="primary"):
            if d_desc:
                if save_row("documentos", [d_tipo, d_desc, d_num, str(d_venc), d_notas]):
                    st.success("✅ Documento guardado")
            else:
                st.warning("La descripción es obligatoria.")

    if df.empty:
        st.info("Aún no hay documentos.")
        return

    for tipo_d in (df["tipo"].unique() if "tipo" in df.columns else []):
        st.subheader(f"📋 {tipo_d}")
        for _, d in df[df["tipo"] == tipo_d].iterrows():
            with st.container(border=True):
                ca, cb = st.columns([3, 1])
                with ca:
                    st.markdown(f"**{d.get('descripcion','')}**")
                    if d.get("numero"):  st.code(d.get("numero",""), language=None)
                    if d.get("notas"):   st.caption(d.get("notas",""))
                with cb:
                    st.markdown(f"Vence:\n**{d.get('vencimiento','')}**")

# ═══════════════════════════════════════════════════════════════
#  APP PRINCIPAL
# ═══════════════════════════════════════════════════════════════

def main():
    st.set_page_config(
        page_title="FamilyTrip Europe 2026",
        page_icon="🌍",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    if "logueado" not in st.session_state:
        st.session_state.logueado = False

    if not st.session_state.logueado:
        login_screen()
        return

    usuario = st.session_state.usuario
    rol     = usuario["rol"]
    nombre  = usuario["nombre"]
    emoji   = usuario["emoji"]

    with st.sidebar:
        st.markdown("## 🌍 FamilyTrip\n**Europa 2026**")
        st.divider()
        st.markdown(f"{emoji} **{nombre}**")
        st.caption(f"Rol: {rol.capitalize()}")
        st.divider()

        opciones = [
            "🏠 Inicio",
            "📅 Itinerario",
            "🚌 Transportes",
            "🏨 Alojamiento",
            "💰 Presupuesto",
            "👨‍👩‍👧‍👦 Familia",
            "📄 Documentos",
        ]
        if rol in ["admin", "coeditor"]:
            opciones.insert(1, "⚡ Registro rápido")
            opciones.insert(2, "➕ Nuevo registro")

        pagina = st.radio("Navegación", opciones, label_visibility="collapsed")
        st.divider()
        if st.button("🚪 Cerrar sesión", use_container_width=True):
            logout()

    if   pagina == "🏠 Inicio":              modulo_dashboard(usuario)
    elif pagina == "⚡ Registro rápido":     modulo_registro_rapido(rol)
    elif pagina == "➕ Nuevo registro":      formulario_nuevo_registro(rol)
    elif pagina == "📅 Itinerario":          modulo_itinerario()
    elif pagina == "🚌 Transportes":         modulo_transportes()
    elif pagina == "🏨 Alojamiento":         modulo_alojamiento()
    elif pagina == "💰 Presupuesto":         modulo_presupuesto()
    elif pagina == "👨‍👩‍👧‍👦 Familia":            modulo_familia()
    elif pagina == "📄 Documentos":          modulo_documentos(rol)

if __name__ == "__main__":
    main()
