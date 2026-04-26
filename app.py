import streamlit as st
import plotly.express as px
from billing import get_costs_by_project, get_costs_by_service, get_daily_trend

st.set_page_config(
    page_title="GCP Billing Dashboard",
    page_icon="☁️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Header ──────────────────────────────────────────────────────────────────
st.title("☁️ GCP Billing Dashboard")
st.caption("Costos de Google Cloud Platform por aplicativo · Actualización diaria")

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Filtros")

    days = st.select_slider(
        "Período",
        options=[7, 14, 30, 60, 90],
        value=30,
        format_func=lambda x: f"Últimos {x} días",
    )
    currency = st.selectbox("Moneda", ["USD", "PEN"], index=0)

    st.divider()
    if st.button("🔄 Actualizar datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.caption("⏱ Datos con 1-2 días de retraso (GCP Billing Export lag)")

# ── Cargar datos ─────────────────────────────────────────────────────────────
with st.spinner("Cargando datos de facturación..."):
    try:
        df_projects = get_costs_by_project(days)
        df_services = get_costs_by_service(days)
        df_trend    = get_daily_trend(days)
    except Exception as e:
        st.error(f"❌ No se pudo conectar con BigQuery: {e}")
        st.info(
            "Verifica que `.streamlit/secrets.toml` esté configurado correctamente "
            "y que el Billing Export a BigQuery esté habilitado. "
            "Revisa `setup-gcp.md` en el Segundo Cerebro para los pasos."
        )
        st.stop()

# Filtrar por moneda seleccionada
proj  = df_projects[df_projects["currency"] == currency].copy()
svc   = df_services[df_services["currency"] == currency].copy()
trend = df_trend[df_trend["currency"] == currency].copy()

# ── KPI Cards ────────────────────────────────────────────────────────────────
total     = proj["net_cost"].sum()
daily_avg = total / days if days > 0 else 0
n_apps    = proj["project_id"].nunique()

if not proj.empty and proj["net_cost"].max() > 0:
    top_row  = proj.loc[proj["net_cost"].idxmax()]
    top_name = top_row["app_name"]
    top_cost = top_row["net_cost"]
else:
    top_name, top_cost = "N/A", 0.0

c1, c2, c3, c4 = st.columns(4)
c1.metric("💰 Gasto Total",       f"{currency} {total:,.2f}")
c2.metric("📱 App más costosa",   top_name, f"{currency} {top_cost:,.2f}")
c3.metric("📅 Promedio diario",   f"{currency} {daily_avg:,.4f}")
c4.metric("🔢 Proyectos activos", n_apps)

st.divider()

# Color consistente entre gráficos
all_apps  = sorted(df_projects["app_name"].unique().tolist())
palette   = px.colors.qualitative.Set2
color_map = {app: palette[i % len(palette)] for i, app in enumerate(all_apps)}

# ── Fila 1: Costo por app + Desglose de servicios ───────────────────────────
col_bar, col_pie = st.columns([3, 2])

with col_bar:
    st.subheader("Costo por Aplicativo")
    if not proj.empty:
        fig = px.bar(
            proj.sort_values("net_cost"),
            x="net_cost",
            y="app_name",
            orientation="h",
            color="app_name",
            color_discrete_map=color_map,
            text_auto=".2f",
            labels={"net_cost": f"Costo neto ({currency})", "app_name": ""},
        )
        fig.update_layout(showlegend=False, height=300, margin=dict(l=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sin datos para el período y moneda seleccionados.")

with col_pie:
    st.subheader("Servicios")
    app_options = ["Todos"] + sorted(proj["app_name"].unique().tolist())
    selected_app = st.selectbox("Ver servicios de:", app_options)

    if selected_app == "Todos":
        svc_view = svc
    else:
        pid      = proj.loc[proj["app_name"] == selected_app, "project_id"].iloc[0]
        svc_view = svc[svc["project_id"] == pid]

    if not svc_view.empty:
        top_svc = svc_view.nlargest(8, "net_cost")
        fig = px.pie(
            top_svc,
            names="service",
            values="net_cost",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Pastel,
        )
        fig.update_traces(textposition="inside", textinfo="percent+label")
        fig.update_layout(showlegend=False, height=300)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sin datos de servicios para la selección.")

# ── Fila 2: Tendencia diaria ─────────────────────────────────────────────────
st.subheader("Tendencia Diaria por Aplicativo")
if not trend.empty:
    fig = px.line(
        trend,
        x="date",
        y="net_cost",
        color="app_name",
        color_discrete_map=color_map,
        markers=True,
        labels={"net_cost": f"Costo neto ({currency})", "date": "Fecha", "app_name": "Aplicativo"},
    )
    fig.update_layout(height=350, hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Sin datos de tendencia para el período seleccionado.")

# ── Fila 3: Tabla detallada ──────────────────────────────────────────────────
st.subheader("Detalle por Aplicativo y Servicio")
if not svc.empty:
    table = (
        svc[["app_name", "service", "net_cost"]]
        .sort_values(["net_cost"], ascending=False)
        .rename(columns={
            "app_name": "Aplicativo",
            "service":  "Servicio GCP",
            "net_cost": f"Costo neto ({currency})",
        })
    )
    st.dataframe(table, use_container_width=True, hide_index=True)
else:
    st.info("Sin datos detallados.")
