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

# ─────────────────────────────────────────
# SONDEREINNAHMEN (Netto, nach 19% MwSt)
# ─────────────────────────────────────────
sondereinnahmen = {
    "2024-10": 42290.00,   # Brutto 50.325,10 €
    "2025-04": 29700.00,   # Brutto 35.343,00 €
    "2026-01": 38790.00,   # Brutto 46.160,10 €
}
df_sonder = pd.DataFrame([
    {"Monat": m, "Sondereinnahmen": v} for m, v in sondereinnahmen.items()
])

# Monats-Aggregation
month_hours = df_clock.groupby("Monat").agg(
    Stunden_gesamt=("Stunden", "sum"),
    Personalkosten=("Kosten", "sum")
).reset_index()

# Merge mit Provision + Sondereinnahmen
# WICHTIG: outer merge auf allen drei Quellen, damit kein Monat verloren geht
df_main = df_prov.merge(month_hours, on="Monat", how="outer")
df_main = df_main.merge(df_sonder, on="Monat", how="outer")
df_main = df_main.fillna(0)
df_main = df_main.sort_values("Monat")

# Laufenden Monat erkennen & Forecast
heute_str = datetime.today().strftime("%Y-%m")
df_main["Ist_Monat"] = df_main["Monat"] == heute_str
df_main["Provision_Forecast"] = df_main.apply(
    lambda r: forecast_current_month(r["Provision"], r["Monat"]) if r["Ist_Monat"] else r["Provision"],
    axis=1
)
# Gesamterlös = Provision + Sondereinnahmen
df_main["Erloes_gesamt"] = df_main["Provision"] + df_main["Sondereinnahmen"]
df_main["Erloes_gesamt_Forecast"] = df_main["Provision_Forecast"] + df_main["Sondereinnahmen"]

df_main["Profit"] = df_main["Erloes_gesamt"] - df_main["Personalkosten"]
df_main["Profit_Forecast"] = df_main["Erloes_gesamt_Forecast"] - df_main["Personalkosten"]
df_main["Marge"] = df_main.apply(
    lambda r: (r["Profit"] / r["Erloes_gesamt"] * 100) if r["Erloes_gesamt"] > 0 else 0, axis=1
)

# ─── BREAK-EVEN & ÜBERSTUNDEN ───
# Ø Stundensatz (gewichtet über alle Mitarbeiter & Stunden)
total_kosten = df_clock["Kosten"].sum()
total_stunden = df_clock["Stunden"].sum()
avg_stundensatz = total_kosten / total_stunden if total_stunden > 0 else 85

df_main["Break_Even_Stunden"] = df_main["Erloes_gesamt"] / avg_stundensatz
df_main["Ueberstunden"] = df_main["Stunden_gesamt"] - df_main["Break_Even_Stunden"]
df_main["Ueberstunden_EUR"] = df_main["Ueberstunden"] * avg_stundensatz

# ─────────────────────────────────────────
# TABS
# ─────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📅 Monatsübersicht",
    "👤 Mitarbeiter",
    "📂 Projektkategorien",
    "📆 Wochenansicht",
    "🏆 Projektübersicht",
    "🔮 Forecast"
])

# ─────────── TAB 1: MONATSÜBERSICHT ───────────
with tab1:
    st.subheader("📅 Monatsübersicht: Provision vs. Personalkosten vs. Profit")

    # KPI-Zeile (Gesamt)
    total_prov = df_main["Provision"].sum()
    total_pk = df_main["Personalkosten"].sum()
    total_profit = df_main["Profit"].sum()
    total_marge = (total_profit / total_prov * 100) if total_prov > 0 else 0

    total_sonder = df_main["Sondereinnahmen"].sum()
    total_erloes = df_main["Erloes_gesamt"].sum()
    avg_ueberstunden = df_main["Ueberstunden"].mean()
    total_ueberstunden_eur = df_main["Ueberstunden_EUR"].sum()

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("💰 Erlös gesamt", f"{total_erloes:,.0f} €".replace(',', '.'),
              delta=f"davon {total_sonder:,.0f} € Sonder".replace(',', '.'))
    k2.metric("👥 Personalkosten gesamt", f"{total_pk:,.0f} €".replace(',', '.'))
    k3.metric("💸 Profit gesamt", f"{total_profit:,.0f} €".replace(',', '.'))
    k4.metric("📊 Ø Marge", f"{total_marge:.1f} %")

    st.markdown("---")

    # Überstunden-Box
    ue_col1, ue_col2, ue_col3 = st.columns(3)
    ue_col1.metric("⏱️ Ø Überstunden pro Monat",
                   f"{avg_ueberstunden:+.1f} h",
                   delta_color="inverse")
    ue_col2.metric("💸 Verlorener Profit (gesamt)",
                   f"{total_ueberstunden_eur:,.0f} €".replace(',', '.'),
                   delta_color="inverse")
    ue_col3.metric("⚖️ Ø Stundensatz (gewichtet)",
                   f"{avg_stundensatz:.2f} €/h")

    st.markdown("---")

    # Balkendiagramm Provision vs Personalkosten
    fig1 = go.Figure()
    fig1.add_trace(go.Bar(name="Provision", x=df_main["Monat"], y=df_main["Provision"], marker_color="#3b82f6"))
    fig1.add_trace(go.Bar(name="Sondereinnahmen", x=df_main["Monat"], y=df_main["Sondereinnahmen"], marker_color="#f59e0b"))
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

    # Überstunden-Chart pro Monat
    fig_ue = go.Figure()
    fig_ue.add_trace(go.Bar(
        x=df_main["Monat"], y=df_main["Ueberstunden"],
        marker_color=df_main["Ueberstunden"].apply(lambda x: "#ef4444" if x > 0 else "#10b981"),
        name="Über-/Unterstunden"
    ))
    fig_ue.add_hline(y=0, line_dash="dash", line_color="gray")
    fig_ue.update_layout(height=280, title="Über-/Unterstunden pro Monat (+ = zu viel gearbeitet)",
                         xaxis_title="", yaxis_title="Stunden")
    st.plotly_chart(fig_ue, use_container_width=True)

    # Detailtabelle
    st.subheader("🗒️ Detailtabelle")
    df_display = df_main[["Monat", "Provision", "Sondereinnahmen", "Erloes_gesamt", "Provision_Forecast", "Personalkosten", "Stunden_gesamt", "Break_Even_Stunden", "Ueberstunden", "Profit", "Marge", "Ist_Monat"]].copy()
    # Formatierung VOR dem Umbenennen
    df_display["Laufend"] = df_display["Ist_Monat"].map({True: "⚠️ laufend", False: ""})
    for col in ["Provision", "Sondereinnahmen", "Erloes_gesamt", "Provision_Forecast", "Personalkosten", "Profit"]:
        df_display[col] = df_display[col].map(lambda x: f"{x:,.0f} €".replace(',', '.'))
    df_display["Marge"] = df_display["Marge"].map(lambda x: f"{x:.1f} %")
    df_display["Stunden_gesamt"] = df_display["Stunden_gesamt"].map(lambda x: f"{x:.1f} h")
    df_display["Break_Even_Stunden"] = df_display["Break_Even_Stunden"].map(lambda x: f"{x:.1f} h")
    df_display["Ueberstunden"] = df_display["Ueberstunden"].map(lambda x: f"{x:+.1f} h")
    # Jetzt umbenennen
    df_display = df_display.drop(columns=["Ist_Monat"])
    df_display.columns = ["Monat", "Provision €", "Sonder €", "Erlös gesamt €", "Forecast €", "Personalkosten €", "Stunden", "Break-Even h", "Über-h", "Profit €", "Marge %", "Laufend"]
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

# ─────────── TAB 5: PROJEKTÜBERSICHT ───────────
with tab5:
    st.subheader("🏆 Gesamtprojekt & Jahresübersicht")

    # Jahr-Spalte ergänzen
    df_main["Jahr"] = df_main["Monat"].str[:4]

    # ─── GESAMT-KPIs ───
    st.markdown("### 📊 Gesamtes Projekt (kumuliert)")

    # Gewinn/Verlust-Anzeige Gesamtprojekt
    gesamt_profit_val = df_main['Profit'].sum()
    gv_label = f"✅ Überschuss: {gesamt_profit_val:,.0f} €".replace(',','.') if gesamt_profit_val >= 0 else f"🔴 Verlust: {gesamt_profit_val:,.0f} €".replace(',','.')
    gv_color = "#10b981" if gesamt_profit_val >= 0 else "#ef4444"
    st.markdown(f"<div style='background:{gv_color}22; border-left: 4px solid {gv_color}; padding: 12px 20px; border-radius:6px; font-size:20px; font-weight:bold; color:{gv_color}'>{gv_label}</div>", unsafe_allow_html=True)
    st.markdown("")
    g1, g2, g3, g4, g5 = st.columns(5)
    g1.metric("💰 Provision gesamt", f"{df_main['Provision'].sum():,.0f} €".replace(',','.'))
    g2.metric("⭐ Sondereinnahmen", f"{df_main['Sondereinnahmen'].sum():,.0f} €".replace(',','.'))
    g3.metric("💸 Erlös gesamt", f"{df_main['Erloes_gesamt'].sum():,.0f} €".replace(',','.'))
    g4.metric("👥 Personalkosten", f"{df_main['Personalkosten'].sum():,.0f} €".replace(',','.'))
    g5.metric("💹 Profit gesamt", f"{df_main['Profit'].sum():,.0f} €".replace(',','.'))

    # Gesamtmarge
    gesamt_erloes = df_main['Erloes_gesamt'].sum()
    gesamt_profit = df_main['Profit'].sum()
    gesamt_marge = (gesamt_profit / gesamt_erloes * 100) if gesamt_erloes > 0 else 0
    gesamt_stunden = df_main['Stunden_gesamt'].sum()
    eff_stundenlohn = gesamt_erloes / gesamt_stunden if gesamt_stunden > 0 else 0

    gx1, gx2, gx3 = st.columns(3)
    gx1.metric("📊 Gesamtmarge", f"{gesamt_marge:.1f} %")
    gx2.metric("⏱️ Gesamtstunden", f"{gesamt_stunden:,.1f} h".replace(',','.'))
    gx3.metric("⚡ Effektiver Stundenerlös", f"{eff_stundenlohn:.2f} €/h")

    st.markdown("---")

    # ─── JAHRESAGGREGATION ───
    st.markdown("### 📅 Auswertung nach Jahr")

    # ERST aggregieren, DANN Karten anzeigen
    df_year = df_main.groupby("Jahr").agg(
        Provision=("Provision", "sum"),
        Sondereinnahmen=("Sondereinnahmen", "sum"),
        Erloes_gesamt=("Erloes_gesamt", "sum"),
        Personalkosten=("Personalkosten", "sum"),
        Profit=("Profit", "sum"),
        Stunden=("Stunden_gesamt", "sum"),
        Ueberstunden=("Ueberstunden", "sum"),
    ).reset_index()
    df_year["Marge"] = (df_year["Profit"] / df_year["Erloes_gesamt"] * 100).round(1)
    df_year["Eff_Stundenlohn"] = (df_year["Erloes_gesamt"] / df_year["Stunden"]).round(2)

    # Gewinn/Verlust pro Jahr als farbige Karten
    jahre = sorted(df_year["Jahr"].unique())
    cols_jahre = st.columns(len(jahre))
    for i, jahr in enumerate(jahre):
        row = df_year[df_year["Jahr"] == jahr].iloc[0]
        p = row["Profit"]
        farbe = "#10b981" if p >= 0 else "#ef4444"
        label = "Überschuss" if p >= 0 else "Verlust"
        cols_jahre[i].markdown(
            f"<div style='background:{farbe}22; border-left:4px solid {farbe}; padding:10px 14px; border-radius:6px;'>"
            f"<div style='font-size:13px; color:#666'>{jahr}</div>"
            f"<div style='font-size:18px; font-weight:bold; color:{farbe}'>{label}</div>"
            f"<div style='font-size:22px; font-weight:bold; color:{farbe}'>{p:,.0f} €</div>"
            f"<div style='font-size:12px; color:#888'>Marge: {row['Marge']:.1f} %</div>"
            f"</div>", unsafe_allow_html=True
        )
    st.markdown("")

    # Jahres-Balkendiagramm
    fig_yr = go.Figure()
    fig_yr.add_trace(go.Bar(name="Provision", x=df_year["Jahr"], y=df_year["Provision"], marker_color="#3b82f6"))
    fig_yr.add_trace(go.Bar(name="Sondereinnahmen", x=df_year["Jahr"], y=df_year["Sondereinnahmen"], marker_color="#f59e0b"))
    fig_yr.add_trace(go.Bar(name="Personalkosten", x=df_year["Jahr"], y=df_year["Personalkosten"], marker_color="#ef4444"))
    fig_yr.add_trace(go.Scatter(name="Profit", x=df_year["Jahr"], y=df_year["Profit"],
                                mode="lines+markers+text", line=dict(color="#10b981", width=3),
                                text=df_year["Profit"].map(lambda x: f"{x:,.0f} €".replace(',','.')),
                                textposition="top center"))
    fig_yr.update_layout(barmode="group", height=400,
                         title="Erlös, Kosten & Profit pro Jahr",
                         xaxis_title="", yaxis_title="€")
    st.plotly_chart(fig_yr, use_container_width=True)

    # Erlösanteil Provision vs Sondereinnahmen pro Jahr (gestapelt %)
    c1, c2 = st.columns(2)
    with c1:
        fig_stack = go.Figure()
        fig_stack.add_trace(go.Bar(name="Provision", x=df_year["Jahr"],
                                   y=df_year["Provision"] / df_year["Erloes_gesamt"] * 100,
                                   marker_color="#3b82f6",
                                   text=(df_year["Provision"] / df_year["Erloes_gesamt"] * 100).map(lambda x: f"{x:.1f}%"),
                                   textposition="inside"))
        fig_stack.add_trace(go.Bar(name="Sondereinnahmen", x=df_year["Jahr"],
                                   y=df_year["Sondereinnahmen"] / df_year["Erloes_gesamt"] * 100,
                                   marker_color="#f59e0b",
                                   text=(df_year["Sondereinnahmen"] / df_year["Erloes_gesamt"] * 100).map(lambda x: f"{x:.1f}%"),
                                   textposition="inside"))
        fig_stack.update_layout(barmode="stack", height=320,
                                title="Erlösanteil: Provision vs. Sonder (%)",
                                yaxis_title="%", xaxis_title="")
        st.plotly_chart(fig_stack, use_container_width=True)

    with c2:
        # Gesamtprojekt Donut
        labels = ["Provision", "Sondereinnahmen"]
        values = [df_main["Provision"].sum(), df_main["Sondereinnahmen"].sum()]
        fig_donut = go.Figure(go.Pie(labels=labels, values=values, hole=0.5,
                                     marker_colors=["#3b82f6", "#f59e0b"]))
        fig_donut.update_layout(height=320, title="Erlösanteil gesamt (Gesamtprojekt)")
        st.plotly_chart(fig_donut, use_container_width=True)

    # Jahrestabelle
    st.markdown("### 🗒️ Jahrestabelle")
    df_year_display = df_year.copy()
    for col in ["Provision", "Sondereinnahmen", "Erloes_gesamt", "Personalkosten", "Profit"]:
        df_year_display[col] = df_year_display[col].map(lambda x: f"{x:,.0f} €".replace(',','.'))
    df_year_display["Stunden"] = df_year_display["Stunden"].map(lambda x: f"{x:.1f} h")
    df_year_display["Ueberstunden"] = df_year_display["Ueberstunden"].map(lambda x: f"{x:+.1f} h")
    df_year_display["Marge"] = df_year_display["Marge"].map(lambda x: f"{x:.1f} %")
    df_year_display["Eff_Stundenlohn"] = df_year_display["Eff_Stundenlohn"].map(lambda x: f"{x:.2f} €/h")
    df_year_display.columns = ["Jahr", "Provision €", "Sonder €", "Erlös gesamt €",
                                "Personalkosten €", "Profit €", "Stunden", "Über-h", "Marge %", "Eff. €/h"]
    st.dataframe(df_year_display, use_container_width=True, hide_index=True)

# ─────────── TAB 6: FORECAST ───────────
with tab6:
    st.subheader("🔮 Forecast: Erlös & Stunden-Budget")

    # ─── EINSTELLUNGEN ───
    fc1, fc2 = st.columns([1, 2])
    with fc1:
        ziel_marge = st.slider("🎯 Ziel-Marge (%)", min_value=5, max_value=60, value=20, step=1)
        wachstum_pct = st.slider("📈 Umsatzwachstum (%)", min_value=10, max_value=100, value=40, step=5)

    # ─── BASIS: Letzte 12 Monate (Saisonmuster) ───
    heute = datetime.today()
    # Alle abgeschlossenen Monate nehmen (nicht laufend)
    df_hist = df_main[~df_main["Ist_Monat"]].copy()
    df_hist["MonatNum"] = pd.to_datetime(df_hist["Monat"]).dt.month

    # Saisonales Muster: Durchschnitt pro Kalendermonat über alle Jahre
    saison = df_hist.groupby("MonatNum").agg(
        Provision_avg=("Provision", "mean"),
        Sonder_avg=("Sondereinnahmen", "mean"),
    ).reset_index()
    saison["Erloes_avg"] = saison["Provision_avg"] + saison["Sonder_avg"]

    # Forecast: nächste 12 Monate
    forecast_monate = []
    for i in range(1, 13):
        # nächster Monat ab jetzt
        monat_dt = pd.Timestamp(heute.year, heute.month, 1) + pd.DateOffset(months=i)
        monat_str = monat_dt.strftime("%Y-%m")
        monat_num = monat_dt.month

        # Saisonaler Basiswert (nur Provision, Sonder separat)
        basis_row = saison[saison["MonatNum"] == monat_num]
        if len(basis_row) > 0:
            basis_prov = basis_row["Provision_avg"].values[0]
            basis_sonder = basis_row["Sonder_avg"].values[0]
        else:
            basis_prov = df_hist["Provision"].mean()
            basis_sonder = 0

        # +Wachstum nur auf Provision (Sonder nicht hochrechnen)
        fc_prov = basis_prov * (1 + wachstum_pct / 100)
        fc_erloes = fc_prov + basis_sonder

        # Ziel-Stunden: Erlös * (1 - Marge) / Stundensatz
        max_personalkosten = fc_erloes * (1 - ziel_marge / 100)
        max_stunden = max_personalkosten / avg_stundensatz if avg_stundensatz > 0 else 0

        # Vergleich mit historischen Ø-Stunden für diesen Monat
        hist_stunden_row = df_hist[df_hist["MonatNum"] == monat_num]["Stunden_gesamt"].mean() if "MonatNum" in df_hist.columns else 0

        forecast_monate.append({
            "Monat": monat_str,
            "Forecast Erlös €": fc_erloes,
            "Forecast Provision €": fc_prov,
            "Max. Personalkosten €": max_personalkosten,
            "Max. Stunden": max_stunden,
            "Hist. Ø Stunden": hist_stunden_row,
        })

    df_fc = pd.DataFrame(forecast_monate)
    df_hist["MonatNum"] = pd.to_datetime(df_hist["Monat"]).dt.month

    with fc2:
        # KPI-Zeile
        a1, a2, a3 = st.columns(3)
        a1.metric("💰 Ø Forecast Erlös/Monat", f"{df_fc['Forecast Erlös €'].mean():,.0f} €".replace(',','.'))
        a2.metric("⏱️ Max. Stunden/Monat (Ø)", f"{df_fc['Max. Stunden'].mean():.1f} h")
        a3.metric("🎯 Ziel-Marge", f"{ziel_marge} %")

    st.markdown("---")

    # Chart: Forecast Erlös
    fig_fc1 = go.Figure()
    fig_fc1.add_trace(go.Bar(
        name="Forecast Provision", x=df_fc["Monat"], y=df_fc["Forecast Provision €"],
        marker_color="#3b82f6"
    ))
    fig_fc1.add_trace(go.Bar(
        name="Max. Personalkosten (Ziel-Marge)", x=df_fc["Monat"], y=df_fc["Max. Personalkosten €"],
        marker_color="#f59e0b"
    ))
    fig_fc1.update_layout(barmode="group", height=340,
                          title=f"Forecast Erlös vs. max. Personalkosten (Ziel: {ziel_marge}% Marge)",
                          xaxis_title="", yaxis_title="€")
    st.plotly_chart(fig_fc1, use_container_width=True)

    # Chart: Max. Stunden vs. historische Stunden
    fig_fc2 = go.Figure()
    fig_fc2.add_trace(go.Bar(
        name="Max. erlaubte Stunden", x=df_fc["Monat"], y=df_fc["Max. Stunden"],
        marker_color="#10b981"
    ))
    fig_fc2.add_trace(go.Scatter(
        name="Hist. Ø Stunden (saisonal)", x=df_fc["Monat"], y=df_fc["Hist. Ø Stunden"],
        mode="lines+markers", line=dict(color="#ef4444", width=2, dash="dash")
    ))
    fig_fc2.update_layout(height=320,
                          title="Max. erlaubte Stunden für Ziel-Marge vs. historischer Aufwand",
                          xaxis_title="", yaxis_title="Stunden")
    st.plotly_chart(fig_fc2, use_container_width=True)

    # Tabelle
    st.markdown("### 🗒️ Forecast-Tabelle")
    df_fc_display = df_fc.copy()
    for col in ["Forecast Erlös €", "Forecast Provision €", "Max. Personalkosten €"]:
        df_fc_display[col] = df_fc_display[col].map(lambda x: f"{x:,.0f} €".replace(',','.'))
    df_fc_display["Max. Stunden"] = df_fc_display["Max. Stunden"].map(lambda x: f"{x:.1f} h")
    df_fc_display["Hist. Ø Stunden"] = df_fc_display["Hist. Ø Stunden"].map(lambda x: f"{x:.1f} h")
    st.dataframe(df_fc_display, use_container_width=True, hide_index=True)
