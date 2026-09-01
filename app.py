"""
Tablero RNDC - Edinsa
Dashboard interactivo para estadísticas de transporte RNDC
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import glob
import os

# ─── Configuración de página ─────────────────────────────────────────────────
st.set_page_config(
    page_title="Tablero RNDC - Edinsa",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Paleta de colores (dataviz skill) ────────────────────────────────────────
COLORS = {
    "blue": "#2a78d6",
    "orange": "#eb6834",
    "aqua": "#1baf7a",
    "yellow": "#eda100",
    "magenta": "#e87ba4",
    "green": "#008300",
    "violet": "#4a3aa7",
    "red": "#e34948",
}
CAT_COLORS = list(COLORS.values())

SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"

# ─── Estilos CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
    [data-testid="stMetric"] {
        background: #fcfcfb;
        border: 1px solid #e1e0d9;
        border-radius: 8px;
        padding: 12px 16px;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.8rem;
        font-weight: 600;
        color: #0b0b0b;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.85rem;
        color: #52514e;
    }
    .block-container { padding-top: 1rem; }
    h1, h2, h3 { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }
</style>
""", unsafe_allow_html=True)


# ─── Funciones de carga de datos ──────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_estadisticas():
    """Carga todos los archivos EstadisticasRNDC (parquet y xlsx)."""
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    frames = []

    # Cargar parquet
    for f in sorted(glob.glob(os.path.join(data_dir, "EstadisticasRNDC_*.parquet"))):
        df = pd.read_parquet(f)
        frames.append(df)

    # Cargar xlsx con mismas columnas
    for f in sorted(glob.glob(os.path.join(data_dir, "EstadisticasRNDC_*.xlsx"))):
        df = pd.read_excel(f)
        frames.append(df)

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)

    # Crear columnas de fecha
    df["MES"] = df["MES"].astype(str)
    df["AÑO"] = df["MES"].str[:4]
    df["MES_NUM"] = df["MES"].str[4:6].astype(int)
    df["PERIODO"] = pd.to_datetime(df["MES"], format="%Y%m")
    df["MES_NOMBRE"] = df["PERIODO"].dt.strftime("%b %Y")

    # Toneladas desde kilogramos
    df["TONELADAS"] = df["KILOGRAMOS"] / 1000

    return df


@st.cache_data(ttl=3600)
def load_ranking():
    """Carga TODOS los archivos de ranking por empresa y los concatena."""
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    files = glob.glob(os.path.join(data_dir, "*.xlsx"))
    frames = []
    for f in sorted(files):
        basename = os.path.basename(f)
        # Excluir archivos que NO son ranking
        if any(kw in basename for kw in ["Estadisticas", "Costo", "Rutas", "Sicetac"]):
            continue
        try:
            df = pd.read_excel(f)
            if "Nombre Empresa" in df.columns:
                frames.append(df)
        except Exception:
            continue

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    # Eliminar duplicados por si un mismo mes se cargó dos veces
    if "Date" in df.columns and "Nombre Empresa" in df.columns:
        df = df.drop_duplicates(subset=["Date", "Nombre Empresa"], keep="last")
    return df


@st.cache_data(ttl=3600)
def load_sicetac():
    """Carga TODOS los archivos SICETAC y los concatena."""
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    frames = []

    for f in sorted(glob.glob(os.path.join(data_dir, "Sicetac_*.parquet"))):
        frames.append(pd.read_parquet(f))
    for f in sorted(glob.glob(os.path.join(data_dir, "Sicetac_*.xlsx"))):
        frames.append(pd.read_excel(f))

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    if "PERIODO" in df.columns:
        df = df.drop_duplicates()
    return df


@st.cache_data(ttl=3600)
def load_costos_fp():
    """Carga TODOS los archivos de costos de flota propia y los concatena."""
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    frames = []

    for f in sorted(glob.glob(os.path.join(data_dir, "Costo ruta flota propia*.xlsx"))):
        try:
            frames.append(pd.read_excel(f))
        except Exception:
            continue

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    if "fecha" in df.columns:
        df = df.drop_duplicates()
    return df


# ─── Layout de gráficos Plotly (template compartido) ──────────────────────────
def chart_layout(fig, title="", height=400):
    """Aplica el layout estándar a una figura Plotly."""
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color=TEXT_PRIMARY, family="system-ui, sans-serif")),
        plot_bgcolor=SURFACE,
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="system-ui, -apple-system, 'Segoe UI', sans-serif", color=TEXT_SECONDARY, size=12),
        height=height,
        margin=dict(l=40, r=20, t=50, b=40),
        xaxis=dict(
            gridcolor=GRIDLINE,
            linecolor=BASELINE,
            zerolinecolor=BASELINE,
            tickfont=dict(color=TEXT_SECONDARY),
        ),
        yaxis=dict(
            gridcolor=GRIDLINE,
            linecolor=BASELINE,
            zerolinecolor=BASELINE,
            tickfont=dict(color=TEXT_SECONDARY),
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(color=TEXT_SECONDARY, size=11),
        ),
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_family="system-ui, sans-serif",
        ),
    )
    return fig


# ─── Carga de datos ──────────────────────────────────────────────────────────
df_stats = load_estadisticas()
df_ranking = load_ranking()
df_sicetac = load_sicetac()
df_costos = load_costos_fp()

# ─── Sidebar ─────────────────────────────────────────────────────────────────
st.sidebar.image("https://img.icons8.com/fluency/48/truck.png", width=40)
st.sidebar.title("Tablero RNDC")
st.sidebar.caption("Edinsa - Estadísticas de transporte")

pagina = st.sidebar.radio(
    "Navegación",
    ["📊 Ranking Empresa", "📦 Estadísticas de Carga", "💰 Comparación Flete FP", "📋 Tabla Consolidada"],
    label_visibility="collapsed",
)

st.sidebar.divider()

# ─── Filtros globales ─────────────────────────────────────────────────────────
if not df_stats.empty:
    años_disponibles = sorted(df_stats["AÑO"].unique())
    año_sel = st.sidebar.multiselect("Año", años_disponibles, default=años_disponibles)

    meses_disponibles = sorted(df_stats[df_stats["AÑO"].isin(año_sel)]["MES_NUM"].unique())
    meses_nombres = {1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
                     7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"}
    mes_sel = st.sidebar.multiselect(
        "Mes",
        meses_disponibles,
        default=meses_disponibles,
        format_func=lambda x: meses_nombres.get(x, str(x)),
    )

    # Filtrar datos base
    mask = df_stats["AÑO"].isin(año_sel) & df_stats["MES_NUM"].isin(mes_sel)
    df_filtrado = df_stats[mask].copy()
else:
    df_filtrado = df_stats
    año_sel = []
    mes_sel = []


# ── Constante: nombre de EDINSA en los datos ─────────────────────────────────
EDINSA_NAME = "EMPRESA DE DISTRIBUCIONES INDUSTRIALES S.A."
EDINSA_COLOR = COLORS["orange"]  # naranja para resaltar
OTHER_COLOR = COLORS["blue"]     # azul para las demás

# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA 1: RANKING EMPRESA
# ══════════════════════════════════════════════════════════════════════════════
if pagina == "📊 Ranking Empresa":
    st.title("Ranking Empresa RNDC")

    if df_ranking.empty:
        st.warning("No se encontró el archivo de ranking de empresas.")
    else:
        # Limpiar datos
        df_rank = df_ranking.copy()
        df_rank = df_rank.dropna(subset=["Nombre Empresa"])
        df_rank["Nombre Empresa"] = df_rank["Nombre Empresa"].str.strip()
        df_rank["Toneladas"] = pd.to_numeric(df_rank["Toneladas"], errors="coerce").fillna(0)
        df_rank["Manifiestos Radicados"] = pd.to_numeric(df_rank["Manifiestos Radicados"], errors="coerce").fillna(0)
        df_rank["Galones"] = pd.to_numeric(df_rank.get("Galones", 0), errors="coerce").fillna(0)

        # Detectar meses disponibles
        if "Date" in df_rank.columns:
            df_rank["Date"] = pd.to_datetime(df_rank["Date"], errors="coerce")
            df_rank["Mes_Num"] = df_rank["Date"].dt.month
            df_rank["Año"] = df_rank["Date"].dt.year
            meses_map = {1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
                         7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"}
            df_rank["Mes_Nombre"] = df_rank["Mes_Num"].map(meses_map)

        # ── Filtros de año/mes en el sidebar para ranking ─────────────────────
        if "Año" in df_rank.columns:
            años_rank = sorted(df_rank["Año"].dropna().unique().astype(int))
            año_rank_sel = st.sidebar.multiselect("Año (Ranking)", años_rank, default=años_rank, key="rank_año")
            df_rank = df_rank[df_rank["Año"].isin(año_rank_sel)]

        # ── KPIs ─────────────────────────────────────────────────────────────
        total_empresas = df_rank["Nombre Empresa"].nunique()
        total_tons = df_rank["Toneladas"].sum()
        total_manifiestos = df_rank["Manifiestos Radicados"].sum()

        # Datos de EDINSA
        df_edinsa = df_rank[df_rank["Nombre Empresa"].str.contains("DISTRIBUCIONES INDUSTRIALES", case=False, na=False)]
        tons_edinsa = df_edinsa["Toneladas"].sum()
        pct_edinsa = (tons_edinsa / total_tons * 100) if total_tons > 0 else 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Empresas", f"{total_empresas:,.0f}")
        col2.metric("Tons Totales Mercado", f"{total_tons:,.0f}")
        col3.metric("Tons EDINSA", f"{tons_edinsa:,.0f}")
        col4.metric("% Participación EDINSA", f"{pct_edinsa:.1f} %")

        st.divider()

        # ── Tabla de participación EDINSA por mes ─────────────────────────────
        if "Mes_Nombre" in df_rank.columns and not df_edinsa.empty:
            st.subheader("% de Tons transportadas por EDINSA en Colombia")

            # Agrupar por mes
            tons_mes_total = df_rank.groupby(["Mes_Num", "Mes_Nombre"], as_index=False)["Toneladas"].sum()
            tons_mes_total.columns = ["Mes_Num", "Mes", "Tons Empresa"]

            tons_mes_edinsa = df_edinsa.groupby(["Mes_Num", "Mes_Nombre"], as_index=False)["Toneladas"].sum()
            tons_mes_edinsa.columns = ["Mes_Num", "Mes", "Tons EDINSA"]

            df_participacion = tons_mes_total.merge(tons_mes_edinsa, on=["Mes_Num", "Mes"], how="left")
            df_participacion["Tons EDINSA"] = df_participacion["Tons EDINSA"].fillna(0)
            df_participacion["% participación tons EDINSA"] = (
                df_participacion["Tons EDINSA"] / df_participacion["Tons Empresa"] * 100
            ).round(1)
            df_participacion = df_participacion.sort_values("Mes_Num")

            # Fila de totales
            total_row = pd.DataFrame([{
                "Mes_Num": 99,
                "Mes": "Total",
                "Tons EDINSA": df_participacion["Tons EDINSA"].sum(),
                "Tons Empresa": df_participacion["Tons Empresa"].sum(),
                "% participación tons EDINSA": round(
                    df_participacion["Tons EDINSA"].sum() / df_participacion["Tons Empresa"].sum() * 100, 1
                ) if df_participacion["Tons Empresa"].sum() > 0 else 0,
            }])
            df_participacion = pd.concat([df_participacion, total_row], ignore_index=True)

            # Mostrar tabla con formato
            df_show_part = df_participacion[["Mes", "Tons EDINSA", "Tons Empresa", "% participación tons EDINSA"]].copy()
            st.dataframe(
                df_show_part.style.format({
                    "Tons EDINSA": "{:,.0f}",
                    "Tons Empresa": "{:,.0f}",
                    "% participación tons EDINSA": "{:.1f} %",
                }).apply(
                    lambda row: ["font-weight: bold"] * len(row) if row["Mes"] == "Total" else [""] * len(row),
                    axis=1,
                ),
                use_container_width=True,
                hide_index=True,
                height=min(400, (len(df_participacion) + 1) * 38),
            )

            # Gráfico de línea: participación EDINSA por mes
            df_part_chart = df_participacion[df_participacion["Mes"] != "Total"].copy()
            fig_part = go.Figure()
            fig_part.add_trace(go.Bar(
                x=df_part_chart["Mes"],
                y=df_part_chart["Tons EDINSA"],
                name="Tons EDINSA",
                marker=dict(color=EDINSA_COLOR, cornerradius=4),
                hovertemplate="<b>%{x}</b><br>Tons EDINSA: %{y:,.0f}<extra></extra>",
                yaxis="y",
            ))
            fig_part.add_trace(go.Scatter(
                x=df_part_chart["Mes"],
                y=df_part_chart["% participación tons EDINSA"],
                name="% Participación",
                mode="lines+markers+text",
                text=[f"{v:.1f}%" for v in df_part_chart["% participación tons EDINSA"]],
                textposition="top center",
                textfont=dict(color=TEXT_SECONDARY, size=11),
                line=dict(color=COLORS["aqua"], width=2),
                marker=dict(size=8),
                hovertemplate="<b>%{x}</b><br>Participación: %{y:.1f}%<extra></extra>",
                yaxis="y2",
            ))
            fig_part.update_layout(
                yaxis2=dict(
                    overlaying="y", side="right",
                    gridcolor="rgba(0,0,0,0)",
                    tickfont=dict(color=COLORS["aqua"]),
                    ticksuffix="%",
                    range=[0, max(df_part_chart["% participación tons EDINSA"].max() * 2, 5)],
                ),
            )
            chart_layout(fig_part, "Toneladas EDINSA y % Participación por Mes", height=380)
            st.plotly_chart(fig_part, use_container_width=True)

        st.divider()

        # ── Top empresas por toneladas (con EDINSA resaltada) ─────────────────
        top_n = st.slider("Top empresas a mostrar", 10, 50, 20)

        # Agrupar por empresa (sumando todos los meses)
        df_rank_agg = df_rank.groupby("Nombre Empresa", as_index=False).agg(
            Toneladas=("Toneladas", "sum"),
            Manifiestos=("Manifiestos Radicados", "sum"),
        )
        df_top = df_rank_agg.nlargest(top_n, "Toneladas").sort_values("Toneladas")

        # Asignar color: naranja para EDINSA, azul para las demás
        df_top["es_edinsa"] = df_top["Nombre Empresa"].str.contains("DISTRIBUCIONES INDUSTRIALES", case=False, na=False)
        bar_colors = [EDINSA_COLOR if es else OTHER_COLOR for es in df_top["es_edinsa"]]

        fig_bar = go.Figure(go.Bar(
            y=df_top["Nombre Empresa"],
            x=df_top["Toneladas"],
            orientation="h",
            marker=dict(color=bar_colors, cornerradius=4),
            hovertemplate="<b>%{y}</b><br>Toneladas: %{x:,.0f}<extra></extra>",
        ))
        chart_layout(fig_bar, f"Top {top_n} Empresas por Toneladas", height=max(400, top_n * 28))
        st.plotly_chart(fig_bar, use_container_width=True)

        # ── Tabla detallada y scatter ─────────────────────────────────────────
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Tabla por Empresa")
            df_tabla = df_rank_agg[["Nombre Empresa", "Manifiestos", "Toneladas"]].copy()
            df_tabla["% Participación"] = (df_tabla["Toneladas"] / df_tabla["Toneladas"].sum() * 100).round(2)
            df_tabla = df_tabla.sort_values("Toneladas", ascending=False).reset_index(drop=True)
            df_tabla.index += 1

            # Resaltar EDINSA en la tabla
            def highlight_edinsa(row):
                if "DISTRIBUCIONES INDUSTRIALES" in str(row["Nombre Empresa"]).upper():
                    return [f"background-color: {EDINSA_COLOR}22; font-weight: bold; color: {EDINSA_COLOR}"] * len(row)
                return [""] * len(row)

            st.dataframe(
                df_tabla.style.apply(highlight_edinsa, axis=1).format({
                    "Manifiestos": "{:,.0f}",
                    "Toneladas": "{:,.0f}",
                    "% Participación": "{:.2f} %",
                }),
                use_container_width=True,
                height=500,
            )

        with col_b:
            st.subheader("Manifiestos vs Toneladas")
            df_top_scatter = df_rank_agg.nlargest(top_n, "Toneladas")
            df_top_scatter["es_edinsa"] = df_top_scatter["Nombre Empresa"].str.contains(
                "DISTRIBUCIONES INDUSTRIALES", case=False, na=False
            )

            # Otras empresas
            df_other = df_top_scatter[~df_top_scatter["es_edinsa"]]
            df_ed = df_top_scatter[df_top_scatter["es_edinsa"]]

            fig_scatter = go.Figure()
            fig_scatter.add_trace(go.Scatter(
                x=df_other["Manifiestos"],
                y=df_other["Toneladas"],
                mode="markers",
                name="Otras empresas",
                text=df_other["Nombre Empresa"],
                marker=dict(color=OTHER_COLOR, size=10, line=dict(width=1, color="white")),
                hovertemplate="<b>%{text}</b><br>Manifiestos: %{x:,.0f}<br>Toneladas: %{y:,.0f}<extra></extra>",
            ))
            if not df_ed.empty:
                fig_scatter.add_trace(go.Scatter(
                    x=df_ed["Manifiestos"],
                    y=df_ed["Toneladas"],
                    mode="markers+text",
                    name="EDINSA",
                    text=["EDINSA"],
                    textposition="top center",
                    textfont=dict(color=EDINSA_COLOR, size=12, family="system-ui, sans-serif"),
                    marker=dict(color=EDINSA_COLOR, size=16, line=dict(width=2, color="white"),
                                symbol="diamond"),
                    hovertemplate="<b>EDINSA</b><br>Manifiestos: %{x:,.0f}<br>Toneladas: %{y:,.0f}<extra></extra>",
                ))
            chart_layout(fig_scatter, "Relación Manifiestos vs Toneladas", height=500)
            st.plotly_chart(fig_scatter, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA 2: ESTADÍSTICAS DE CARGA
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "📦 Estadísticas de Carga":
    st.title("Estadísticas de Carga")

    if df_filtrado.empty:
        st.warning("No hay datos para los filtros seleccionados.")
    else:
        # Filtros adicionales en la página
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        with col_f1:
            configs = ["Todos"] + sorted(df_filtrado["CONFIG_VEHICULO"].dropna().unique().tolist())
            config_sel = st.selectbox("Configuración vehículo", configs)
        with col_f2:
            deptos_orig = ["Todos"] + sorted(df_filtrado["DEPARTAMENTOORIGEN"].dropna().unique().tolist())
            depto_orig_sel = st.selectbox("Depto. Origen", deptos_orig)
        with col_f3:
            deptos_dest = ["Todos"] + sorted(df_filtrado["DEPARTAMENTODESTINO"].dropna().unique().tolist())
            depto_dest_sel = st.selectbox("Depto. Destino", deptos_dest)
        with col_f4:
            mercancias = ["Todos"] + sorted(df_filtrado["MERCANCIA"].dropna().unique().tolist())
            mercancia_sel = st.selectbox("Mercancía", mercancias)

        df_f = df_filtrado.copy()
        if config_sel != "Todos":
            df_f = df_f[df_f["CONFIG_VEHICULO"] == config_sel]
        if depto_orig_sel != "Todos":
            df_f = df_f[df_f["DEPARTAMENTOORIGEN"] == depto_orig_sel]
        if depto_dest_sel != "Todos":
            df_f = df_f[df_f["DEPARTAMENTODESTINO"] == depto_dest_sel]
        if mercancia_sel != "Todos":
            df_f = df_f[df_f["MERCANCIA"] == mercancia_sel]

        # KPIs
        col1, col2, col3, col4 = st.columns(4)
        total_viajes = df_f["VIAJESTOTALES"].sum()
        total_tons = df_f["TONELADAS"].sum()
        total_flete = df_f["VALORESPAGADOS"].sum()
        flete_promedio = df_f["VALORESPAGADOS"].sum() / max(df_f["VIAJESTOTALES"].sum(), 1)

        col1.metric("Viajes", f"{total_viajes:,.0f}")
        col2.metric("Toneladas", f"{total_tons:,.0f}")
        col3.metric("Flete Pagado", f"${total_flete:,.0f}")
        col4.metric("Flete Promedio", f"${flete_promedio:,.0f}")

        st.divider()

        # Fila 1: Naturaleza de carga + Configuración vehículo
        col_a, col_b = st.columns(2)

        with col_a:
            df_nat = df_f.groupby("NATURALEZACARGA", as_index=False)["VIAJESTOTALES"].sum()
            df_nat = df_nat.sort_values("VIAJESTOTALES", ascending=False)
            fig_nat = px.pie(
                df_nat,
                names="NATURALEZACARGA",
                values="VIAJESTOTALES",
                color_discrete_sequence=CAT_COLORS,
                hole=0.4,
            )
            fig_nat.update_traces(
                textposition="inside",
                textinfo="percent+label",
                hovertemplate="<b>%{label}</b><br>Viajes: %{value:,.0f}<br>%{percent}<extra></extra>",
                marker=dict(line=dict(color=SURFACE, width=2)),
            )
            chart_layout(fig_nat, "Viajes por Naturaleza de Carga", height=380)
            st.plotly_chart(fig_nat, use_container_width=True)

        with col_b:
            df_cfg = df_f.groupby("CONFIG_VEHICULO", as_index=False)["VIAJESTOTALES"].sum()
            df_cfg = df_cfg.nlargest(8, "VIAJESTOTALES")
            fig_cfg = px.pie(
                df_cfg,
                names="CONFIG_VEHICULO",
                values="VIAJESTOTALES",
                color_discrete_sequence=CAT_COLORS,
                hole=0.4,
            )
            fig_cfg.update_traces(
                textposition="inside",
                textinfo="percent+label",
                hovertemplate="<b>%{label}</b><br>Viajes: %{value:,.0f}<br>%{percent}<extra></extra>",
                marker=dict(line=dict(color=SURFACE, width=2)),
            )
            chart_layout(fig_cfg, "Viajes por Configuración Vehículo", height=380)
            st.plotly_chart(fig_cfg, use_container_width=True)

        # Fila 2: Tendencia de viajes y flete por mes
        col_c, col_d = st.columns(2)

        with col_c:
            df_trend = df_f.groupby(["MES_NOMBRE", "PERIODO"], as_index=False).agg(
                Viajes=("VIAJESTOTALES", "sum")
            ).sort_values("PERIODO")

            fig_trend = px.line(
                df_trend,
                x="MES_NOMBRE",
                y="Viajes",
                markers=True,
                color_discrete_sequence=[COLORS["blue"]],
            )
            fig_trend.update_traces(
                line=dict(width=2),
                marker=dict(size=8),
                hovertemplate="<b>%{x}</b><br>Viajes: %{y:,.0f}<extra></extra>",
            )
            chart_layout(fig_trend, "Viajes por Mes", height=380)
            st.plotly_chart(fig_trend, use_container_width=True)

        with col_d:
            df_flete = df_f.groupby(["MES_NOMBRE", "PERIODO"], as_index=False).agg(
                Viajes=("VIAJESTOTALES", "sum"),
                Flete=("VALORESPAGADOS", "sum"),
            ).sort_values("PERIODO")
            df_flete["Flete Promedio"] = df_flete["Flete"] / df_flete["Viajes"].replace(0, 1)

            fig_flete = px.line(
                df_flete,
                x="MES_NOMBRE",
                y="Flete Promedio",
                markers=True,
                color_discrete_sequence=[COLORS["orange"]],
            )
            fig_flete.update_traces(
                line=dict(width=2),
                marker=dict(size=8),
                hovertemplate="<b>%{x}</b><br>Flete Prom: $%{y:,.0f}<extra></extra>",
            )
            chart_layout(fig_flete, "Flete Promedio por Mes", height=380)
            st.plotly_chart(fig_flete, use_container_width=True)

        # Fila 3: Top mercancías por toneladas
        df_merc = df_f.groupby("MERCANCIA", as_index=False)["TONELADAS"].sum()
        df_merc = df_merc.nlargest(15, "TONELADAS")

        fig_merc = px.bar(
            df_merc.sort_values("TONELADAS"),
            y="MERCANCIA",
            x="TONELADAS",
            orientation="h",
            color_discrete_sequence=[COLORS["aqua"]],
        )
        fig_merc.update_traces(
            marker=dict(cornerradius=4, line=dict(width=0)),
            hovertemplate="<b>%{y}</b><br>Toneladas: %{x:,.0f}<extra></extra>",
        )
        chart_layout(fig_merc, "Top 15 Mercancías por Toneladas", height=450)
        st.plotly_chart(fig_merc, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA 3: COMPARACIÓN FLETE FP
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "💰 Comparación Flete FP":
    st.title("Comparación Flete: Mercado vs Flota Propia vs SICETAC")

    if df_costos.empty and df_sicetac.empty:
        st.warning("No se encontraron datos de costos de flota propia ni de SICETAC.")
    else:
        # Datos de Flota Propia
        if not df_costos.empty:
            st.subheader("Costos Flota Propia")

            col_f1, col_f2 = st.columns(2)
            with col_f1:
                operaciones = ["Todos"] + sorted(df_costos["Operación"].dropna().unique().tolist())
                op_sel = st.selectbox("Operación", operaciones)
            with col_f2:
                origenes_fp = ["Todos"] + sorted(df_costos["Origen"].dropna().unique().tolist())
                orig_fp_sel = st.selectbox("Origen FP", origenes_fp)

            df_fp = df_costos.copy()
            if op_sel != "Todos":
                df_fp = df_fp[df_fp["Operación"] == op_sel]
            if orig_fp_sel != "Todos":
                df_fp = df_fp[df_fp["Origen"] == orig_fp_sel]

            # KPIs de flota propia
            col1, col2, col3 = st.columns(3)
            flete_prom_carroceria = df_fp["Flete Calculado carrocería"].mean() if "Flete Calculado carrocería" in df_fp.columns else 0
            flete_prom_botellero = df_fp["Flete Calculado Botellero"].mean() if "Flete Calculado Botellero" in df_fp.columns else 0
            rutas_total = len(df_fp)

            col1.metric("Rutas", f"{rutas_total:,.0f}")
            col2.metric("Flete Prom. Carrocería", f"${flete_prom_carroceria:,.0f}")
            col3.metric("Flete Prom. Botellero", f"${flete_prom_botellero:,.0f}")

            # Gráfico comparativo carrocería vs botellero
            if "Flete Calculado carrocería" in df_fp.columns and "Flete Calculado Botellero" in df_fp.columns:
                df_comp = df_fp[["Destino", "Flete Calculado carrocería", "Flete Calculado Botellero"]].copy()
                df_comp = df_comp.dropna()
                df_comp = df_comp.groupby("Destino", as_index=False).mean(numeric_only=True)
                df_comp = df_comp.nlargest(20, "Flete Calculado carrocería")

                fig_comp = go.Figure()
                fig_comp.add_trace(go.Bar(
                    y=df_comp["Destino"],
                    x=df_comp["Flete Calculado carrocería"],
                    name="Carrocería",
                    orientation="h",
                    marker=dict(color=COLORS["blue"], cornerradius=4),
                    hovertemplate="<b>%{y}</b><br>Carrocería: $%{x:,.0f}<extra></extra>",
                ))
                fig_comp.add_trace(go.Bar(
                    y=df_comp["Destino"],
                    x=df_comp["Flete Calculado Botellero"],
                    name="Botellero",
                    orientation="h",
                    marker=dict(color=COLORS["orange"], cornerradius=4),
                    hovertemplate="<b>%{y}</b><br>Botellero: $%{x:,.0f}<extra></extra>",
                ))
                fig_comp.update_layout(barmode="group")
                chart_layout(fig_comp, "Flete Calculado: Carrocería vs Botellero (Top 20 destinos)", height=550)
                st.plotly_chart(fig_comp, use_container_width=True)

        st.divider()

        # Datos SICETAC
        if not df_sicetac.empty:
            st.subheader("Tarifas SICETAC")

            col_s1, col_s2 = st.columns(2)
            with col_s1:
                configs_sic = ["Todos"] + sorted(df_sicetac["CONFIGURACION"].dropna().unique().tolist())
                config_sic_sel = st.selectbox("Configuración (SICETAC)", configs_sic)
            with col_s2:
                origenes_sic = ["Todos"] + sorted(df_sicetac["NOMORIGEN"].dropna().unique().tolist())
                orig_sic_sel = st.selectbox("Origen (SICETAC)", origenes_sic)

            df_sic = df_sicetac.copy()
            if config_sic_sel != "Todos":
                df_sic = df_sic[df_sic["CONFIGURACION"] == config_sic_sel]
            if orig_sic_sel != "Todos":
                df_sic = df_sic[df_sic["NOMORIGEN"] == orig_sic_sel]

            col1, col2, col3 = st.columns(3)
            valor_prom = df_sic["VALOR"].mean() if "VALOR" in df_sic.columns else 0
            distancia_prom = df_sic["DISTANCIA"].mean() if "DISTANCIA" in df_sic.columns else 0
            rutas_sic = len(df_sic)

            col1.metric("Rutas SICETAC", f"{rutas_sic:,.0f}")
            col2.metric("Valor Promedio", f"${valor_prom:,.0f}")
            col3.metric("Distancia Promedio (km)", f"{distancia_prom:,.0f}")

            # Top destinos por valor
            df_dest_sic = df_sic.groupby("NOMDESTINO", as_index=False).agg(
                Valor_Prom=("VALOR", "mean"),
                Rutas=("VALOR", "count"),
            )
            df_dest_sic = df_dest_sic.nlargest(15, "Valor_Prom")

            fig_sic = px.bar(
                df_dest_sic.sort_values("Valor_Prom"),
                y="NOMDESTINO",
                x="Valor_Prom",
                orientation="h",
                color_discrete_sequence=[COLORS["aqua"]],
            )
            fig_sic.update_traces(
                marker=dict(cornerradius=4),
                hovertemplate="<b>%{y}</b><br>Valor Prom: $%{x:,.0f}<extra></extra>",
            )
            chart_layout(fig_sic, "Top 15 Destinos por Valor Promedio SICETAC", height=450)
            st.plotly_chart(fig_sic, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA 4: TABLA CONSOLIDADA
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "📋 Tabla Consolidada":
    st.title("Tabla Consolidada")

    if df_filtrado.empty:
        st.warning("No hay datos para los filtros seleccionados.")
    else:
        # Filtros adicionales
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            configs_tc = ["Todos"] + sorted(df_filtrado["CONFIG_VEHICULO"].dropna().unique().tolist())
            config_tc_sel = st.selectbox("Configuración", configs_tc, key="tc_config")

        df_tc = df_filtrado.copy()
        if config_tc_sel != "Todos":
            df_tc = df_tc[df_tc["CONFIG_VEHICULO"] == config_tc_sel]

        # Tabla consolidada por mes
        df_consol = df_tc.groupby(["MES_NOMBRE", "PERIODO"], as_index=False).agg(
            Viajes=("VIAJESTOTALES", "sum"),
            Viajes_con_valor=("VIAJESTOTALES", lambda x: (df_tc.loc[x.index, "VALORESPAGADOS"] > 0).sum()),
            Flete_pagado=("VALORESPAGADOS", "sum"),
            Toneladas=("TONELADAS", "sum"),
        ).sort_values("PERIODO")

        df_consol["Flete Promedio"] = (df_consol["Flete_pagado"] / df_consol["Viajes_con_valor"].replace(0, 1)).round(0)

        # KPIs totales
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Viajes", f"{df_consol['Viajes'].sum():,.0f}")
        col2.metric("Viajes con Valor", f"{df_consol['Viajes_con_valor'].sum():,.0f}")
        col3.metric("Flete Pagado Total", f"${df_consol['Flete_pagado'].sum():,.0f}")
        col4.metric("Toneladas Total", f"{df_consol['Toneladas'].sum():,.0f}")

        st.divider()

        # Tabla
        df_display = df_consol[["MES_NOMBRE", "Viajes", "Viajes_con_valor", "Flete_pagado", "Toneladas"]].copy()
        df_display.columns = ["Mes", "Viajes", "Viajes con Valor", "Flete Pagado", "Toneladas"]

        # Formato de números
        st.dataframe(
            df_display.style.format({
                "Viajes": "{:,.0f}",
                "Viajes con Valor": "{:,.0f}",
                "Flete Pagado": "${:,.0f}",
                "Toneladas": "{:,.0f}",
            }),
            use_container_width=True,
            height=400,
            hide_index=True,
        )

        # Gráfico de tendencia
        fig_consol = go.Figure()
        fig_consol.add_trace(go.Bar(
            x=df_consol["MES_NOMBRE"],
            y=df_consol["Viajes"],
            name="Viajes",
            marker=dict(color=COLORS["blue"], cornerradius=4),
            hovertemplate="<b>%{x}</b><br>Viajes: %{y:,.0f}<extra></extra>",
        ))
        fig_consol.add_trace(go.Scatter(
            x=df_consol["MES_NOMBRE"],
            y=df_consol["Toneladas"],
            name="Toneladas",
            yaxis="y2",
            mode="lines+markers",
            line=dict(color=COLORS["orange"], width=2),
            marker=dict(size=8),
            hovertemplate="<b>%{x}</b><br>Toneladas: %{y:,.0f}<extra></extra>",
        ))

        fig_consol.update_layout(
            yaxis2=dict(
                overlaying="y",
                side="right",
                gridcolor="rgba(0,0,0,0)",
                tickfont=dict(color=COLORS["orange"]),
            ),
        )
        chart_layout(fig_consol, "Viajes y Toneladas por Mes", height=420)
        st.plotly_chart(fig_consol, use_container_width=True)


# ─── Footer ──────────────────────────────────────────────────────────────────
st.sidebar.divider()
st.sidebar.caption("Datos: RNDC - Ministerio de Transporte")
st.sidebar.caption("Desarrollado para Edinsa")
