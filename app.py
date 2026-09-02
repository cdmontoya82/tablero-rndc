"""
Tablero RNDC - Edinsa
Dashboard interactivo para estadísticas de transporte RNDC
(Versión optimizada para Streamlit Cloud — pre-agregación de datos)
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import glob
import os
import gc

# ─── Columnas de pre-agregación unificada ────────────────────────────────────
# Un solo dataset que sirve para las 4 páginas
STATS_LOAD_COLS = [
    "MES", "CONFIG_VEHICULO", "COD_CONFIG_VEHICULO", "NATURALEZACARGA", "MERCANCIA",
    "DEPARTAMENTOORIGEN", "DEPARTAMENTODESTINO",
    "MUNICIPIOORIGEN", "MUNICIPIODESTINO",
    "VIAJESTOTALES", "KILOGRAMOS", "VALORESPAGADOS", "VIAJESVALORCERO",
]
STATS_GROUP_COLS = [
    "MES", "CONFIG_VEHICULO", "COD_CONFIG_VEHICULO", "NATURALEZACARGA", "MERCANCIA",
    "DEPARTAMENTOORIGEN", "DEPARTAMENTODESTINO",
    "MUNICIPIOORIGEN", "MUNICIPIODESTINO",
]
SICETAC_COLUMNS = [
    "PERIODO", "NOMORIGEN", "NOMDESTINO", "CONFIGURACION", "VALOR", "DISTANCIA",
]

# ─── Configuración de página ─────────────────────────────────────────────────
st.set_page_config(
    page_title="Tablero RNDC - Edinsa",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Paleta de colores ───────────────────────────────────────────────────────
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

MESES_NOMBRE = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}
MESES_CORTO = {1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
               7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"}

# Colores para años en gráficos multi-año
YEAR_COLORS = {"2024": COLORS["blue"], "2025": "#1a1a6e", "2026": COLORS["orange"]}

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


# ─── Funciones auxiliares ────────────────────────────────────────────────────
_load_log = []


def _get_data_dir():
    try:
        base = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        base = os.getcwd()
    data_dir = os.path.join(base, "data")
    if not os.path.isdir(data_dir):
        data_dir = os.path.join(os.getcwd(), "data")
    return data_dir


def _to_category(df, cols):
    for col in cols:
        if col in df.columns:
            df[col] = df[col].astype("category")
    return df


# ─── Carga de datos ──────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_estadisticas():
    """Carga EstadisticasRNDC con PRE-AGREGACIÓN unificada.

    Un solo dataset con municipio + departamento + config que sirve para
    páginas 2 (Estadísticas), 3 (Comparativo) y 4 (Tabla Consolidada).
    """
    data_dir = _get_data_dir()
    agg_frames = []

    all_files = (
        sorted(glob.glob(os.path.join(data_dir, "EstadisticasRNDC_*.parquet")))
        + sorted(glob.glob(os.path.join(data_dir, "EstadisticasRNDC_*.xlsx")))
    )

    for f in all_files:
        try:
            if f.endswith(".parquet"):
                raw = pd.read_parquet(f, columns=STATS_LOAD_COLS)
            else:
                raw = pd.read_excel(f, usecols=lambda c: c in STATS_LOAD_COLS)

            _load_log.append(f"OK: {os.path.basename(f)} ({len(raw)} filas)")

            # Viajes con flete = viajes totales - viajes con valor cero
            if "VIAJESVALORCERO" in raw.columns:
                raw["VIAJES_CON_VALOR"] = (
                    raw["VIAJESTOTALES"] - raw["VIAJESVALORCERO"].fillna(0)
                ).clip(lower=0).astype("int32")
            else:
                raw["VIAJES_CON_VALOR"] = raw["VIAJESTOTALES"]

            agg = raw.groupby(STATS_GROUP_COLS, as_index=False, observed=True).agg(
                VIAJESTOTALES=("VIAJESTOTALES", "sum"),
                KILOGRAMOS=("KILOGRAMOS", "sum"),
                VALORESPAGADOS=("VALORESPAGADOS", "sum"),
                VIAJES_CON_VALOR=("VIAJES_CON_VALOR", "sum"),
            )
            agg_frames.append(agg)
            del raw
            gc.collect()

        except Exception as e:
            _load_log.append(f"ERROR {os.path.basename(f)}: {e}")

    if not agg_frames:
        _load_log.append("SIN DATOS: No se encontraron archivos EstadisticasRNDC")
        return pd.DataFrame()

    df = pd.concat(agg_frames, ignore_index=True)
    del agg_frames
    gc.collect()

    df = df.groupby(STATS_GROUP_COLS, as_index=False, observed=True).agg(
        VIAJESTOTALES=("VIAJESTOTALES", "sum"),
        KILOGRAMOS=("KILOGRAMOS", "sum"),
        VALORESPAGADOS=("VALORESPAGADOS", "sum"),
        VIAJES_CON_VALOR=("VIAJES_CON_VALOR", "sum"),
    )

    df["MES"] = df["MES"].astype(str)
    df["AÑO"] = df["MES"].str[:4]
    df["MES_NUM"] = df["MES"].str[4:6].astype(int)
    df["PERIODO"] = pd.to_datetime(df["MES"], format="%Y%m")
    df["MES_NOMBRE"] = df["PERIODO"].dt.strftime("%b %Y")
    df["TONELADAS"] = df["KILOGRAMOS"] / 1000

    _to_category(df, STATS_GROUP_COLS + ["AÑO", "MES_NOMBRE"])
    _load_log.append(f"Estadísticas final: {len(df)} filas pre-agregadas")
    return df


@st.cache_data(ttl=3600)
def load_ranking():
    data_dir = _get_data_dir()
    files = glob.glob(os.path.join(data_dir, "*.xlsx"))
    frames = []
    for f in sorted(files):
        basename = os.path.basename(f)
        if any(kw in basename for kw in ["Estadisticas", "Costo", "Rutas", "Sicetac"]):
            continue
        try:
            df = pd.read_excel(f)
            if "Nombre Empresa" in df.columns:
                frames.append(df)
                _load_log.append(f"OK ranking: {basename} ({len(df)} filas)")
        except Exception as e:
            _load_log.append(f"ERROR ranking {basename}: {e}")

    if not frames:
        _load_log.append("SIN DATOS: No se encontraron archivos de ranking")
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    del frames
    gc.collect()
    if "Date" in df.columns and "Nombre Empresa" in df.columns:
        df = df.drop_duplicates(subset=["Date", "Nombre Empresa"], keep="last")
    return df


@st.cache_data(ttl=3600)
def load_sicetac():
    data_dir = _get_data_dir()
    agg_frames = []

    all_files = (
        sorted(glob.glob(os.path.join(data_dir, "Sicetac_*.parquet")))
        + sorted(glob.glob(os.path.join(data_dir, "Sicetac_*.xlsx")))
    )

    for f in all_files:
        try:
            if f.endswith(".parquet"):
                raw = pd.read_parquet(f, columns=SICETAC_COLUMNS)
            else:
                raw = pd.read_excel(f, usecols=lambda c: c in SICETAC_COLUMNS)

            _load_log.append(f"OK sicetac: {os.path.basename(f)} ({len(raw)} filas)")

            raw["PERIODO"] = raw["PERIODO"].astype(str).str[:6]

            agg = raw.groupby(
                ["PERIODO", "CONFIGURACION", "NOMORIGEN", "NOMDESTINO"], as_index=False, observed=True
            ).agg(
                VALOR_SUMA=("VALOR", "sum"),
                DISTANCIA_SUMA=("DISTANCIA", "sum"),
                CONTEO=("VALOR", "count"),
            )
            agg_frames.append(agg)
            del raw
            gc.collect()

        except Exception as e:
            _load_log.append(f"ERROR sicetac {os.path.basename(f)}: {e}")

    if not agg_frames:
        _load_log.append("SIN DATOS: No se encontraron archivos SICETAC")
        return pd.DataFrame()

    df = pd.concat(agg_frames, ignore_index=True)
    del agg_frames
    gc.collect()

    df = df.groupby(
        ["PERIODO", "CONFIGURACION", "NOMORIGEN", "NOMDESTINO"], as_index=False, observed=True
    ).agg(
        VALOR_SUMA=("VALOR_SUMA", "sum"),
        DISTANCIA_SUMA=("DISTANCIA_SUMA", "sum"),
        CONTEO=("CONTEO", "sum"),
    )
    df["VALOR"] = df["VALOR_SUMA"] / df["CONTEO"]
    df["DISTANCIA"] = df["DISTANCIA_SUMA"] / df["CONTEO"]

    _to_category(df, ["PERIODO", "CONFIGURACION", "NOMORIGEN", "NOMDESTINO"])
    _load_log.append(f"SICETAC final: {len(df)} filas pre-agregadas")
    return df


FP_LOAD_COLS = [
    "fecha", "Origen", "Destino", "Operación",
    "Flete Calculado carrocería", "costo cargue", "Costo descargue",
    "MUNICIPIO_ORIGEN", "MUNICIPIO_DESTINO",
]


@st.cache_data(ttl=3600)
def load_costos_fp():
    data_dir = _get_data_dir()
    frames = []

    for f in sorted(glob.glob(os.path.join(data_dir, "Costo ruta flota propia*.xlsx"))):
        try:
            raw = pd.read_excel(f, usecols=lambda c: c in FP_LOAD_COLS)
            frames.append(raw)
            _load_log.append(f"OK costos: {os.path.basename(f)} ({len(raw)} filas)")
            del raw
        except Exception as e:
            _load_log.append(f"ERROR costos {os.path.basename(f)}: {e}")

    if not frames:
        _load_log.append("SIN DATOS: No se encontraron archivos de costos FP")
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    del frames
    gc.collect()

    if "fecha" in df.columns:
        df = df.drop_duplicates()
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
        df["MES_FP"] = df["fecha"].dt.strftime("%Y%m")

    # Calcular flete sin cargue ni descargue
    if "Flete Calculado carrocería" in df.columns:
        df["Flete_sin_CyD"] = (
            df["Flete Calculado carrocería"]
            - df["costo cargue"].fillna(0)
            - df["Costo descargue"].fillna(0)
        )

    # Normalizar municipios (mayúsculas, sin espacios extra)
    for col in ["MUNICIPIO_ORIGEN", "MUNICIPIO_DESTINO"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.upper()
            df.loc[df[col] == "NAN", col] = None

    return df


# ─── Layout de gráficos Plotly ───────────────────────────────────────────────
def chart_layout(fig, title="", height=400):
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color=TEXT_PRIMARY, family="system-ui, sans-serif")),
        plot_bgcolor=SURFACE,
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="system-ui, -apple-system, 'Segoe UI', sans-serif", color=TEXT_SECONDARY, size=12),
        height=height,
        margin=dict(l=40, r=20, t=50, b=40),
        xaxis=dict(gridcolor=GRIDLINE, linecolor=BASELINE, zerolinecolor=BASELINE, tickfont=dict(color=TEXT_SECONDARY)),
        yaxis=dict(gridcolor=GRIDLINE, linecolor=BASELINE, zerolinecolor=BASELINE, tickfont=dict(color=TEXT_SECONDARY)),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT_SECONDARY, size=11)),
        hoverlabel=dict(bgcolor="white", font_size=12, font_family="system-ui, sans-serif"),
    )
    return fig


# ─── Cargar todos los datasets ───────────────────────────────────────────────
try:
    df_stats = load_estadisticas()
except Exception as e:
    st.error(f"Error cargando Estadísticas: {e}")
    df_stats = pd.DataFrame()

try:
    df_ranking = load_ranking()
except Exception as e:
    st.error(f"Error cargando Ranking: {e}")
    df_ranking = pd.DataFrame()

try:
    df_sicetac = load_sicetac()
except Exception as e:
    st.error(f"Error cargando SICETAC: {e}")
    df_sicetac = pd.DataFrame()

try:
    df_costos = load_costos_fp()
except Exception as e:
    st.error(f"Error cargando Costos FP: {e}")
    df_costos = pd.DataFrame()

gc.collect()

# ─── Sidebar ─────────────────────────────────────────────────────────────────
st.sidebar.title("🚛 Tablero RNDC")
st.sidebar.caption("Edinsa - Estadísticas de transporte")

pagina = st.sidebar.radio(
    "Navegación",
    ["📊 Ranking Empresa", "📦 Estadísticas de Carga", "💰 Comparativo FP y FM", "📋 Tabla Consolidada"],
    label_visibility="collapsed",
)

st.sidebar.divider()

# ─── Filtros globales (para páginas 2 y 4) ───────────────────────────────────
if not df_stats.empty:
    años_disponibles = sorted(df_stats["AÑO"].unique())
    año_sel = st.sidebar.multiselect("Año", años_disponibles, default=años_disponibles)

    meses_disponibles = sorted(df_stats[df_stats["AÑO"].isin(año_sel)]["MES_NUM"].unique())
    mes_sel = st.sidebar.multiselect(
        "Mes", meses_disponibles, default=meses_disponibles,
        format_func=lambda x: MESES_CORTO.get(x, str(x)),
    )

    mask = df_stats["AÑO"].isin(año_sel) & df_stats["MES_NUM"].isin(mes_sel)
    df_filtrado = df_stats[mask].copy()
else:
    df_filtrado = df_stats
    año_sel = []
    mes_sel = []


# ── Constantes EDINSA ─────────────────────────────────────────────────────────
EDINSA_NAME = "EMPRESA DE DISTRIBUCIONES INDUSTRIALES S.A."
EDINSA_COLOR = COLORS["orange"]
OTHER_COLOR = COLORS["blue"]


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA 1: RANKING EMPRESA
# ══════════════════════════════════════════════════════════════════════════════
if pagina == "📊 Ranking Empresa":
    st.title("Ranking Empresa RNDC")

    if df_ranking.empty:
        st.warning("No se encontró el archivo de ranking de empresas.")
    else:
        df_rank = df_ranking.copy()
        df_rank = df_rank.dropna(subset=["Nombre Empresa"])
        df_rank["Nombre Empresa"] = df_rank["Nombre Empresa"].str.strip()
        df_rank["Toneladas"] = pd.to_numeric(df_rank["Toneladas"], errors="coerce").fillna(0)
        df_rank["Manifiestos Radicados"] = pd.to_numeric(df_rank["Manifiestos Radicados"], errors="coerce").fillna(0)

        if "Date" in df_rank.columns:
            df_rank["Date"] = pd.to_datetime(df_rank["Date"], errors="coerce")
            df_rank["Mes_Num"] = df_rank["Date"].dt.month
            df_rank["Año"] = df_rank["Date"].dt.year
            df_rank["Mes_Nombre"] = df_rank["Mes_Num"].map(MESES_NOMBRE)

        if "Año" in df_rank.columns:
            años_rank = sorted(df_rank["Año"].dropna().unique().astype(int))
            año_rank_sel = st.sidebar.multiselect("Año (Ranking)", años_rank, default=años_rank, key="rank_año")
            df_rank = df_rank[df_rank["Año"].isin(año_rank_sel)]

        total_empresas = df_rank["Nombre Empresa"].nunique()
        total_tons = df_rank["Toneladas"].sum()

        df_edinsa = df_rank[df_rank["Nombre Empresa"].str.contains("DISTRIBUCIONES INDUSTRIALES", case=False, na=False)]
        tons_edinsa = df_edinsa["Toneladas"].sum()
        pct_edinsa = (tons_edinsa / total_tons * 100) if total_tons > 0 else 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Empresas", f"{total_empresas:,.0f}")
        col2.metric("Tons Totales Mercado", f"{total_tons:,.0f}")
        col3.metric("Tons EDINSA", f"{tons_edinsa:,.0f}")
        col4.metric("% Participación EDINSA", f"{pct_edinsa:.1f} %")

        st.divider()

        if "Mes_Nombre" in df_rank.columns and not df_edinsa.empty:
            st.subheader("% de Tons transportadas por EDINSA en Colombia")

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

            total_row = pd.DataFrame([{
                "Mes_Num": 99, "Mes": "Total",
                "Tons EDINSA": df_participacion["Tons EDINSA"].sum(),
                "Tons Empresa": df_participacion["Tons Empresa"].sum(),
                "% participación tons EDINSA": round(
                    df_participacion["Tons EDINSA"].sum() / df_participacion["Tons Empresa"].sum() * 100, 1
                ) if df_participacion["Tons Empresa"].sum() > 0 else 0,
            }])
            df_participacion = pd.concat([df_participacion, total_row], ignore_index=True)

            df_show_part = df_participacion[["Mes", "Tons EDINSA", "Tons Empresa", "% participación tons EDINSA"]].copy()
            st.dataframe(
                df_show_part.style.format({
                    "Tons EDINSA": "{:,.0f}", "Tons Empresa": "{:,.0f}",
                    "% participación tons EDINSA": "{:.1f} %",
                }).apply(
                    lambda row: ["font-weight: bold"] * len(row) if row["Mes"] == "Total" else [""] * len(row),
                    axis=1,
                ),
                use_container_width=True, hide_index=True,
                height=min(400, (len(df_participacion) + 1) * 38),
            )

            df_part_chart = df_participacion[df_participacion["Mes"] != "Total"].copy()
            fig_part = go.Figure()
            fig_part.add_trace(go.Bar(
                x=df_part_chart["Mes"], y=df_part_chart["Tons EDINSA"],
                name="Tons EDINSA", marker=dict(color=EDINSA_COLOR, cornerradius=4),
                hovertemplate="<b>%{x}</b><br>Tons EDINSA: %{y:,.0f}<extra></extra>",
            ))
            fig_part.add_trace(go.Scatter(
                x=df_part_chart["Mes"], y=df_part_chart["% participación tons EDINSA"],
                name="% Participación", mode="lines+markers+text",
                text=[f"{v:.1f}%" for v in df_part_chart["% participación tons EDINSA"]],
                textposition="top center", textfont=dict(color=TEXT_SECONDARY, size=11),
                line=dict(color=COLORS["aqua"], width=2), marker=dict(size=8),
                hovertemplate="<b>%{x}</b><br>Participación: %{y:.1f}%<extra></extra>",
                yaxis="y2",
            ))
            fig_part.update_layout(yaxis2=dict(
                overlaying="y", side="right", gridcolor="rgba(0,0,0,0)",
                tickfont=dict(color=COLORS["aqua"]), ticksuffix="%",
                range=[0, max(df_part_chart["% participación tons EDINSA"].max() * 2, 5)],
            ))
            chart_layout(fig_part, "Toneladas EDINSA y % Participación por Mes", height=380)
            st.plotly_chart(fig_part, use_container_width=True)

        st.divider()

        top_n = st.slider("Top empresas a mostrar", 10, 50, 20)
        df_rank_agg = df_rank.groupby("Nombre Empresa", as_index=False).agg(
            Toneladas=("Toneladas", "sum"), Manifiestos=("Manifiestos Radicados", "sum"),
        )
        df_top = df_rank_agg.nlargest(top_n, "Toneladas").sort_values("Toneladas")
        df_top["es_edinsa"] = df_top["Nombre Empresa"].str.contains("DISTRIBUCIONES INDUSTRIALES", case=False, na=False)
        bar_colors = [EDINSA_COLOR if es else OTHER_COLOR for es in df_top["es_edinsa"]]

        fig_bar = go.Figure(go.Bar(
            y=df_top["Nombre Empresa"], x=df_top["Toneladas"], orientation="h",
            marker=dict(color=bar_colors, cornerradius=4),
            hovertemplate="<b>%{y}</b><br>Toneladas: %{x:,.0f}<extra></extra>",
        ))
        chart_layout(fig_bar, f"Top {top_n} Empresas por Toneladas", height=max(400, top_n * 28))
        st.plotly_chart(fig_bar, use_container_width=True)

        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Tabla por Empresa")
            df_tabla = df_rank_agg[["Nombre Empresa", "Manifiestos", "Toneladas"]].copy()
            df_tabla["% Participación"] = (df_tabla["Toneladas"] / df_tabla["Toneladas"].sum() * 100).round(2)
            df_tabla = df_tabla.sort_values("Toneladas", ascending=False).reset_index(drop=True)
            df_tabla.index += 1

            def highlight_edinsa(row):
                if "DISTRIBUCIONES INDUSTRIALES" in str(row["Nombre Empresa"]).upper():
                    return [f"background-color: {EDINSA_COLOR}22; font-weight: bold; color: {EDINSA_COLOR}"] * len(row)
                return [""] * len(row)

            st.dataframe(
                df_tabla.style.apply(highlight_edinsa, axis=1).format({
                    "Manifiestos": "{:,.0f}", "Toneladas": "{:,.0f}", "% Participación": "{:.2f} %",
                }),
                use_container_width=True, height=500,
            )

        with col_b:
            st.subheader("Manifiestos vs Toneladas")
            df_top_scatter = df_rank_agg.nlargest(top_n, "Toneladas")
            df_top_scatter["es_edinsa"] = df_top_scatter["Nombre Empresa"].str.contains(
                "DISTRIBUCIONES INDUSTRIALES", case=False, na=False)
            df_other = df_top_scatter[~df_top_scatter["es_edinsa"]]
            df_ed = df_top_scatter[df_top_scatter["es_edinsa"]]

            fig_scatter = go.Figure()
            fig_scatter.add_trace(go.Scatter(
                x=df_other["Manifiestos"], y=df_other["Toneladas"],
                mode="markers", name="Otras empresas", text=df_other["Nombre Empresa"],
                marker=dict(color=OTHER_COLOR, size=10, line=dict(width=1, color="white")),
                hovertemplate="<b>%{text}</b><br>Manifiestos: %{x:,.0f}<br>Toneladas: %{y:,.0f}<extra></extra>",
            ))
            if not df_ed.empty:
                fig_scatter.add_trace(go.Scatter(
                    x=df_ed["Manifiestos"], y=df_ed["Toneladas"],
                    mode="markers+text", name="EDINSA", text=["EDINSA"],
                    textposition="top center",
                    textfont=dict(color=EDINSA_COLOR, size=12, family="system-ui, sans-serif"),
                    marker=dict(color=EDINSA_COLOR, size=16, line=dict(width=2, color="white"), symbol="diamond"),
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
        # ── Filtros ──────────────────────────────────────────────────────────
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        with col_f1:
            # Usar COD_CONFIG para mostrar formato corto como Power BI
            configs_cod = sorted(df_filtrado["COD_CONFIG_VEHICULO"].dropna().unique().tolist())
            configs_cod = [c for c in configs_cod if c.strip()]
            config_sel = st.selectbox("Configuración", ["Todos"] + configs_cod, key="est_config")
        with col_f2:
            mercancias = ["Todos"] + sorted(df_filtrado["MERCANCIA"].dropna().unique().tolist())
            mercancia_sel = st.selectbox("Mercancía", mercancias, key="est_merc")
        with col_f3:
            deptos_orig = ["Todos"] + sorted(df_filtrado["DEPARTAMENTOORIGEN"].dropna().unique().tolist())
            depto_orig_sel = st.selectbox("Departamento origen", deptos_orig, key="est_depto_o")
        with col_f4:
            deptos_dest = ["Todos"] + sorted(df_filtrado["DEPARTAMENTODESTINO"].dropna().unique().tolist())
            depto_dest_sel = st.selectbox("Departamento destino", deptos_dest, key="est_depto_d")

        col_f5, col_f6, col_f7, col_f8 = st.columns(4)
        with col_f5:
            nat_options = ["Todos"] + sorted(df_filtrado["NATURALEZACARGA"].dropna().unique().tolist())
            nat_sel = st.selectbox("Naturaleza de la carga", nat_options, key="est_nat")
        with col_f6:
            # Municipio origen (filtrado por depto)
            df_temp = df_filtrado.copy()
            if depto_orig_sel != "Todos":
                df_temp = df_temp[df_temp["DEPARTAMENTOORIGEN"] == depto_orig_sel]
            muni_orig_options = sorted(df_temp["MUNICIPIOORIGEN"].dropna().unique().tolist())
            muni_orig_sel = st.selectbox("Municipio origen", ["Todos"] + muni_orig_options, key="est_muni_o")
        with col_f7:
            df_temp2 = df_filtrado.copy()
            if depto_dest_sel != "Todos":
                df_temp2 = df_temp2[df_temp2["DEPARTAMENTODESTINO"] == depto_dest_sel]
            muni_dest_options = sorted(df_temp2["MUNICIPIODESTINO"].dropna().unique().tolist())
            muni_dest_sel = st.selectbox("Municipio destino", ["Todos"] + muni_dest_options, key="est_muni_d")

        # Aplicar filtros
        df_f = df_filtrado.copy()
        if config_sel != "Todos":
            df_f = df_f[df_f["COD_CONFIG_VEHICULO"] == config_sel]
        if mercancia_sel != "Todos":
            df_f = df_f[df_f["MERCANCIA"] == mercancia_sel]
        if depto_orig_sel != "Todos":
            df_f = df_f[df_f["DEPARTAMENTOORIGEN"] == depto_orig_sel]
        if depto_dest_sel != "Todos":
            df_f = df_f[df_f["DEPARTAMENTODESTINO"] == depto_dest_sel]
        if nat_sel != "Todos":
            df_f = df_f[df_f["NATURALEZACARGA"] == nat_sel]
        if muni_orig_sel != "Todos":
            df_f = df_f[df_f["MUNICIPIOORIGEN"] == muni_orig_sel]
        if muni_dest_sel != "Todos":
            df_f = df_f[df_f["MUNICIPIODESTINO"] == muni_dest_sel]

        # ── KPIs ─────────────────────────────────────────────────────────────
        total_viajes = df_f["VIAJESTOTALES"].sum()
        total_tons = df_f["TONELADAS"].sum()
        total_flete = df_f["VALORESPAGADOS"].sum()
        viajes_con_valor = df_f["VIAJES_CON_VALOR"].sum()
        flete_prom = total_flete / max(viajes_con_valor, 1)

        # Promedio de flete por mes (promedio de los promedios mensuales)
        df_prom_mes = df_f.groupby("MES", observed=True).agg(
            V=("VALORESPAGADOS", "sum"), VC=("VIAJES_CON_VALOR", "sum"),
        )
        df_prom_mes["prom"] = df_prom_mes["V"] / df_prom_mes["VC"].replace(0, 1)
        flete_prom_mensual = df_prom_mes["prom"].mean() if len(df_prom_mes) > 0 else 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Viajes", f"{total_viajes:,.0f}")
        col2.metric("Toneladas totales", f"{total_tons:,.0f}")
        col3.metric("Flete promedio", f"${flete_prom:,.0f}")
        col4.metric("Flete promedio mes", f"${flete_prom_mensual:,.0f}")

        st.divider()

        # ── Gráfico 1: Flete promedio por mes, líneas por año ────────────────
        # Solo viajes con valor > 0
        df_flete_trend = df_f.groupby(["AÑO", "MES_NUM"], as_index=False, observed=True).agg(
            VALORESPAGADOS=("VALORESPAGADOS", "sum"),
            VIAJES_CON_VALOR=("VIAJES_CON_VALOR", "sum"),
        )
        df_flete_trend["Flete_Prom"] = df_flete_trend["VALORESPAGADOS"] / df_flete_trend["VIAJES_CON_VALOR"].replace(0, 1)
        df_flete_trend["Mes_Label"] = df_flete_trend["MES_NUM"].map(MESES_NOMBRE)
        df_flete_trend = df_flete_trend.sort_values(["AÑO", "MES_NUM"])

        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            fig_flete = go.Figure()
            for año in sorted(df_flete_trend["AÑO"].unique()):
                df_año = df_flete_trend[df_flete_trend["AÑO"] == año]
                color = YEAR_COLORS.get(str(año), COLORS["violet"])
                fig_flete.add_trace(go.Scatter(
                    x=df_año["Mes_Label"], y=df_año["Flete_Prom"],
                    name=str(año), mode="lines+markers+text",
                    text=[f"{v:,.0f}" for v in df_año["Flete_Prom"]],
                    textposition="top center", textfont=dict(size=9, color=color),
                    line=dict(color=color, width=2), marker=dict(size=6),
                    hovertemplate=f"<b>{año} - %{{x}}</b><br>Flete Prom: $%{{y:,.0f}}<extra></extra>",
                ))
            chart_layout(fig_flete, "Flete promedio", height=420)
            fig_flete.update_layout(xaxis=dict(categoryorder="array",
                                                categoryarray=list(MESES_NOMBRE.values())))
            st.plotly_chart(fig_flete, use_container_width=True)

        # ── Gráfico 2: Cantidad de viajes por mes, líneas por año ────────────
        df_viajes_trend = df_f.groupby(["AÑO", "MES_NUM"], as_index=False, observed=True).agg(
            Viajes=("VIAJESTOTALES", "sum"),
        )
        df_viajes_trend["Mes_Label"] = df_viajes_trend["MES_NUM"].map(MESES_NOMBRE)
        df_viajes_trend = df_viajes_trend.sort_values(["AÑO", "MES_NUM"])

        with col_chart2:
            fig_viajes = go.Figure()
            for año in sorted(df_viajes_trend["AÑO"].unique()):
                df_año = df_viajes_trend[df_viajes_trend["AÑO"] == año]
                color = YEAR_COLORS.get(str(año), COLORS["violet"])
                fig_viajes.add_trace(go.Scatter(
                    x=df_año["Mes_Label"], y=df_año["Viajes"],
                    name=str(año), mode="lines+markers+text",
                    text=[f"{v:,.0f}" for v in df_año["Viajes"]],
                    textposition="top center", textfont=dict(size=9, color=color),
                    line=dict(color=color, width=2), marker=dict(size=6),
                    hovertemplate=f"<b>{año} - %{{x}}</b><br>Viajes: %{{y:,.0f}}<extra></extra>",
                ))
            chart_layout(fig_viajes, "Cantidad de viajes", height=420)
            fig_viajes.update_layout(xaxis=dict(categoryorder="array",
                                                 categoryarray=list(MESES_NOMBRE.values())))
            st.plotly_chart(fig_viajes, use_container_width=True)

        st.divider()

        # ── Fila 2: Mercancía + Naturaleza + Config ──────────────────────────
        col_a, col_b, col_c = st.columns(3)

        with col_a:
            df_merc = df_f.groupby("MERCANCIA", as_index=False, observed=True)["TONELADAS"].sum()
            df_merc = df_merc.nlargest(10, "TONELADAS")
            fig_merc = px.bar(df_merc.sort_values("TONELADAS"), y="MERCANCIA", x="TONELADAS",
                              orientation="h", color_discrete_sequence=[COLORS["blue"]])
            fig_merc.update_traces(marker=dict(cornerradius=4),
                                    hovertemplate="<b>%{y}</b><br>Toneladas: %{x:,.0f}<extra></extra>")
            chart_layout(fig_merc, "Toneladas totales por Mercancía", height=380)
            st.plotly_chart(fig_merc, use_container_width=True)

        with col_b:
            df_nat = df_f.groupby("NATURALEZACARGA", as_index=False, observed=True)["VIAJESTOTALES"].sum()
            df_nat = df_nat.sort_values("VIAJESTOTALES", ascending=False)
            fig_nat = px.pie(df_nat, names="NATURALEZACARGA", values="VIAJESTOTALES",
                             color_discrete_sequence=CAT_COLORS, hole=0.4)
            fig_nat.update_traces(textposition="inside", textinfo="percent+label",
                                  hovertemplate="<b>%{label}</b><br>Viajes: %{value:,.0f}<br>%{percent}<extra></extra>",
                                  marker=dict(line=dict(color=SURFACE, width=2)))
            chart_layout(fig_nat, "Naturaleza de la carga", height=380)
            st.plotly_chart(fig_nat, use_container_width=True)

        with col_c:
            df_cfg = df_f.groupby("COD_CONFIG_VEHICULO", as_index=False, observed=True)["VIAJESTOTALES"].sum()
            df_cfg = df_cfg.nlargest(8, "VIAJESTOTALES")
            fig_cfg = px.pie(df_cfg, names="COD_CONFIG_VEHICULO", values="VIAJESTOTALES",
                             color_discrete_sequence=CAT_COLORS, hole=0.4)
            fig_cfg.update_traces(textposition="inside", textinfo="percent+label",
                                  hovertemplate="<b>%{label}</b><br>Viajes: %{value:,.0f}<br>%{percent}<extra></extra>",
                                  marker=dict(line=dict(color=SURFACE, width=2)))
            chart_layout(fig_cfg, "Configuración vehículo", height=380)
            st.plotly_chart(fig_cfg, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA 3: COMPARATIVO FLETES
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "💰 Comparativo FP y FM":
    st.title("Comparativo de Fletes")
    st.caption("Flete Mercado (Estadísticas RNDC) · Nuestro Flete (sin cargue ni descargue) · Tarifa SICETAC")

    has_fm = not df_stats.empty
    has_fp = not df_costos.empty
    has_sic = not df_sicetac.empty

    # Verificar que el archivo FP tenga las columnas de municipio
    fp_has_muni = (
        has_fp
        and "MUNICIPIO_ORIGEN" in df_costos.columns
        and "MUNICIPIO_DESTINO" in df_costos.columns
        and df_costos["MUNICIPIO_ORIGEN"].notna().any()
    )

    if not has_fm and not has_fp and not has_sic:
        st.warning("No se encontraron datos para la comparación.")
    else:
        if has_fp and not fp_has_muni:
            st.warning(
                "⚠️ El archivo de costos propios no tiene las columnas **MUNICIPIO_ORIGEN** y **MUNICIPIO_DESTINO**. "
                "Agrega estas columnas al Excel con el formato 'CIUDAD DEPARTAMENTO' (ej: SESQUILE CUNDINAMARCA) "
                "para poder cruzar con Estadísticas RNDC y SICETAC."
            )

        # ── Filtros de configuración, mercancía y naturaleza ────────────────
        col_fc1, col_fc2, col_fc3 = st.columns(3)

        with col_fc1:
            if has_fm:
                configs_comp = sorted(df_stats["COD_CONFIG_VEHICULO"].dropna().unique().tolist())
                configs_comp = [c for c in configs_comp if c.strip()]
                # Pre-seleccionar 3S3 si existe
                default_idx = configs_comp.index("3S3") + 1 if "3S3" in configs_comp else 0
            else:
                configs_comp = []
                default_idx = 0
            config_comp_sel = st.selectbox(
                "Configuración", ["Todos"] + configs_comp,
                index=default_idx, key="comp_config"
            )

        with col_fc2:
            if has_fm:
                mercancias_comp = sorted(df_stats["MERCANCIA"].dropna().unique().tolist())
            else:
                mercancias_comp = []
            mercancia_comp_sel = st.selectbox(
                "Mercancía", ["Todos"] + mercancias_comp, key="comp_merc"
            )

        with col_fc3:
            if has_fm:
                nat_comp_options = sorted(df_stats["NATURALEZACARGA"].dropna().unique().tolist())
                # Pre-seleccionar Carga Normal si existe
                nat_normal = [n for n in nat_comp_options if "NORMAL" in n.upper()]
                default_nat_idx = nat_comp_options.index(nat_normal[0]) + 1 if nat_normal else 0
            else:
                nat_comp_options = []
                default_nat_idx = 0
            nat_comp_sel = st.selectbox(
                "Naturaleza de la carga", ["Todos"] + nat_comp_options,
                index=default_nat_idx, key="comp_nat"
            )

        # ── Aplicar filtros base a Estadísticas ─────────────────────────────
        if has_fm:
            df_fm_base = df_stats.copy()
            if config_comp_sel != "Todos":
                df_fm_base = df_fm_base[df_fm_base["COD_CONFIG_VEHICULO"] == config_comp_sel]
            if mercancia_comp_sel != "Todos":
                df_fm_base = df_fm_base[df_fm_base["MERCANCIA"] == mercancia_comp_sel]
            if nat_comp_sel != "Todos":
                df_fm_base = df_fm_base[df_fm_base["NATURALEZACARGA"] == nat_comp_sel]
        else:
            df_fm_base = pd.DataFrame()

        # SICETAC: filtrar por config seleccionada
        if has_sic:
            df_sic_base = df_sicetac.copy()
            if config_comp_sel != "Todos":
                df_sic_base = df_sic_base[df_sic_base["CONFIGURACION"] == config_comp_sel]
        else:
            df_sic_base = pd.DataFrame()

        # ── Construir listas de municipios para filtros ──────────────────────
        muni_orig_set = set()
        muni_dest_set = set()

        if not df_fm_base.empty:
            muni_orig_set.update(df_fm_base["MUNICIPIOORIGEN"].dropna().unique())
            muni_dest_set.update(df_fm_base["MUNICIPIODESTINO"].dropna().unique())
        if has_sic and not df_sic_base.empty:
            muni_orig_set.update(df_sic_base["NOMORIGEN"].dropna().unique())
            muni_dest_set.update(df_sic_base["NOMDESTINO"].dropna().unique())
        if fp_has_muni:
            muni_orig_set.update(df_costos["MUNICIPIO_ORIGEN"].dropna().unique())
            muni_dest_set.update(df_costos["MUNICIPIO_DESTINO"].dropna().unique())

        # ── Filtros de municipio ─────────────────────────────────────────────
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            muni_orig_sel = st.selectbox(
                "Municipio origen", ["Todos"] + sorted(muni_orig_set), key="comp_orig"
            )
        with col_f2:
            if muni_orig_sel != "Todos":
                dest_set = set()
                if not df_fm_base.empty:
                    dest_set.update(
                        df_fm_base[df_fm_base["MUNICIPIOORIGEN"] == muni_orig_sel]["MUNICIPIODESTINO"]
                        .dropna().unique()
                    )
                if not df_sic_base.empty:
                    dest_set.update(
                        df_sic_base[df_sic_base["NOMORIGEN"] == muni_orig_sel]["NOMDESTINO"]
                        .dropna().unique()
                    )
                if fp_has_muni:
                    dest_set.update(
                        df_costos[df_costos["MUNICIPIO_ORIGEN"] == muni_orig_sel]["MUNICIPIO_DESTINO"]
                        .dropna().unique()
                    )
                muni_dest_options = sorted(dest_set)
            else:
                muni_dest_options = sorted(muni_dest_set)

            muni_dest_sel = st.selectbox(
                "Municipio destino", ["Todos"] + muni_dest_options, key="comp_dest"
            )

        st.divider()

        # ── Calcular Flete Mercado (Estadísticas RNDC) ───────────────────────
        # Flete promedio = VALORESPAGADOS / VIAJES_CON_VALOR
        # (viajes con valor = viajes totales - viajes valor cero)
        if not df_fm_base.empty:
            df_fm = df_fm_base.copy()
            if muni_orig_sel != "Todos":
                df_fm = df_fm[df_fm["MUNICIPIOORIGEN"] == muni_orig_sel]
            if muni_dest_sel != "Todos":
                df_fm = df_fm[df_fm["MUNICIPIODESTINO"] == muni_dest_sel]

            if not df_fm.empty:
                fm_agg = df_fm.groupby(
                    ["MES", "MUNICIPIOORIGEN", "MUNICIPIODESTINO"], as_index=False, observed=True
                ).agg(
                    VALOR=("VALORESPAGADOS", "sum"),
                    VIAJES_CV=("VIAJES_CON_VALOR", "sum"),
                )
                fm_agg["Flete Mercado"] = fm_agg["VALOR"] / fm_agg["VIAJES_CV"].replace(0, 1)
            else:
                fm_agg = pd.DataFrame()
        else:
            fm_agg = pd.DataFrame()

        # ── Calcular Nuestro Flete (FP sin cargue ni descargue) ──────────────
        if fp_has_muni and "Flete_sin_CyD" in df_costos.columns:
            df_fp = df_costos.copy()
            if muni_orig_sel != "Todos":
                df_fp = df_fp[df_fp["MUNICIPIO_ORIGEN"] == muni_orig_sel]
            if muni_dest_sel != "Todos":
                df_fp = df_fp[df_fp["MUNICIPIO_DESTINO"] == muni_dest_sel]

            if not df_fp.empty and "MES_FP" in df_fp.columns:
                fp_agg = df_fp.groupby(
                    ["MES_FP", "MUNICIPIO_ORIGEN", "MUNICIPIO_DESTINO"], as_index=False
                ).agg(**{"Nuestro Flete": ("Flete_sin_CyD", "mean")})
                fp_agg = fp_agg.rename(columns={
                    "MES_FP": "MES",
                    "MUNICIPIO_ORIGEN": "MUNICIPIOORIGEN",
                    "MUNICIPIO_DESTINO": "MUNICIPIODESTINO",
                })
            else:
                fp_agg = pd.DataFrame()
        else:
            fp_agg = pd.DataFrame()

        # ── Calcular Promedio SICETAC ────────────────────────────────────────
        if not df_sic_base.empty:
            df_sic = df_sic_base.copy()
            if muni_orig_sel != "Todos":
                df_sic = df_sic[df_sic["NOMORIGEN"] == muni_orig_sel]
            if muni_dest_sel != "Todos":
                df_sic = df_sic[df_sic["NOMDESTINO"] == muni_dest_sel]

            if not df_sic.empty:
                sic_agg = df_sic.groupby("PERIODO", as_index=False, observed=True).agg(
                    VALOR_SUMA=("VALOR_SUMA", "sum"), CONTEO=("CONTEO", "sum"),
                )
                sic_agg["SICETAC"] = sic_agg["VALOR_SUMA"] / sic_agg["CONTEO"].replace(0, 1)
                sic_agg = sic_agg.rename(columns={"PERIODO": "MES"})
            else:
                sic_agg = pd.DataFrame()
        else:
            sic_agg = pd.DataFrame()

        # ── Construir tabla comparativa ──────────────────────────────────────
        st.subheader("Comparativo de Fletes")

        # Base: usar periodos de todas las fuentes disponibles
        all_periodos = set()
        if not fm_agg.empty:
            all_periodos.update(fm_agg["MES"].unique())
        if not fp_agg.empty:
            all_periodos.update(fp_agg["MES"].unique())
        if not sic_agg.empty:
            all_periodos.update(sic_agg["MES"].unique())

        if not all_periodos:
            st.info("No hay datos para la combinación de filtros seleccionada. Selecciona un municipio de origen y destino.")
        else:
            tabla = pd.DataFrame({"MES": sorted(all_periodos)})

            # Agregar Flete Mercado
            if not fm_agg.empty:
                fm_por_mes = fm_agg.groupby("MES", as_index=False, observed=True).agg(
                    **{"Flete Mercado": ("Flete Mercado", "mean"),
                       "MUNICIPIOORIGEN": ("MUNICIPIOORIGEN", "first"),
                       "MUNICIPIODESTINO": ("MUNICIPIODESTINO", "first")}
                )
                tabla = tabla.merge(fm_por_mes[["MES", "Flete Mercado"]], on="MES", how="left")
            else:
                tabla["Flete Mercado"] = None

            # Agregar Nuestro Flete
            if not fp_agg.empty:
                fp_por_mes = fp_agg.groupby("MES", as_index=False, observed=True).agg(
                    **{"Nuestro Flete": ("Nuestro Flete", "mean")}
                )
                tabla = tabla.merge(fp_por_mes[["MES", "Nuestro Flete"]], on="MES", how="left")
            else:
                tabla["Nuestro Flete"] = None

            # Agregar SICETAC
            if not sic_agg.empty:
                tabla = tabla.merge(sic_agg[["MES", "SICETAC"]], on="MES", how="left")
            else:
                tabla["SICETAC"] = None

            tabla = tabla.sort_values("MES")

            # Formatear periodo para display
            tabla["Periodo"] = tabla["MES"].apply(
                lambda x: f"{MESES_NOMBRE.get(int(str(x)[4:6]), str(x)[4:6])} {str(x)[:4]}"
                if pd.notna(x) and len(str(x)) >= 6 else str(x)
            )

            # Origen/destino info
            ruta_label = ""
            if muni_orig_sel != "Todos" and muni_dest_sel != "Todos":
                ruta_label = f"**Ruta:** {muni_orig_sel} → {muni_dest_sel}"
            elif muni_orig_sel != "Todos":
                ruta_label = f"**Origen:** {muni_orig_sel}"
            elif muni_dest_sel != "Todos":
                ruta_label = f"**Destino:** {muni_dest_sel}"
            if ruta_label:
                st.markdown(ruta_label)

            # Tabla con total
            tabla_display = tabla[["Periodo", "Flete Mercado", "Nuestro Flete", "SICETAC"]].copy()

            total_dict = {"Periodo": "Promedio"}
            for col in ["Flete Mercado", "Nuestro Flete", "SICETAC"]:
                vals = tabla_display[col].dropna()
                total_dict[col] = vals.mean() if len(vals) > 0 else None
            tabla_con_total = pd.concat([tabla_display, pd.DataFrame([total_dict])], ignore_index=True)

            format_dict = {c: "${:,.0f}" for c in ["Flete Mercado", "Nuestro Flete", "SICETAC"]}

            col_tabla, col_chart = st.columns([1, 1])

            with col_tabla:
                st.dataframe(
                    tabla_con_total.style.format(format_dict, na_rep="-").apply(
                        lambda row: ["font-weight: bold"] * len(row)
                        if row["Periodo"] == "Promedio" else [""] * len(row),
                        axis=1,
                    ),
                    use_container_width=True, hide_index=True,
                    height=min(500, (len(tabla_con_total) + 1) * 38),
                )

            with col_chart:
                fig_comp = go.Figure()
                series_config = [
                    ("Flete Mercado", COLORS["red"], "Flete Mercado"),
                    ("Nuestro Flete", COLORS["blue"], "Nuestro Flete"),
                    ("SICETAC", COLORS["yellow"], "SICETAC"),
                ]
                for col, color, name in series_config:
                    if col in tabla.columns and tabla[col].notna().any():
                        df_line = tabla[tabla[col].notna()]
                        fig_comp.add_trace(go.Scatter(
                            x=df_line["Periodo"], y=df_line[col],
                            name=name, mode="lines+markers+text",
                            text=[f"${v:,.0f}" if pd.notna(v) else "" for v in df_line[col]],
                            textposition="top center", textfont=dict(size=9, color=color),
                            line=dict(color=color, width=2.5), marker=dict(size=8),
                            hovertemplate=f"<b>%{{x}}</b><br>{name}: $%{{y:,.0f}}<extra></extra>",
                        ))
                chart_layout(fig_comp, "Comparativo de Fletes por Mes", height=450)
                st.plotly_chart(fig_comp, use_container_width=True)

        st.divider()

        # ── Detalle de rutas con datos FP ────────────────────────────────────
        if fp_has_muni and "Flete_sin_CyD" in df_costos.columns:
            with st.expander("Detalle Nuestro Flete por Ruta"):
                df_fp_det = df_costos.copy()

                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    operaciones = ["Todos"] + sorted(df_fp_det["Operación"].dropna().unique().tolist())
                    op_sel = st.selectbox("Operación", operaciones, key="fp_op")
                with col_d2:
                    origenes_fp = ["Todos"] + sorted(df_fp_det["MUNICIPIO_ORIGEN"].dropna().unique().tolist())
                    orig_fp_sel = st.selectbox("Municipio Origen FP", origenes_fp, key="fp_muni_orig")

                if op_sel != "Todos":
                    df_fp_det = df_fp_det[df_fp_det["Operación"] == op_sel]
                if orig_fp_sel != "Todos":
                    df_fp_det = df_fp_det[df_fp_det["MUNICIPIO_ORIGEN"] == orig_fp_sel]

                col1, col2, col3 = st.columns(3)
                flete_sin_cyd_prom = df_fp_det["Flete_sin_CyD"].mean() if not df_fp_det.empty else 0
                flete_con_cyd_prom = df_fp_det["Flete Calculado carrocería"].mean() if "Flete Calculado carrocería" in df_fp_det.columns and not df_fp_det.empty else 0
                col1.metric("Rutas", f"{len(df_fp_det):,.0f}")
                col2.metric("Flete Prom. sin CyD", f"${flete_sin_cyd_prom:,.0f}")
                col3.metric("Flete Prom. con CyD", f"${flete_con_cyd_prom:,.0f}")

                # Tabla de rutas
                if not df_fp_det.empty:
                    df_rutas = df_fp_det.groupby(
                        ["MUNICIPIO_ORIGEN", "MUNICIPIO_DESTINO"], as_index=False
                    ).agg(
                        Rutas=("Flete_sin_CyD", "count"),
                        **{"Flete sin CyD": ("Flete_sin_CyD", "mean"),
                           "Flete con CyD": ("Flete Calculado carrocería", "mean")},
                    ).sort_values("Flete sin CyD", ascending=False)

                    st.dataframe(
                        df_rutas.style.format({
                            "Rutas": "{:,.0f}",
                            "Flete sin CyD": "${:,.0f}",
                            "Flete con CyD": "${:,.0f}",
                        }),
                        use_container_width=True, hide_index=True,
                        height=min(500, (len(df_rutas) + 1) * 38),
                    )


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA 4: TABLA CONSOLIDADA
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "📋 Tabla Consolidada":
    st.title("Tabla Consolidada")

    if df_filtrado.empty:
        st.warning("No hay datos para los filtros seleccionados.")
    else:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            configs_tc = ["Todos"] + sorted(df_filtrado["CONFIG_VEHICULO"].dropna().unique().tolist())
            config_tc_sel = st.selectbox("Configuración", configs_tc, key="tc_config")

        df_tc = df_filtrado.copy()
        if config_tc_sel != "Todos":
            df_tc = df_tc[df_tc["CONFIG_VEHICULO"] == config_tc_sel]

        df_consol = df_tc.groupby(["MES_NOMBRE", "PERIODO"], as_index=False, observed=True).agg(
            Viajes=("VIAJESTOTALES", "sum"),
            Viajes_con_valor=("VIAJES_CON_VALOR", "sum"),
            Flete_pagado=("VALORESPAGADOS", "sum"),
            Toneladas=("TONELADAS", "sum"),
        ).sort_values("PERIODO")

        df_consol["Flete Promedio"] = (df_consol["Flete_pagado"] / df_consol["Viajes_con_valor"].replace(0, 1)).round(0)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Viajes", f"{df_consol['Viajes'].sum():,.0f}")
        col2.metric("Viajes con Valor", f"{df_consol['Viajes_con_valor'].sum():,.0f}")
        col3.metric("Flete Pagado Total", f"${df_consol['Flete_pagado'].sum():,.0f}")
        col4.metric("Toneladas Total", f"{df_consol['Toneladas'].sum():,.0f}")

        st.divider()

        df_display = df_consol[["MES_NOMBRE", "Viajes", "Viajes_con_valor", "Flete_pagado", "Toneladas"]].copy()
        df_display.columns = ["Mes", "Viajes", "Viajes con Valor", "Flete Pagado", "Toneladas"]

        st.dataframe(
            df_display.style.format({
                "Viajes": "{:,.0f}", "Viajes con Valor": "{:,.0f}",
                "Flete Pagado": "${:,.0f}", "Toneladas": "{:,.0f}",
            }),
            use_container_width=True, height=400, hide_index=True,
        )

        fig_consol = go.Figure()
        fig_consol.add_trace(go.Bar(
            x=df_consol["MES_NOMBRE"], y=df_consol["Viajes"], name="Viajes",
            marker=dict(color=COLORS["blue"], cornerradius=4),
            hovertemplate="<b>%{x}</b><br>Viajes: %{y:,.0f}<extra></extra>",
        ))
        fig_consol.add_trace(go.Scatter(
            x=df_consol["MES_NOMBRE"], y=df_consol["Toneladas"], name="Toneladas",
            yaxis="y2", mode="lines+markers",
            line=dict(color=COLORS["orange"], width=2), marker=dict(size=8),
            hovertemplate="<b>%{x}</b><br>Toneladas: %{y:,.0f}<extra></extra>",
        ))
        fig_consol.update_layout(yaxis2=dict(
            overlaying="y", side="right", gridcolor="rgba(0,0,0,0)",
            tickfont=dict(color=COLORS["orange"]),
        ))
        chart_layout(fig_consol, "Viajes y Toneladas por Mes", height=420)
        st.plotly_chart(fig_consol, use_container_width=True)


# ─── Footer ──────────────────────────────────────────────────────────────────
st.sidebar.divider()
st.sidebar.caption("Datos: RNDC - Ministerio de Transporte")
st.sidebar.caption("Desarrollado para Edinsa")

with st.sidebar.expander("🔧 Diagnóstico"):
    data_dir = _get_data_dir()
    st.write(f"**Carpeta data:** `{data_dir}`")
    st.write(f"**Existe:** {os.path.isdir(data_dir)}")
    if os.path.isdir(data_dir):
        archivos = os.listdir(data_dir)
        st.write(f"**Archivos encontrados:** {len(archivos)}")
        for a in sorted(archivos):
            size_kb = os.path.getsize(os.path.join(data_dir, a)) / 1024
            st.write(f"- {a} ({size_kb:.0f} KB)")
    st.divider()
    st.write(f"**Estadísticas:** {df_stats.shape[0]} filas (pre-agregado)")
    st.write(f"**Ranking:** {df_ranking.shape[0]} filas")
    st.write(f"**SICETAC:** {df_sicetac.shape[0]} filas (pre-agregado)")
    st.write(f"**Costos FP:** {df_costos.shape[0]} filas")
    if _load_log:
        st.divider()
        st.write("**Log de carga:**")
        for msg in _load_log:
            st.write(f"- {msg}")
