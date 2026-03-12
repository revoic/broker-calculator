import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import calendar

st.set_page_config(page_title="Broker Profit Analyse", layout="wide")
st.title("📊 Broker Revenue & Profit Analyse")
st.markdown("---")

# ─────────────────────────────────────────
# PASSWORTSCHUTZ
# ─────────────────────────────────────────
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    pwd = st.text_input("🔒 Passwort", type="password")
    if pwd == st.secrets.get("PASSWORD", "revoic2026"):
        st.session_state.authenticated = True
        st.rerun()
    elif pwd:
        st.error("Falsches Passwort")
    st.stop()

# ─────────────────────────────────────────
# HILFSFUNKTIONEN
# ─────────────────────────────────────────
def parse_provision_excel(uploaded_file):
    """Liest Provision (Zeile 31) und Monate aus dem Abrechnungs-Excel."""
    df = pd.read_excel(uploaded_file, header=None)
    # Header-Zeile: Spalte 0 = Name, Spalten 1..n-1 = Monate, letzte = Comments
    header_row = df.iloc[0]
    months = []
    provisions = []
    for col_idx in range(1, len(header_row) - 1):
        raw = header_row[col_idx]
        try:
            m = pd.to_datetime(str(raw)).strftime("%Y-%m")
        except:
            continue
        prov_val = df.iloc[30, col_idx]  # Zeile 31 = index 30
        try:
            prov_val = abs(float(prov_val))
        except:
            prov_val = 0.0
        months.append(m)
        provisions.append(prov_val)
    return pd.DataFrame({"Monat": months, "Provision": provisions})


def parse_clockify_csv(uploaded_file):
    """Liest den Clockify Detailbericht CSV."""
    df = pd.read_csv(uploaded_file)
    df["Startdatum"] = pd.to_datetime(df["Startdatum"], format="%d.%m.%Y", errors="coerce")
    df["Monat"] = df["Startdatum"].dt.to_period("M").astype(str)
    df["KW"] = df["Startdatum"].dt.isocalendar().week.astype(str).str.zfill(2)
    df["Jahr"] = df["Startdatum"].dt.year.astype(str)
    df["KW_Label"] = df["Jahr"] + "-KW" + df["KW"]
    df["Stunden"] = pd.to_numeric(df["Dauer (dezimal)"], errors="coerce").fillna(0)
    return df


def forecast_current_month(ist_provision, monat_str):
    """Hochrechnung auf Basis vergangener Tage im laufenden Monat."""
    heute = datetime.today()
    year, month = int(monat_str[:4]), int(monat_str[5:7])
    tage_gesamt = calendar.monthrange(year, month)[1]
    if heute.year == year and heute.month == month:
        tage_vergangen = heute.day
    else:
        tage_vergangen = tage_gesamt
    if tage_vergangen == 0:
        return ist_provision
    return ist_provision * (tage_gesamt / tage_vergangen)


# ─────────────────────────────────────────
# SIDEBAR – UPLOADS & EINSTELLUNGEN
# ─────────────────────────────────────────
with st.sidebar:
    st.header("📂 Daten Upload")
    excel_file = st.file_uploader("Abrechnungs-Excel (.xlsx)", type=["xlsx"])
    clock_file = st.file_uploader("Clockify Detailbericht (.csv)", type=["csv"])

    st.markdown("---")
    st.header("💶 Stundensätze (€/h)")

    # Default-Stundensätze laut Screenshot
    default_rates = {
        "Maik Busch": 120,
        "Talha Gülbahar": 58,
        "Max Kirchhoff": 80,
        "Maximilian Lang": 75,
        "Maggy Roocks": 75,
        "Verena Behl": 90,
        "Jannick Müller": 36,
        "Olena Vasylieva": 80,
        "Joelina Dietrich": 90,
        "Mehmet Akkan": 80,
        "Stephan Bruns": 120,
        "Speranza Coda": 75,
        "Alexander Broßmann": 80,
        "Canel Cekin": 75,
        "Daniela Heinrich": 90,
        "Arta Arjana Osmani": 75,
        "Casie Garnatz": 36,
        "yemets.oksana": 14,
    }
    mitarbeiter_liste = list(default_rates.keys())

    # Session State initialisieren
    for ma, rate in default_rates.items():
        key = f"rate_{ma}"
        if key not in st.session_state:
            st.session_state[key] = rate

    # Reset-Button
    if st.button("🔄 Auf Standardwerte zurücksetzen"):
        for ma, rate in default_rates.items():
            st.session_state[f"rate_{ma}"] = rate
        st.rerun()

    stundensaetze = {}
    with st.expander("Stundensätze anpassen", expanded=False):
        for ma in mitarbeiter_liste:
            stundensaetze[ma] = st.number_input(
                ma, min_value=0, max_value=500,
                step=1, key=f"rate_{ma}"
            )
    default_rate = 85

    st.markdown("---")
    st.caption("Laufender Monat wird automatisch als unvollständig erkannt und hochgerechnet.")

# ─────────────────────────────────────────
# HAUPTBEREICH
# ─────────────────────────────────────────
if not excel_file or not clock_file:
    st.info("👈 Bitte links das Abrechnungs-Excel und den Clockify Detailbericht hochladen.")
    st.stop()

# Daten laden
df_prov = parse_provision_excel(excel_file)
df_clock = parse_clockify_csv(clock_file)

# Monate abgleichen
alle_monate = sorted(set(df_prov["Monat"].tolist() + df_clock["Monat"].unique().tolist()))

# Stunden + Kosten pro Monat & Mitarbeiter berechnen
df_clock["Stundensatz"] = df_clock["Benutzer"].map(stundensaetze).fillna(default_rate)
df_clock["Kosten"] = df_clock["Stunden"] * df_clock["Stundensatz"]

# Monats-Aggregation
month_hours = df_clock.groupby("Monat").agg(
    Stunden_gesamt=("Stunden", "sum"),
    Personalkosten=("Kosten", "sum")
).reset_index()

# Merge mit Provision
df_main = df_prov.merge(month_hours, on="Monat", how="outer").fillna(0)
df_main = df_main.sort_values("Monat")

# Laufenden Monat erkennen & Forecast
heute_str = datetime.today().strftime("%Y-%m")
df_main["Ist_Monat"] = df_main["Monat"] == heute_str
df_main["Provision_Forecast"] = df_main.apply(
    lambda r: forecast_current_month(r["Provision"], r["Monat"]) if r["Ist_Monat"] else r["Provision"],
    axis=1
)
df_main["Profit"] = df_main["Provision"] - df_main["Personalkosten"]
df_main["Profit_Forecast"] = df_main["Provision_Forecast"] - df_main["Personalkosten"]
df_main["Marge"] = df_main.apply(
    lambda r: (r["Profit"] / r["Provision"] * 100) if r["Provision"] > 0 else 0, axis=1
)

# ─────────────────────────────────────────
# TABS
# ─────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📅 Monatsübersicht",
    "👤 Mitarbeiter",
    "📂 Projektkategorien",
    "📆 Wochenansicht"
])

# ─────────── TAB 1: MONATSÜBERSICHT ───────────
with tab1:
    st.subheader("📅 Monatsübersicht: Provision vs. Personalkosten vs. Profit")

    # KPI-Zeile (Gesamt)
    total_prov = df_main["Provision"].sum()
    total_pk = df_main["Personalkosten"].sum()
    total_profit = df_main["Profit"].sum()
    total_marge = (total_profit / total_prov * 100) if total_prov > 0 else 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("💰 Provision gesamt", f"{total_prov:,.0f} €".replace(',', '.'))
    k2.metric("👥 Personalkosten gesamt", f"{total_pk:,.0f} €".replace(',', '.'))
    k3.metric("💸 Profit gesamt", f"{total_profit:,.0f} €".replace(',', '.'))
    k4.metric("📊 Ø Marge", f"{total_marge:.1f} %")

    st.markdown("---")

    # Balkendiagramm Provision vs Personalkosten
    fig1 = go.Figure()
    fig1.add_trace(go.Bar(name="Provision (Ist)", x=df_main["Monat"], y=df_main["Provision"], marker_color="#3b82f6"))
    fig1.add_trace(go.Bar(name="Provision (Forecast)", x=df_main[df_main["Ist_Monat"]]["Monat"],
                          y=df_main[df_main["Ist_Monat"]]["Provision_Forecast"],
                          marker_color="#93c5fd", opacity=0.7))
    fig1.add_trace(go.Bar(name="Personalkosten", x=df_main["Monat"], y=df_main["Personalkosten"], marker_color="#ef4444"))
    fig1.update_layout(barmode="group", height=350, title="Provision vs. Personalkosten pro Monat",
                       xaxis_title="", yaxis_title="€")
    st.plotly_chart(fig1, use_container_width=True)

    # Profit-Linie
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=df_main["Monat"], y=df_main["Profit"],
                              mode="lines+markers", name="Profit", line=dict(color="#10b981", width=2)))
    fig2.add_trace(go.Scatter(
        x=df_main[df_main["Ist_Monat"]]["Monat"],
        y=df_main[df_main["Ist_Monat"]]["Profit_Forecast"],
        mode="markers", name="Profit Forecast",
        marker=dict(color="#6ee7b7", size=12, symbol="star")
    ))
    fig2.add_hline(y=0, line_dash="dash", line_color="gray")
    fig2.update_layout(height=300, title="Profit-Verlauf", xaxis_title="", yaxis_title="€")
    st.plotly_chart(fig2, use_container_width=True)

    # Detailtabelle
    st.subheader("🗒️ Detailtabelle")
    df_display = df_main[["Monat", "Provision", "Provision_Forecast", "Personalkosten", "Stunden_gesamt", "Profit", "Marge", "Ist_Monat"]].copy()
    df_display.columns = ["Monat", "Provision (Ist) €", "Provision (Forecast) €", "Personalkosten €", "Stunden", "Profit €", "Marge %", "Laufend"]
    df_display["Laufend"] = df_display["Laufend"].map({True: "⚠️ laufend", False: ""})
    for col in ["Provision (Ist) €", "Provision (Forecast) €", "Personalkosten €", "Profit €"]:
        df_display[col] = df_display[col].map(lambda x: f"{x:,.0f} €".replace(',', '.'))
    df_display["Marge %"] = df_display["Marge %"].map(lambda x: f"{x:.1f} %")
    df_display["Stunden"] = df_display["Stunden"].map(lambda x: f"{x:.1f} h")
    st.dataframe(df_display, use_container_width=True, hide_index=True)

# ─────────── TAB 2: MITARBEITER ───────────
with tab2:
    st.subheader("👤 Auswertung nach Mitarbeiter")

    monat_filter = st.selectbox("Monat auswählen", ["Alle"] + sorted(df_clock["Monat"].unique().tolist(), reverse=True))

    df_ma = df_clock.copy()
    if monat_filter != "Alle":
        df_ma = df_ma[df_ma["Monat"] == monat_filter]

    ma_agg = df_ma.groupby("Benutzer").agg(
        Stunden=("Stunden", "sum"),
        Kosten=("Kosten", "sum")
    ).reset_index().sort_values("Stunden", ascending=False)

    fig_ma = px.bar(ma_agg, x="Benutzer", y="Stunden", text="Stunden",
                    title="Stunden pro Mitarbeiter",
                    color="Kosten", color_continuous_scale="Blues")
    fig_ma.update_traces(texttemplate="%{text:.1f}h", textposition="outside")
    fig_ma.update_layout(height=400, xaxis_title="", coloraxis_colorbar_title="Kosten €")
    st.plotly_chart(fig_ma, use_container_width=True)

    # Tabelle
    ma_agg["Stunden"] = ma_agg["Stunden"].map(lambda x: f"{x:.1f} h")
    ma_agg["Kosten"] = ma_agg["Kosten"].map(lambda x: f"{x:,.0f} €".replace(',', '.'))
    ma_agg.columns = ["Mitarbeiter", "Stunden", "Personalkosten €"]
    st.dataframe(ma_agg, use_container_width=True, hide_index=True)

# ─────────── TAB 3: PROJEKTKATEGORIEN ───────────
with tab3:
    st.subheader("📂 Auswertung nach Projektkategorie")

    monat_filter2 = st.selectbox("Monat", ["Alle"] + sorted(df_clock["Monat"].unique().tolist(), reverse=True), key="proj_monat")

    df_proj = df_clock.copy()
    if monat_filter2 != "Alle":
        df_proj = df_proj[df_proj["Monat"] == monat_filter2]

    proj_agg = df_proj.groupby("Projekt").agg(
        Stunden=("Stunden", "sum"),
        Kosten=("Kosten", "sum")
    ).reset_index().sort_values("Stunden", ascending=False)

    c1, c2 = st.columns(2)
    with c1:
        fig_pie = px.pie(proj_agg, names="Projekt", values="Stunden",
                         title="Stundenanteil nach Kategorie", hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)
    with c2:
        fig_pk = px.bar(proj_agg, x="Projekt", y="Kosten", text="Kosten",
                        title="Kosten nach Kategorie (€)")
        fig_pk.update_traces(texttemplate="%{text:,.0f}€", textposition="outside")
        fig_pk.update_layout(height=350, xaxis_title="", yaxis_title="€")
        st.plotly_chart(fig_pk, use_container_width=True)

    # Drilldown: Projekt → Mitarbeiter
    st.markdown("#### Detailansicht: Kategorie × Mitarbeiter")
    proj_ma = df_proj.groupby(["Projekt", "Benutzer"]).agg(
        Stunden=("Stunden", "sum"),
        Kosten=("Kosten", "sum")
    ).reset_index()
    proj_ma["Stunden"] = proj_ma["Stunden"].map(lambda x: f"{x:.1f} h")
    proj_ma["Kosten"] = proj_ma["Kosten"].map(lambda x: f"{x:,.0f} €".replace(',', '.'))
    proj_ma.columns = ["Projekt", "Mitarbeiter", "Stunden", "Kosten €"]
    st.dataframe(proj_ma, use_container_width=True, hide_index=True)

# ─────────── TAB 4: WOCHENANSICHT ───────────
with tab4:
    st.subheader("📆 Wochenansicht – Stunden & Kosten")

    monat_filter3 = st.selectbox("Monat", sorted(df_clock["Monat"].unique().tolist(), reverse=True), key="week_monat")
    df_week = df_clock[df_clock["Monat"] == monat_filter3]

    kw_agg = df_week.groupby(["KW_Label", "Benutzer"]).agg(
        Stunden=("Stunden", "sum"),
        Kosten=("Kosten", "sum")
    ).reset_index()

    fig_week = px.bar(kw_agg, x="KW_Label", y="Stunden", color="Benutzer",
                      text="Stunden", barmode="stack",
                      title=f"Stunden pro KW – {monat_filter3}")
    fig_week.update_traces(texttemplate="%{text:.1f}", textposition="inside")
    fig_week.update_layout(height=400, xaxis_title="Kalenderwoche", yaxis_title="Stunden")
    st.plotly_chart(fig_week, use_container_width=True)

    # Kosten pro KW
    kw_kosten = df_week.groupby("KW_Label").agg(Kosten=("Kosten", "sum")).reset_index()
    fig_kw_k = px.line(kw_kosten, x="KW_Label", y="Kosten", markers=True,
                       title="Personalkosten pro KW (€)")
    fig_kw_k.update_layout(height=280, xaxis_title="", yaxis_title="€")
    st.plotly_chart(fig_kw_k, use_container_width=True)
