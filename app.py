import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, date, timedelta
import json
import re

# ═══════════════════════════════════════════════════════════════
#  CONFIGURACIÓN — ajusta estos valores antes de desplegar
# ═══════════════════════════════════════════════════════════════

SHEET_NAME = "FamilyTrip Europe 2026"

PINS = {
    "1921": {"nombre": "Papá",   "rol": "admin",    "emoji": "👨"},
    "2115": {"nombre": "Mamá",   "rol": "coeditor", "emoji": "👩"},
    "2408": {"nombre": "Analu", "rol": "viewer",   "emoji": "🧒"},
    "2911": {"nombre": "Sebas", "rol": "viewer",   "emoji": "🧒"},
}

TC_EUR_MXN          = 21.50    # 1 EUR = ? MXN  — actualiza cuando quieras
TC_USD_MXN          = 17.80    # 1 USD = ? MXN
PRESUPUESTO_MXN     = 180_000  # Presupuesto total del viaje en pesos

CIUDADES     = ["Madrid", "Barcelona", "París", "Bruselas", "Brujas", "Strasburgo", "Milan", "Venecia", "Florencia", "Roma", "Napoles", "Capri", "Asturias", "Otros"]
MONEDAS      = ["MXN", "EUR", "USD"]
PAGADORES    = ["Papá", "Mamá"]
RUBROS       = ["🏨 Hospedaje", "✈️ Vuelos", "🚆 Trenes", "🚗 Transporte local",
                "🍽️ Comida", "🎭 Actividades", "🛍️ Compras", "💊 Farmacia", "🔧 Otros"]
TIPOS_TRANSP = ["✈️ Vuelo", "🚄 Tren AVE", "🚆 Tren regional", "🚌 Autobús",
                "⛴️ Ferry", "🚗 Renta de auto", "🚕 Uber/Taxi", "🚇 Metro/Bus ciudad"]

# ═══════════════════════════════════════════════════════════════
#  GENERADOR DE IDs RELACIONALES
# ═══════════════════════════════════════════════════════════════

def _slug(text: str, maxlen: int = 6) -> str:
    """Convierte texto a slug corto: 'Barcelona' → 'BCN'"""
    text = text.upper().strip()
    # Abreviaturas conocidas
    abrevs = {
        "MADRID": "MAD", "BARCELONA": "BCN", "PARÍS": "PAR", "PARIS": "PAR",
        "ROMA": "ROM", "LISBOA": "LIS", "AMSTERDAM": "AMS", "OTRA": "OTR",
        "VUELO": "VUE", "TREN AVE": "AVE", "TREN REGIONAL": "TRR",
        "AUTOBÚS": "BUS", "AUTOBUS": "BUS", "FERRY": "FRY",
        "RENTA DE AUTO": "CAR", "UBER/TAXI": "UBR", "METRO/BUS CIUDAD": "MET",
    }
    for key, val in abrevs.items():
        if key in text:
            return val
    # Si no hay abreviatura: tomar iniciales de palabras o primeras letras
    words = re.sub(r'[^A-Z0-9 ]', '', text).split()
    if len(words) >= 2:
        return "".join(w[0] for w in words[:maxlen])
    return text[:maxlen]

def gen_id(prefix: str, fecha: date, extra: str = "") -> str:
    """
    Genera ID único legible:
      HSP-20250714-BCN
      TRN-20250713-IB3456
      EVT-20250714-153042
      GST-20250714-153042
    """
    date_str = fecha.strftime("%Y%m%d")
    if extra:
        suffix = _slug(extra)[:8]
    else:
        suffix = datetime.now().strftime("%H%M%S")
    return f"{prefix}-{date_str}-{suffix}"

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

@st.cache_data(ttl=30)
def get_df(sheet_name: str) -> pd.DataFrame:
    try:
        ws = get_client().open(SHEET_NAME).worksheet(sheet_name)
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
#  UTILIDADES
# ═══════════════════════════════════════════════════════════════

def a_mxn(monto: float, moneda: str) -> float:
    if moneda == "EUR": return round(monto * TC_EUR_MXN, 2)
    if moneda == "USD": return round(monto * TC_USD_MXN, 2)
    return round(monto, 2)

def fmt_mxn(v) -> str:
    try:    return f"${float(v):,.0f} MXN"
    except: return "—"

def fmt_orig(monto, moneda) -> str:
    try:
        symbols = {"MXN": "$", "EUR": "€", "USD": "USD $"}
        s = symbols.get(str(moneda), "")
        return f"{s}{float(monto):,.2f} {moneda}"
    except: return "—"

# ═══════════════════════════════════════════════════════════════
#  AUTENTICACIÓN
# ═══════════════════════════════════════════════════════════════

def login_screen():
    st.markdown("""
        <div style='text-align:center;padding:2.5rem 0 1.5rem'>
            <div style='font-size:56px'>🌍</div>
            <h1 style='margin:0.4rem 0 0.2rem;font-size:1.9rem;font-weight:500'>
                FamilyTrip Europe 2025
            </h1>
            <p style='color:#888;margin:0'>13 Jul – 15 Ago &nbsp;·&nbsp; ¡Nos vamos!</p>
        </div>
    """, unsafe_allow_html=True)
    _, col, _ = st.columns([1, 2, 1])
    with col:
        pin = st.text_input("PIN", type="password", max_chars=4,
                            placeholder="Ingresa tu PIN de 4 dígitos",
                            label_visibility="collapsed")
        if st.button("Entrar →", use_container_width=True, type="primary"):
            if pin in PINS:
                st.session_state.usuario  = PINS[pin]
                st.session_state.logueado = True
                st.rerun()
            else:
                st.error("PIN incorrecto.")

def logout():
    st.session_state.clear()
    st.rerun()

# ═══════════════════════════════════════════════════════════════
#  FORMULARIO INTELIGENTE UNIFICADO
# ═══════════════════════════════════════════════════════════════

def formulario_nuevo_registro(rol: str):
    if rol not in ["admin", "coeditor"]:
        return

    st.header("➕ Nuevo registro")
    st.caption("Un formulario → datos guardados en todas las hojas relacionadas automáticamente.")

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
            h_ciudad  = st.selectbox("Ciudad", CIUDADES, key="h_ciudad")
            h_hotel   = st.text_input("Nombre del hotel / alojamiento")
            h_dir     = st.text_input("Dirección")
            h_tel     = st.text_input("Teléfono")
            h_maps    = st.text_input("Link Google Maps")
        with c2:
            h_conf    = st.text_input("Nº de confirmación")
            h_cin     = st.date_input("Check-in",  value=date(2025, 7, 13))
            h_cout    = st.date_input("Check-out", value=date(2025, 7, 16))
            h_pagador = st.selectbox("Pagado por", PAGADORES)

        noches = max((h_cout - h_cin).days, 1)
        st.info(f"📅 {noches} noche(s)")

        st.subheader("💰 Desglose de costo")
        c3, c4 = st.columns(2)
        with c3:
            h_moneda = st.selectbox("Moneda", MONEDAS, key="h_moneda")
            h_modo   = st.radio("Ingreso de monto",
                                ["Total de la estadía", "Por noche"], horizontal=True)
        with c4:
            if h_modo == "Total de la estadía":
                h_base  = st.number_input("Tarifa base total",  min_value=0.0, step=10.0, format="%.2f")
                h_imp   = st.number_input("Impuestos / cargos", min_value=0.0, step=1.0,  format="%.2f")
                h_total = h_base + h_imp
                h_x_n   = round(h_total / noches, 2)
            else:
                h_x_n   = st.number_input("Tarifa base por noche",  min_value=0.0, step=10.0, format="%.2f")
                h_imp_n = st.number_input("Impuestos por noche",     min_value=0.0, step=1.0,  format="%.2f")
                h_base  = round(h_x_n * noches, 2)
                h_imp   = round(h_imp_n * noches, 2)
                h_total = h_base + h_imp

        h_mxn = a_mxn(h_total, h_moneda)
        ka, kb, kc = st.columns(3)
        ka.metric("Total estadía",   fmt_orig(h_total, h_moneda))
        kb.metric("Costo por noche", fmt_orig(h_x_n,   h_moneda))
        kc.metric("Total en MXN",    fmt_mxn(h_mxn))

        h_notas = st.text_area("Notas adicionales", height=70)

        if st.button("💾 Guardar hospedaje", type="primary", use_container_width=True):
            if not h_hotel:
                st.warning("El nombre del hotel es obligatorio.")
                return

            # Generar ID principal del hospedaje
            id_hsp = gen_id("HSP", h_cin, h_ciudad)

            # 1 → alojamiento
            ok1 = save_row("alojamiento", [
                id_hsp, h_ciudad, h_hotel, h_dir, h_tel,
                h_conf, str(h_cin), str(h_cout), h_maps
            ])
            # 2 → gastos (con FK al hospedaje)
            id_gst = gen_id("GST", h_cin, h_ciudad + "HSP")
            ok2 = save_row("gastos", [
                id_gst, id_hsp, "", "",
                str(h_cin), "🏨 Hospedaje",
                f"Hotel {h_hotel} – {h_ciudad}",
                noches, h_x_n, h_imp, h_base, h_total,
                h_moneda, h_mxn, h_pagador, h_notas
            ])
            # 3 → itinerario: check-in (con FK al hospedaje)
            ok3 = save_row("itinerario", [
                gen_id("EVT", h_cin, "CHECKIN"),
                str(h_cin), "15:00", "🏨 Check-in",
                f"Check-in {h_hotel}", h_dir, h_ciudad,
                id_hsp, "", h_conf
            ])
            # 4 → itinerario: check-out
            ok4 = save_row("itinerario", [
                gen_id("EVT", h_cout, "CHECKOUT"),
                str(h_cout), "12:00", "🏨 Check-out",
                f"Check-out {h_hotel}", "", h_ciudad,
                id_hsp, "", ""
            ])

            if ok1 and ok2 and ok3 and ok4:
                st.success(
                    f"✅ Guardado · ID: `{id_hsp}`\n\n"
                    f"→ alojamiento · gastos · itinerario (check-in + check-out)"
                )
                st.caption(f"Costo: {fmt_orig(h_total, h_moneda)} = {fmt_mxn(h_mxn)}")
                st.balloons()

    # ── TRANSPORTE ───────────────────────────────────────────────
    elif tipo == "🚌 Transporte":
        st.subheader("🚌 Transporte / Traslado")
        c1, c2 = st.columns(2)
        with c1:
            t_tipo      = st.selectbox("Tipo de transporte", TIPOS_TRANSP)
            t_prov      = st.text_input("Proveedor / Aerolínea",
                                         placeholder="ej: Iberia, Renfe")
            t_num       = st.text_input("Nº vuelo / tren / reserva",
                                         placeholder="ej: IB3456, AVE02143")
            t_conf      = st.text_input("Código de confirmación")
            t_doc       = st.text_input("Link Google Drive (PDF / QR / boarding pass)")
        with c2:
            t_fecha     = st.date_input("Fecha de salida", value=date(2026, 7, 13))
            t_hora_sal  = st.time_input("Hora de salida")
            t_hora_llg  = st.time_input("Hora de llegada estimada")
            t_anticip   = st.number_input("Minutos de anticipación al punto de salida",
                                           min_value=0, max_value=300, value=90, step=15)

        st.markdown("**📍 Origen**")
        c3, c4 = st.columns(2)
        with c3:
            t_oc = st.selectbox("Ciudad origen", CIUDADES, key="t_oc")
            t_ol = st.text_input("Aeropuerto / Estación",
                                  placeholder="ej: Aeropuerto Madrid-Barajas T4")
        with c4:
            t_od       = st.text_input("Dirección origen (para Maps)")
            t_instrida = st.text_area("Cómo llegar / instrucciones",
                                       placeholder="ej: Tomar Uber del hotel. Salir a las 5:00am",
                                       height=80)

        st.markdown("**🏁 Destino**")
        c5, c6 = st.columns(2)
        with c5:
            t_dc = st.selectbox("Ciudad destino", CIUDADES, key="t_dc")
            t_dl = st.text_input("Aeropuerto / Estación destino",
                                  placeholder="ej: Estación Barcelona Sants")
        with c6:
            t_dd       = st.text_input("Dirección destino (para Maps)")
            t_instrllg = st.text_area("Instrucciones al llegar",
                                       placeholder="ej: Tomar Metro L3 dirección centro",
                                       height=80)

        st.markdown("**💰 Costo**")
        c7, c8 = st.columns(2)
        with c7:
            t_moneda  = st.selectbox("Moneda", MONEDAS, key="t_moneda")
            t_monto   = st.number_input("Monto", min_value=0.0, step=10.0, format="%.2f")
            t_pagador = st.selectbox("Pagado por", PAGADORES, key="t_pag")
            t_notas   = st.text_area("Notas", height=60)
        with c8:
            t_mxn = a_mxn(t_monto, t_moneda)
            st.metric("Equivalente MXN", fmt_mxn(t_mxn))

        dt_lim    = datetime.combine(t_fecha, t_hora_sal) - timedelta(minutes=int(t_anticip))
        hora_lim  = dt_lim.strftime("%H:%M")
        st.info(f"⏰ Debes estar en **{t_ol or 'el punto de salida'}** a las **{hora_lim}**")

        if st.button("💾 Guardar transporte", type="primary", use_container_width=True):
            id_trn = gen_id("TRN", t_fecha, t_num or t_prov)
            titulo = f"{t_tipo} {t_prov} {t_num}".strip()
            rubro_g = ("✈️ Vuelos" if "Vuelo" in t_tipo
                       else "🚆 Trenes" if "Tren" in t_tipo
                       else "🚗 Transporte local")

            # 1 → transportes
            ok1 = save_row("transportes", [
                id_trn,
                str(t_fecha), str(t_hora_sal)[:5], str(t_hora_llg)[:5],
                t_tipo, t_prov, t_num, t_conf,
                t_oc, t_ol, t_od,
                t_dc, t_dl, t_dd,
                hora_lim, t_instrida, t_instrllg,
                t_doc, t_monto, t_moneda, t_mxn, t_pagador, t_notas
            ])
            # 2 → gastos (FK al transporte)
            id_gst = gen_id("GST", t_fecha, t_num or t_prov)
            ok2 = save_row("gastos", [
                id_gst, "", id_trn, "",
                str(t_fecha), rubro_g, titulo,
                1, t_monto, 0, t_monto, t_monto,
                t_moneda, t_mxn, t_pagador, t_notas
            ])
            # 3 → itinerario (FK al transporte)
            ok3 = save_row("itinerario", [
                gen_id("EVT", t_fecha, t_num or t_prov),
                str(t_fecha), str(t_hora_sal)[:5], t_tipo, titulo,
                f"Sale: {t_ol} | Llega: {t_dl} | Límite: {hora_lim}",
                t_oc, "", id_trn, t_conf
            ])

            if ok1 and ok2 and ok3:
                st.success(
                    f"✅ Guardado · ID: `{id_trn}`\n\n"
                    f"→ transportes · gastos · itinerario"
                )
                st.caption(f"Costo: {fmt_orig(t_monto, t_moneda)} = {fmt_mxn(t_mxn)}")

    # ── ACTIVIDAD / GASTO GENERAL ─────────────────────────────────
    else:
        st.subheader("🎭 Actividad / Gasto general")
        c1, c2 = st.columns(2)
        with c1:
            a_fecha   = st.date_input("Fecha", value=date.today())
            a_hora    = st.time_input("Hora")
            a_ciudad  = st.selectbox("Ciudad", CIUDADES, key="a_ciudad")
            a_rubro   = st.selectbox("Rubro",
                                      [r for r in RUBROS if "Hospedaje" not in r
                                       and "Vuelos" not in r and "Trenes" not in r])
        with c2:
            a_titulo  = st.text_input("Nombre / descripción")
            a_detalle = st.text_area("Detalles", height=80)
            a_pagador = st.selectbox("Pagado por", PAGADORES, key="a_pag")

        c3, c4 = st.columns(2)
        with c3:
            a_moneda = st.selectbox("Moneda", MONEDAS, key="a_moneda")
            a_monto  = st.number_input("Monto", min_value=0.0, step=1.0, format="%.2f")
        with c4:
            a_mxn = a_mxn_val = a_mxn(a_monto, a_moneda)
            st.metric("Equivalente MXN", fmt_mxn(a_mxn_val))

        a_al_itin = st.checkbox("Agregar también al itinerario", value=True)
        a_notas   = st.text_input("Notas")

        if st.button("💾 Guardar", type="primary", use_container_width=True):
            if not a_titulo:
                st.warning("La descripción es obligatoria.")
                return
            id_gst = gen_id("GST", a_fecha, a_titulo)
            id_evt = gen_id("EVT", a_fecha, a_titulo)

            # 1 → gastos (sin FK de hospedaje/transporte, pero con FK de evento)
            ok1 = save_row("gastos", [
                id_gst, "", "", id_evt,
                str(a_fecha), a_rubro, a_titulo,
                1, a_monto, 0, a_monto, a_monto,
                a_moneda, a_mxn_val, a_pagador, a_notas
            ])
            ok2 = True
            if a_al_itin:
                ok2 = save_row("itinerario", [
                    id_evt,
                    str(a_fecha), str(a_hora)[:5], a_rubro,
                    a_titulo, a_detalle, a_ciudad,
                    "", "", ""
                ])

            if ok1 and ok2:
                st.success(f"✅ Guardado · {a_titulo} · {fmt_mxn(a_mxn_val)}")

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
        st.markdown(
            f"### {label} &nbsp;<span style='font-size:0.8rem;color:#888'>📍 {ciudad_d}</span>",
            unsafe_allow_html=True
        )
        for _, ev in eventos.iterrows():
            hora  = str(ev.get("hora", ""))[:5]
            tipo  = ev.get("tipo", "ℹ️")
            tit   = ev.get("titulo", "")
            desc  = ev.get("descripcion", "")
            conf  = ev.get("confirmacion", "")
            id_ev = ev.get("id_evento", "")
            with st.container(border=True):
                ca, cb = st.columns([1, 7])
                with ca:
                    st.markdown(f"**{hora}**")
                with cb:
                    st.markdown(f"{tipo} &nbsp;**{tit}**")
                    if desc:
                        st.caption(desc)
                    if conf:
                        st.caption(f"🔖 `{conf}`")
                    if id_ev:
                        st.caption(f"ID: `{id_ev}`")
        st.divider()

# ═══════════════════════════════════════════════════════════════
#  MÓDULO: TRANSPORTES
# ═══════════════════════════════════════════════════════════════

def modulo_transportes():
    st.header("🚌 Transportes")
    df = get_df("transportes")
    if df.empty:
        st.info("Aún no hay transportes. Usa '➕ Nuevo registro → Transporte' para agregar.")
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
                st.markdown(
                    f"**Origen:** {t.get('origen_ciudad','')} — {t.get('origen_lugar','')}"
                )
                st.markdown(
                    f"**Destino:** {t.get('destino_ciudad','')} — {t.get('destino_lugar','')}"
                )
                st.caption(f"ID: `{t.get('id_transporte','')}`")
            with c2:
                st.markdown(f"⏰ **Estar ahí a las {t.get('hora_limite','')}**")
                if t.get("instrucciones_ida"):
                    st.caption(f"📌 {t.get('instrucciones_ida','')}")
                if t.get("instrucciones_llegada"):
                    st.caption(f"🏁 {t.get('instrucciones_llegada','')}")
                orig_dir = t.get("origen_direccion", "")
                if orig_dir:
                    url = f"https://maps.google.com/?q={orig_dir.replace(' ','+')}"
                    st.link_button("🗺️ Maps origen", url)
            with c3:
                st.metric("Costo", fmt_mxn(t.get("monto_mxn", 0)))
                st.caption(fmt_orig(t.get("monto", ""), t.get("moneda", "")))
                st.caption(f"Pagó: {t.get('pagado_por','')}")
                conf = t.get("confirmacion", "")
                if conf:
                    st.code(conf, language=None)
                doc = t.get("link_documento", "")
                if doc:
                    st.link_button("📄 Ver doc.", doc)

# ═══════════════════════════════════════════════════════════════
#  MÓDULO: ALOJAMIENTO
# ═══════════════════════════════════════════════════════════════

def modulo_alojamiento():
    st.header("🏨 Alojamiento")
    df     = get_df("alojamiento")
    df_gst = get_df("gastos")

    if df.empty:
        st.info("Aún no hay hoteles. Usa '➕ Nuevo registro → Hospedaje' para agregar.")
        return

    for _, h in df.iterrows():
        id_hsp = h.get("id_hospedaje", "")
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"### 🏨 {h.get('hotel','')}")
                st.markdown(f"📍 **{h.get('ciudad','')}** &nbsp; {h.get('direccion','')}")
                st.markdown(f"📞 `{h.get('telefono','')}`")
                if h.get("confirmacion"):
                    st.markdown(f"🔖 Confirmación: `{h.get('confirmacion','')}`")
                st.caption(f"ID: `{id_hsp}`")
                if h.get("maps_url"):
                    st.link_button("🗺️ Ver en Maps", h.get("maps_url", ""))
            with c2:
                st.markdown(f"**Check-in**\n\n{h.get('checkin','')}")
                st.markdown(f"**Check-out**\n\n{h.get('checkout','')}")
                try:
                    cin    = pd.to_datetime(h.get("checkin"))
                    cout   = pd.to_datetime(h.get("checkout"))
                    noches = (cout - cin).days
                    st.caption(f"{noches} noche(s)")
                except Exception:
                    pass
                # Cruzar con gastos por id_hospedaje
                if not df_gst.empty and "id_hospedaje" in df_gst.columns and id_hsp:
                    gasto_hsp = df_gst[df_gst["id_hospedaje"] == id_hsp]
                    if not gasto_hsp.empty:
                        total_mxn = pd.to_numeric(
                            gasto_hsp["monto_mxn"], errors="coerce"
                        ).sum()
                        st.metric("Costo total", fmt_mxn(total_mxn))

# ═══════════════════════════════════════════════════════════════
#  MÓDULO: PRESUPUESTO
# ═══════════════════════════════════════════════════════════════

def modulo_presupuesto():
    st.header("💰 Presupuesto y Gastos")

    with st.expander("⚙️ Tipo de cambio"):
        st.caption(f"EUR → MXN: **{TC_EUR_MXN}** &nbsp;|&nbsp; USD → MXN: **{TC_USD_MXN}**")
        st.caption("Edita `TC_EUR_MXN` y `TC_USD_MXN` en app.py para actualizar.")

    df = get_df("gastos")
    if df.empty:
        st.info("Aún no hay gastos registrados.")
        return

    for col in ["monto_total", "monto_mxn", "costo_por_unidad", "impuestos", "unidades"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df["semana"] = df["fecha"].dt.isocalendar().week.astype(str)

    total = df["monto_mxn"].sum()
    resto = PRESUPUESTO_MXN - total
    pct   = min(total / PRESUPUESTO_MXN, 1.0)
    color = "#22c55e" if pct < 0.70 else ("#f59e0b" if pct < 0.90 else "#ef4444")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Gastado",     fmt_mxn(total))
    k2.metric("Presupuesto", fmt_mxn(PRESUPUESTO_MXN))
    k3.metric("Disponible",  fmt_mxn(resto))
    k4.metric("% Utilizado", f"{pct*100:.1f}%")

    st.markdown(f"""
        <div style='background:var(--secondary-background-color);border-radius:8px;
                    height:14px;margin:4px 0 20px'>
            <div style='background:{color};width:{pct*100:.1f}%;height:14px;border-radius:8px'></div>
        </div>
    """, unsafe_allow_html=True)

    # Filtros
    st.subheader("Análisis")
    cf1, cf2, cf3 = st.columns(3)
    f_agrup   = cf1.selectbox("Agrupar por", ["Rubro", "Semana", "Pagador"])
    f_pagador = cf2.selectbox("Pagador", ["Todos"] + PAGADORES)
    f_rubro   = cf3.selectbox("Rubro",   ["Todos"] + RUBROS)

    df_f = df.copy()
    if f_pagador != "Todos" and "pagado_por" in df_f.columns:
        df_f = df_f[df_f["pagado_por"] == f_pagador]
    if f_rubro != "Todos" and "rubro" in df_f.columns:
        df_f = df_f[df_f["rubro"] == f_rubro]

    col_agrup = {"Rubro": "rubro", "Semana": "semana", "Pagador": "pagado_por"}[f_agrup]
    if col_agrup in df_f.columns:
        agg = df_f.groupby(col_agrup)["monto_mxn"].sum().reset_index()
        agg.columns = [f_agrup, "MXN"]
        st.bar_chart(agg.set_index(f_agrup))

    # Tabla detalle
    st.subheader("Detalle de gastos")
    cols_map = {
        "id_gasto": "ID", "fecha": "Fecha", "rubro": "Rubro",
        "descripcion": "Descripción", "unidades": "Nts/Uds",
        "costo_por_unidad": "P. unit.", "monto_total": "Total orig.",
        "moneda": "Mon.", "monto_mxn": "Total MXN", "pagado_por": "Pagador",
        "id_hospedaje": "Ref. Hotel", "id_transporte": "Ref. Transp."
    }
    cols_ok = [c for c in cols_map if c in df_f.columns]
    df_show = df_f[cols_ok].rename(columns=cols_map).sort_values("Fecha", ascending=False)
    st.dataframe(df_show, use_container_width=True, hide_index=True)

    # Balance por persona
    st.subheader("Balance por persona")
    if "pagado_por" in df.columns:
        for p in PAGADORES:
            tot_p = df[df["pagado_por"] == p]["monto_mxn"].sum()
            pct_p = tot_p / total * 100 if total > 0 else 0
            st.markdown(f"**{p}**: {fmt_mxn(tot_p)} ({pct_p:.1f}%)")

    # Vista: gastos cruzados por hospedaje
    st.subheader("Detalle por hospedaje")
    df_hsp = get_df("alojamiento")
    if not df_hsp.empty and "id_hospedaje" in df.columns:
        for _, h in df_hsp.iterrows():
            id_h  = h.get("id_hospedaje", "")
            gastos_h = df[df["id_hospedaje"] == id_h]
            if not gastos_h.empty:
                total_h = gastos_h["monto_mxn"].sum()
                with st.expander(f"🏨 {h.get('hotel','')} — {fmt_mxn(total_h)}"):
                    st.dataframe(
                        gastos_h[["fecha", "descripcion", "unidades",
                                  "monto_total", "moneda", "monto_mxn"]],
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
            d_tipo  = st.selectbox("Tipo", ["Pasaporte", "Visa", "Seguro de viaje",
                                            "Tarjeta de crédito", "Otro"])
            d_desc  = st.text_input("Descripción (ej: Pasaporte Papá)")
            d_num   = st.text_input("Número / código")
        with c2:
            d_venc  = st.date_input("Vencimiento", value=date(2026, 1, 1))
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

    for tipo in (df["tipo"].unique() if "tipo" in df.columns else []):
        st.subheader(f"📋 {tipo}")
        for _, d in df[df["tipo"] == tipo].iterrows():
            with st.container(border=True):
                ca, cb = st.columns([3, 1])
                with ca:
                    st.markdown(f"**{d.get('descripcion','')}**")
                    if d.get("numero"):
                        st.code(d.get("numero", ""), language=None)
                    if d.get("notas"):
                        st.caption(d.get("notas", ""))
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

        opciones = ["📅 Itinerario", "🚌 Transportes", "🏨 Alojamiento",
                    "💰 Presupuesto", "📄 Documentos"]
        if rol in ["admin", "coeditor"]:
            opciones.insert(0, "➕ Nuevo registro")

        pagina = st.radio("Navegación", opciones, label_visibility="collapsed")
        st.divider()
        if st.button("🚪 Cerrar sesión", use_container_width=True):
            logout()

    if   pagina == "➕ Nuevo registro": formulario_nuevo_registro(rol)
    elif pagina == "📅 Itinerario":     modulo_itinerario()
    elif pagina == "🚌 Transportes":    modulo_transportes()
    elif pagina == "🏨 Alojamiento":    modulo_alojamiento()
    elif pagina == "💰 Presupuesto":    modulo_presupuesto()
    elif pagina == "📄 Documentos":     modulo_documentos(rol)

if __name__ == "__main__":
    main()
