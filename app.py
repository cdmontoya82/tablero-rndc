# Tablero RNDC - Edinsa
# Dashboard interactivo para estadisticas de transporte RNDC
# Version optimizada para Streamlit Cloud (pre-agregacion en 3 niveles)

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import glob
import os
import gc

# --- Columnas de pre-agregacion ---
# CORE: para paginas 2 y 4 (sin municipio ni mercancia)
CORE_AGG_COLS = [
    "MES", "CONFIG_VEHICULO", "COD_CONFIG_VEHICULO", "NATURALEZACARGA",
    "DEPARTAMENTOORIGEN", "DEPARTAMENTODESTINO",
]
# MERC: solo para el grafico de mercancia en pagina 2
MERC_AGG_COLS = ["MES", "MERCANCIA"]
# MUNI: para pagina 3 (comparativo)
MUNI_AGG_COLS = [
    "MES", "COD_CONFIG_VEHICULO", "NATURALEZACARGA",
    "CODMUNICIPIOORIGEN", "MUNICIPIOORIGEN",
    "CODMUNICIPIODESTINO", "MUNICIPIODESTINO",
]
SICETAC_COLUMNS = [
    "PERIODO", "ORIGEN", "NOMORIGEN", "DESTINO", "NOMDESTINO",
    "CONFIGURACION", "VALOR", "DISTANCIA",
]

# --- Configuracion de pagina ---
st.set_page_config(
    page_title="Tablero RNDC - Edinsa",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Paleta de colores ---
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
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}
MESES_CORTO = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
}

YEAR_COLORS = {
    "2024": COLORS["blue"],
    "2025": "#1a1a6e",
    "2026": COLORS["orange"],
}

# --- Estilos CSS ---
st.markdown(
    "<style>"
    '[data-testid="stMetric"]{background:#fcfcfb;border:1px solid #e1e0d9;border-radius:8px;padding:12px 16px}'
    '[data-testid="stMetricValue"]{font-size:1.8rem;font-weight:600;color:#0b0b0b}'
    '[data-testid="stMetricLabel"]{font-size:0.85rem;color:#52514e}'
    ".block-container{padding-top:1rem}"
    "h1,h2,h3{font-family:system-ui,-apple-system,'Segoe UI',sans-serif}"
    "</style>",
    unsafe_allow_html=True,
)


# --- Funciones auxiliares ---
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


# --- Carga de datos (3 niveles para Estadisticas) ---

@st.cache_data(ttl=3600)
def load_estadisticas():
    # Carga con pre-agregacion en 3 niveles para reducir memoria:
    # CORE (paginas 2, 4), MERC (grafico mercancia), MUNI (pagina 3)
    data_dir = _get_data_dir()
    all_files = sorted(glob.glob(os.path.join(data_dir, "EstadisticasRNDC_*.parquet")))
    all_files += sorted(glob.glob(os.path.join(data_dir, "EstadisticasRNDC_*.xlsx")))

    ALL_COLS = [
        "MES", "CONFIG_VEHICULO", "COD_CONFIG_VEHICULO", "NATURALEZACARGA",
        "MERCANCIA", "DEPARTAMENTOORIGEN", "DEPARTAMENTODESTINO",
        "CODMUNICIPIOORIGEN", "MUNICIPIOORIGEN",
        "CODMUNICIPIODESTINO", "MUNICIPIODESTINO",
        "VIAJESTOTALES", "KILOGRAMOS", "VALORESPAGADOS", "VIAJESVALORCERO",
    ]

    core_parts = []
    merc_parts = []
    muni_acc = None

    for idx, f in enumerate(all_files):
        try:
            if f.endswith(".parquet"):
                raw = pd.read_parquet(f, columns=ALL_COLS)
            else:
                raw = pd.read_excel(f, usecols=lambda c: c in ALL_COLS)

            _load_log.append(
                "OK: {} ({} filas)".format(os.path.basename(f), len(raw))
            )

            if "VIAJESVALORCERO" in raw.columns:
                raw["VIAJES_CON_VALOR"] = (
                    raw["VIAJESTOTALES"] - raw["VIAJESVALORCERO"].fillna(0)
                ).clip(lower=0).astype("int32")
            else:
                raw["VIAJES_CON_VALOR"] = raw["VIAJESTOTALES"]
            raw["TONELADAS"] = raw["KILOGRAMOS"] / 1000

            # CORE agg
            ac = raw.groupby(CORE_AGG_COLS, as_index=False, observed=True).agg(
                VIAJESTOTALES=("VIAJESTOTALES", "sum"),
                KILOGRAMOS=("KILOGRAMOS", "sum"),
                VALORESPAGADOS=("VALORESPAGADOS", "sum"),
                VIAJES_CON_VALOR=("VIAJES_CON_VALOR", "sum"),
                TONELADAS=("TONELADAS", "sum"),
            )
            _to_category(ac, CORE_AGG_COLS)
            for nc in ["VIAJESTOTALES", "KILOGRAMOS", "VIAJES_CON_VALOR"]:
                if nc in ac.columns:
                    ac[nc] = pd.to_numeric(ac[nc], downcast="integer")
            core_parts.append(ac)

            # MERC agg
            if "MERCANCIA" in raw.columns:
                am = raw.groupby(MERC_AGG_COLS, as_index=False, observed=True).agg(
                    TONELADAS=("TONELADAS", "sum"),
                    VIAJESTOTALES=("VIAJESTOTALES", "sum"),
                )
                _to_category(am, MERC_AGG_COLS)
                merc_parts.append(am)

            # MUNI agg (re-agregar cada 2 archivos para limitar pico de memoria)
            mu = raw.groupby(MUNI_AGG_COLS, as_index=False, observed=True).agg(
                VIAJESTOTALES=("VIAJESTOTALES", "sum"),
                VALORESPAGADOS=("VALORESPAGADOS", "sum"),
                VIAJES_CON_VALOR=("VIAJES_CON_VALOR", "sum"),
            )
            _to_category(mu, MUNI_AGG_COLS)

            if muni_acc is None:
                muni_acc = mu
            else:
                muni_acc = pd.concat([muni_acc, mu], ignore_index=True)
                if (idx + 1) % 2 == 0:
                    muni_acc = muni_acc.groupby(
                        MUNI_AGG_COLS, as_index=False, observed=True,
                    ).agg(
                        VIAJESTOTALES=("VIAJESTOTALES", "sum"),
                        VALORESPAGADOS=("VALORESPAGADOS", "sum"),
                        VIAJES_CON_VALOR=("VIAJES_CON_VALOR", "sum"),
                    )
                    _to_category(muni_acc, MUNI_AGG_COLS)

            del raw, mu
            gc.collect()

        except Exception as e:
            _load_log.append(
                "ERROR {}: {}".format(os.path.basename(f), e)
            )

    # Ensamblar DataFrames finales
    if not core_parts:
        _load_log.append("SIN DATOS: No se encontraron archivos EstadisticasRNDC")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    df_core = pd.concat(core_parts, ignore_index=True)
    del core_parts
    gc.collect()
    _to_category(df_core, CORE_AGG_COLS)

    df_merc = pd.DataFrame()
    if merc_parts:
        df_merc = pd.concat(merc_parts, ignore_index=True)
        del merc_parts
        gc.collect()
        _to_category(df_merc, MERC_AGG_COLS)

    if muni_acc is not None:
        muni_acc = muni_acc.groupby(
            MUNI_AGG_COLS, as_index=False, observed=True,
        ).agg(
            VIAJESTOTALES=("VIAJESTOTALES", "sum"),
            VALORESPAGADOS=("VALORESPAGADOS", "sum"),
            VIAJES_CON_VALOR=("VIAJES_CON_VALOR", "sum"),
        )
        _to_category(muni_acc, MUNI_AGG_COLS)
    else:
        muni_acc = pd.DataFrame()

    # Agregar columnas derivadas al core
    df_core["MES"] = df_core["MES"].astype(str)
    df_core["ANO"] = df_core["MES"].str[:4]
    df_core["MES_NUM"] = df_core["MES"].str[4:6].astype(int)
    df_core["PERIODO"] = pd.to_datetime(df_core["MES"], format="%Y%m")
    df_core["MES_NOMBRE"] = df_core["PERIODO"].dt.strftime("%b %Y")
    _to_category(df_core, CORE_AGG_COLS + ["ANO", "MES_NOMBRE"])

    # Agregar columnas derivadas al merc
    if not df_merc.empty:
        df_merc["MES"] = df_merc["MES"].astype(str)
        df_merc["ANO"] = df_merc["MES"].str[:4]
        df_merc["MES_NUM"] = df_merc["MES"].str[4:6].astype(int)
        _to_category(df_merc, MERC_AGG_COLS + ["ANO"])

    # Agregar columnas derivadas al muni
    if not muni_acc.empty:
        muni_acc["MES"] = muni_acc["MES"].astype(str)
        muni_acc["ANO"] = muni_acc["MES"].str[:4]
        muni_acc["MES_NUM"] = muni_acc["MES"].str[4:6].astype(int)

    _load_log.append(
        "Estadisticas final: core={}, merc={}, muni={} filas".format(
            len(df_core), len(df_merc), len(muni_acc)
        )
    )
    return df_core, df_merc, muni_acc


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
                _load_log.append(
                    "OK ranking: {} ({} filas)".format(basename, len(df))
                )
        except Exception as e:
            _load_log.append("ERROR ranking {}: {}".format(basename, e))

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

    all_files = sorted(glob.glob(os.path.join(data_dir, "Sicetac_*.parquet")))
    all_files += sorted(glob.glob(os.path.join(data_dir, "Sicetac_*.xlsx")))

    for f in all_files:
        try:
            if f.endswith(".parquet"):
                raw = pd.read_parquet(f, columns=SICETAC_COLUMNS)
            else:
                raw = pd.read_excel(f, usecols=lambda c: c in SICETAC_COLUMNS)

            _load_log.append(
                "OK sicetac: {} ({} filas)".format(os.path.basename(f), len(raw))
            )

            raw["PERIODO"] = raw["PERIODO"].astype(str).str[:6]
            for dcol in ["ORIGEN", "DESTINO"]:
                if dcol in raw.columns:
                    raw[dcol] = pd.to_numeric(
                        raw[dcol], errors="coerce"
                    ).fillna(0).astype("int64")

            agg = raw.groupby(
                ["PERIODO", "CONFIGURACION", "ORIGEN", "NOMORIGEN",
                 "DESTINO", "NOMDESTINO"],
                as_index=False, observed=True,
            ).agg(
                VALOR_SUMA=("VALOR", "sum"),
                DISTANCIA_SUMA=("DISTANCIA", "sum"),
                CONTEO=("VALOR", "count"),
            )
            _to_category(
                agg, ["PERIODO", "CONFIGURACION", "NOMORIGEN", "NOMDESTINO"]
            )
            agg_frames.append(agg)
            del raw
            gc.collect()

        except Exception as e:
            _load_log.append(
                "ERROR sicetac {}: {}".format(os.path.basename(f), e)
            )

    if not agg_frames:
        _load_log.append("SIN DATOS: No se encontraron archivos SICETAC")
        return pd.DataFrame()

    df = pd.concat(agg_frames, ignore_index=True)
    del agg_frames
    gc.collect()

    df = df.groupby(
        ["PERIODO", "CONFIGURACION", "ORIGEN", "NOMORIGEN",
         "DESTINO", "NOMDESTINO"],
        as_index=False, observed=True,
    ).agg(
        VALOR_SUMA=("VALOR_SUMA", "sum"),
        DISTANCIA_SUMA=("DISTANCIA_SUMA", "sum"),
        CONTEO=("CONTEO", "sum"),
    )
    df["VALOR"] = df["VALOR_SUMA"] / df["CONTEO"]
    df["DISTANCIA"] = df["DISTANCIA_SUMA"] / df["CONTEO"]

    _to_category(df, ["PERIODO", "CONFIGURACION", "NOMORIGEN", "NOMDESTINO"])
    _load_log.append(
        "SICETAC final: {} filas pre-agregadas".format(len(df))
    )
    return df


@st.cache_data(ttl=3600)
def load_costos_fp():
    # Carga archivos Costo_fp_sinCYD_*.xlsx (un archivo por mes).
    data_dir = _get_data_dir()
    frames = []

    new_files = sorted(
        glob.glob(os.path.join(data_dir, "Costo_fp_sinCYD_*.xlsx"))
    )
    if new_files:
        all_files = new_files
        _load_log.append(
            "FP: usando {} archivos formato nuevo".format(len(new_files))
        )
    else:
        all_files = sorted(
            glob.glob(os.path.join(data_dir, "Costo ruta flota propia*.xlsx"))
        )
        _load_log.append(
            "FP: usando {} archivos formato anterior".format(len(all_files))
        )

    COL_MAP = {
        "fecha": ["fecha"],
        "centro_orig": ["centro origen"],
        "centro_dest": ["centro destino"],
        "cod_muni_o": ["municio origen", "municipio origen"],
        "cod_muni_d": ["municipio destino"],
        "config": ["configuracion", "configuración"],
        "naturaleza": ["naturaleza"],
        "costo": ["costo sin cyd", "costo sin c y d"],
    }

    def _find_col(actual_cols, patterns):
        lower_map = {c.strip().lower(): c for c in actual_cols}
        for pat in patterns:
            if pat in lower_map:
                return lower_map[pat]
        return None

    for f in all_files:
        try:
            raw = pd.read_excel(f)
            _load_log.append(
                "OK costos: {} ({} filas, cols: {})".format(
                    os.path.basename(f), len(raw), list(raw.columns[:10])
                )
            )

            rename = {}
            for internal, pats in COL_MAP.items():
                found = _find_col(raw.columns, pats)
                if found:
                    rename[found] = internal

            raw = raw.rename(columns=rename)
            frames.append(raw)
            del raw
        except Exception as e:
            _load_log.append(
                "ERROR costos {}: {}".format(os.path.basename(f), e)
            )

    if not frames:
        _load_log.append("SIN DATOS: No se encontraron archivos de costos FP")
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    del frames
    gc.collect()

    df = df.drop_duplicates()

    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
        df["MES_FP"] = df["fecha"].dt.strftime("%Y%m")

    for col in ["cod_muni_o", "cod_muni_d"]:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col], errors="coerce"
            ).fillna(0).astype("int64")

    if "costo" in df.columns:
        df["Flete_sin_CyD"] = pd.to_numeric(df["costo"], errors="coerce")
        if (
            df["Flete_sin_CyD"].isna().sum() > df["Flete_sin_CyD"].notna().sum()
            and df["costo"].notna().any()
        ):
            df["Flete_sin_CyD"] = pd.to_numeric(
                df["costo"].astype(str)
                .str.replace(".", "", regex=False)
                .str.replace(",", ".", regex=False),
                errors="coerce",
            )

    if "Flete_sin_CyD" not in df.columns or df["Flete_sin_CyD"].isna().all():
        flete_col = _find_col(
            df.columns,
            ["flete calculado carrocería", "flete calculado carroceria"],
        )
        cargue_col = _find_col(df.columns, ["costo cargue"])
        descargue_col = _find_col(df.columns, ["costo descargue"])
        if flete_col:
            df["Flete_sin_CyD"] = (
                df[flete_col]
                - (df[cargue_col].fillna(0) if cargue_col else 0)
                - (df[descargue_col].fillna(0) if descargue_col else 0)
            )

    rename_final = {
        "cod_muni_o": "COD_MUNI_ORIG",
        "cod_muni_d": "COD_MUNI_DEST",
        "config": "CONFIG_FP",
        "naturaleza": "NATURALEZA_FP",
    }
    df = df.rename(
        columns={k: v for k, v in rename_final.items() if k in df.columns}
    )

    _load_log.append(
        "FP final: {} filas, cols internas: COD_MUNI_ORIG={}, "
        "Flete_sin_CyD={}, MES_FP={}".format(
            len(df),
            "COD_MUNI_ORIG" in df.columns,
            "Flete_sin_CyD" in df.columns and df["Flete_sin_CyD"].notna().any(),
            "MES_FP" in df.columns,
        )
    )
    return df


# --- Layout de graficos Plotly ---
def chart_layout(fig, title="", height=400):
    fig.update_layout(
        title=dict(
            text=title,
            font=dict(size=16, color=TEXT_PRIMARY, family="system-ui, sans-serif"),
        ),
        plot_bgcolor=SURFACE,
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(
            family="system-ui, -apple-system, 'Segoe UI', sans-serif",
            color=TEXT_SECONDARY, size=12,
        ),
        height=height,
        margin=dict(l=40, r=20, t=50, b=40),
        xaxis=dict(
            gridcolor=GRIDLINE, linecolor=BASELINE,
            zerolinecolor=BASELINE, tickfont=dict(color=TEXT_SECONDARY),
        ),
        yaxis=dict(
            gridcolor=GRIDLINE, linecolor=BASELINE,
            zerolinecolor=BASELINE, tickfont=dict(color=TEXT_SECONDARY),
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(color=TEXT_SECONDARY, size=11),
        ),
        hoverlabel=dict(
            bgcolor="white", font_size=12,
            font_family="system-ui, sans-serif",
        ),
    )
    return fig


# --- Cargar todos los datasets ---
try:
    df_core, df_merc, df_muni = load_estadisticas()
except Exception as e:
    st.error("Error cargando Estadisticas: {}".format(e))
    df_core = pd.DataFrame()
    df_merc = pd.DataFrame()
    df_muni = pd.DataFrame()

try:
    df_ranking = load_ranking()
except Exception as e:
    st.error("Error cargando Ranking: {}".format(e))
    df_ranking = pd.DataFrame()

try:
    df_sicetac = load_sicetac()
except Exception as e:
    st.error("Error cargando SICETAC: {}".format(e))
    df_sicetac = pd.DataFrame()

try:
    df_costos = load_costos_fp()
except Exception as e:
    st.error("Error cargando Costos FP: {}".format(e))
    df_costos = pd.DataFrame()

gc.collect()

# --- Sidebar ---
st.sidebar.title("🚛 Tablero RNDC")
st.sidebar.caption("Edinsa - Estadisticas de transporte")

pagina = st.sidebar.radio(
    "Navegacion",
    [
        "📊 Ranking Empresa",
        "📦 Estadisticas de Carga",
        "💰 Comparativo FP y FM",
        "📋 Tabla Consolidada",
    ],
    label_visibility="collapsed",
)

st.sidebar.divider()

# --- Filtros globales (para paginas 2 y 4) ---
if not df_core.empty:
    anos_disponibles = sorted(df_core["ANO"].unique())
    ano_sel = st.sidebar.multiselect(
        "Ano", anos_disponibles, default=anos_disponibles
    )

    meses_disponibles = sorted(
        df_core[df_core["ANO"].isin(ano_sel)]["MES_NUM"].unique()
    )
    mes_sel = st.sidebar.multiselect(
        "Mes", meses_disponibles, default=meses_disponibles,
        format_func=lambda x: MESES_CORTO.get(x, str(x)),
    )

    mask = df_core["ANO"].isin(ano_sel) & df_core["MES_NUM"].isin(mes_sel)
    df_filtrado = df_core[mask].copy()

    # Filtro equivalente para merc
    if not df_merc.empty:
        mask_merc = df_merc["ANO"].isin(ano_sel) & df_merc["MES_NUM"].isin(mes_sel)
        df_merc_filtrado = df_merc[mask_merc].copy()
    else:
        df_merc_filtrado = pd.DataFrame()
else:
    df_filtrado = df_core
    df_merc_filtrado = df_merc
    ano_sel = []
    mes_sel = []


# -- Constantes EDINSA --
EDINSA_NAME = "EMPRESA DE DISTRIBUCIONES INDUSTRIALES S.A."
EDINSA_COLOR = COLORS["orange"]
OTHER_COLOR = COLORS["blue"]

# ======================================================================
# PAGINA 1: RANKING EMPRESA
# ======================================================================
if pagina == "📊 Ranking Empresa":
    st.title("Ranking Empresa RNDC")

    if df_ranking.empty:
        st.warning("No se encontro el archivo de ranking de empresas.")
    else:
        df_rank = df_ranking.copy()
        df_rank = df_rank.dropna(subset=["Nombre Empresa"])
        df_rank["Nombre Empresa"] = df_rank["Nombre Empresa"].str.strip()
        df_rank["Toneladas"] = pd.to_numeric(
            df_rank["Toneladas"], errors="coerce"
        ).fillna(0)
        df_rank["Manifiestos Radicados"] = pd.to_numeric(
            df_rank["Manifiestos Radicados"], errors="coerce"
        ).fillna(0)

        if "Date" in df_rank.columns:
            df_rank["Date"] = pd.to_datetime(df_rank["Date"], errors="coerce")
            df_rank["Mes_Num"] = df_rank["Date"].dt.month
            df_rank["Ano"] = df_rank["Date"].dt.year
            df_rank["Mes_Nombre"] = df_rank["Mes_Num"].map(MESES_NOMBRE)

        if "Ano" in df_rank.columns:
            anos_rank = sorted(
                df_rank["Ano"].dropna().unique().astype(int)
            )
            ano_rank_sel = st.sidebar.multiselect(
                "Ano (Ranking)", anos_rank, default=anos_rank, key="rank_ano"
            )
            df_rank = df_rank[df_rank["Ano"].isin(ano_rank_sel)]

        total_empresas = df_rank["Nombre Empresa"].nunique()
        total_tons = df_rank["Toneladas"].sum()

        df_edinsa = df_rank[
            df_rank["Nombre Empresa"].str.contains(
                "DISTRIBUCIONES INDUSTRIALES", case=False, na=False
            )
        ]
        tons_edinsa = df_edinsa["Toneladas"].sum()
        pct_edinsa = (
            (tons_edinsa / total_tons * 100) if total_tons > 0 else 0
        )

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Empresas", "{:,.0f}".format(total_empresas))
        col2.metric("Tons Totales Mercado", "{:,.0f}".format(total_tons))
        col3.metric("Tons EDINSA", "{:,.0f}".format(tons_edinsa))
        col4.metric("% Participacion EDINSA", "{:.1f} %".format(pct_edinsa))

        st.divider()

        if "Mes_Nombre" in df_rank.columns and not df_edinsa.empty:
            st.subheader("% de Tons transportadas por EDINSA en Colombia")

            tons_mes_total = df_rank.groupby(
                ["Mes_Num", "Mes_Nombre"], as_index=False
            )["Toneladas"].sum()
            tons_mes_total.columns = ["Mes_Num", "Mes", "Tons Empresa"]
            tons_mes_edinsa = df_edinsa.groupby(
                ["Mes_Num", "Mes_Nombre"], as_index=False
            )["Toneladas"].sum()
            tons_mes_edinsa.columns = ["Mes_Num", "Mes", "Tons EDINSA"]

            df_participacion = tons_mes_total.merge(
                tons_mes_edinsa, on=["Mes_Num", "Mes"], how="left"
            )
            df_participacion["Tons EDINSA"] = df_participacion[
                "Tons EDINSA"
            ].fillna(0)
            df_participacion["% participacion tons EDINSA"] = (
                df_participacion["Tons EDINSA"]
                / df_participacion["Tons Empresa"]
                * 100
            ).round(1)
            df_participacion = df_participacion.sort_values("Mes_Num")

            total_row = pd.DataFrame(
                [
                    {
                        "Mes_Num": 99,
                        "Mes": "Total",
                        "Tons EDINSA": df_participacion["Tons EDINSA"].sum(),
                        "Tons Empresa": df_participacion["Tons Empresa"].sum(),
                        "% participacion tons EDINSA": round(
                            df_participacion["Tons EDINSA"].sum()
                            / df_participacion["Tons Empresa"].sum()
                            * 100,
                            1,
                        )
                        if df_participacion["Tons Empresa"].sum() > 0
                        else 0,
                    }
                ]
            )
            df_participacion = pd.concat(
                [df_participacion, total_row], ignore_index=True
            )

            df_show_part = df_participacion[
                ["Mes", "Tons EDINSA", "Tons Empresa", "% participacion tons EDINSA"]
            ].copy()
            st.dataframe(
                df_show_part.style.format(
                    {
                        "Tons EDINSA": "{:,.0f}",
                        "Tons Empresa": "{:,.0f}",
                        "% participacion tons EDINSA": "{:.1f} %",
                    }
                ).apply(
                    lambda row: ["font-weight: bold"] * len(row)
                    if row["Mes"] == "Total"
                    else [""] * len(row),
                    axis=1,
                ),
                width="stretch",
                hide_index=True,
                height=min(400, (len(df_participacion) + 1) * 38),
            )

            df_part_chart = df_participacion[
                df_participacion["Mes"] != "Total"
            ].copy()
            fig_part = go.Figure()
            fig_part.add_trace(
                go.Bar(
                    x=df_part_chart["Mes"],
                    y=df_part_chart["Tons EDINSA"],
                    name="Tons EDINSA",
                    marker=dict(color=EDINSA_COLOR, cornerradius=4),
                    hovertemplate=(
                        "<b>%{x}</b><br>Tons EDINSA: %{y:,.0f}<extra></extra>"
                    ),
                )
            )
            fig_part.add_trace(
                go.Scatter(
                    x=df_part_chart["Mes"],
                    y=df_part_chart["% participacion tons EDINSA"],
                    name="% Participacion",
                    mode="lines+markers+text",
                    text=[
                        "{:.1f}%".format(v)
                        for v in df_part_chart["% participacion tons EDINSA"]
                    ],
                    textposition="top center",
                    textfont=dict(color=TEXT_SECONDARY, size=11),
                    line=dict(color=COLORS["aqua"], width=2),
                    marker=dict(size=8),
                    hovertemplate=(
                        "<b>%{x}</b><br>Participacion: %{y:.1f}%<extra></extra>"
                    ),
                    yaxis="y2",
                )
            )
            fig_part.update_layout(
                yaxis2=dict(
                    overlaying="y",
                    side="right",
                    gridcolor="rgba(0,0,0,0)",
                    tickfont=dict(color=COLORS["aqua"]),
                    ticksuffix="%",
                    range=[
                        0,
                        max(
                            df_part_chart[
                                "% participacion tons EDINSA"
                            ].max()
                            * 2,
                            5,
                        ),
                    ],
                )
            )
            chart_layout(
                fig_part,
                "Toneladas EDINSA y % Participacion por Mes",
                height=380,
            )
            st.plotly_chart(fig_part, width="stretch")

        st.divider()

        top_n = st.slider("Top empresas a mostrar", 10, 50, 20)
        df_rank_agg = df_rank.groupby(
            "Nombre Empresa", as_index=False
        ).agg(
            Toneladas=("Toneladas", "sum"),
            Manifiestos=("Manifiestos Radicados", "sum"),
        )
        df_top = df_rank_agg.nlargest(top_n, "Toneladas").sort_values(
            "Toneladas"
        )
        df_top["es_edinsa"] = df_top["Nombre Empresa"].str.contains(
            "DISTRIBUCIONES INDUSTRIALES", case=False, na=False
        )
        bar_colors = [
            EDINSA_COLOR if es else OTHER_COLOR
            for es in df_top["es_edinsa"]
        ]

        fig_bar = go.Figure(
            go.Bar(
                y=df_top["Nombre Empresa"],
                x=df_top["Toneladas"],
                orientation="h",
                marker=dict(color=bar_colors, cornerradius=4),
                hovertemplate=(
                    "<b>%{y}</b><br>Toneladas: %{x:,.0f}<extra></extra>"
                ),
            )
        )
        chart_layout(
            fig_bar,
            "Top {} Empresas por Toneladas".format(top_n),
            height=max(400, top_n * 28),
        )
        st.plotly_chart(fig_bar, width="stretch")

        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Tabla por Empresa")
            df_tabla = df_rank_agg[
                ["Nombre Empresa", "Manifiestos", "Toneladas"]
            ].copy()
            df_tabla["% Participacion"] = (
                df_tabla["Toneladas"] / df_tabla["Toneladas"].sum() * 100
            ).round(2)
            df_tabla = df_tabla.sort_values(
                "Toneladas", ascending=False
            ).reset_index(drop=True)
            df_tabla.index += 1

            def highlight_edinsa(row):
                if "DISTRIBUCIONES INDUSTRIALES" in str(
                    row["Nombre Empresa"]
                ).upper():
                    return [
                        "background-color: {}22; font-weight: bold; color: {}".format(
                            EDINSA_COLOR, EDINSA_COLOR
                        )
                    ] * len(row)
                return [""] * len(row)

            st.dataframe(
                df_tabla.style.apply(highlight_edinsa, axis=1).format(
                    {
                        "Manifiestos": "{:,.0f}",
                        "Toneladas": "{:,.0f}",
                        "% Participacion": "{:.2f} %",
                    }
                ),
                width="stretch",
                height=500,
            )

        with col_b:
            st.subheader("Manifiestos vs Toneladas")
            df_top_scatter = df_rank_agg.nlargest(top_n, "Toneladas")
            df_top_scatter["es_edinsa"] = df_top_scatter[
                "Nombre Empresa"
            ].str.contains(
                "DISTRIBUCIONES INDUSTRIALES", case=False, na=False
            )
            df_other = df_top_scatter[~df_top_scatter["es_edinsa"]]
            df_ed = df_top_scatter[df_top_scatter["es_edinsa"]]

            fig_scatter = go.Figure()
            fig_scatter.add_trace(
                go.Scatter(
                    x=df_other["Manifiestos"],
                    y=df_other["Toneladas"],
                    mode="markers",
                    name="Otras empresas",
                    text=df_other["Nombre Empresa"],
                    marker=dict(
                        color=OTHER_COLOR, size=10,
                        line=dict(width=1, color="white"),
                    ),
                    hovertemplate=(
                        "<b>%{text}</b><br>Manifiestos: %{x:,.0f}"
                        "<br>Toneladas: %{y:,.0f}<extra></extra>"
                    ),
                )
            )
            if not df_ed.empty:
                fig_scatter.add_trace(
                    go.Scatter(
                        x=df_ed["Manifiestos"],
                        y=df_ed["Toneladas"],
                        mode="markers+text",
                        name="EDINSA",
                        text=["EDINSA"],
                        textposition="top center",
                        textfont=dict(
                            color=EDINSA_COLOR, size=12,
                            family="system-ui, sans-serif",
                        ),
                        marker=dict(
                            color=EDINSA_COLOR, size=16,
                            line=dict(width=2, color="white"),
                            symbol="diamond",
                        ),
                        hovertemplate=(
                            "<b>EDINSA</b><br>Manifiestos: %{x:,.0f}"
                            "<br>Toneladas: %{y:,.0f}<extra></extra>"
                        ),
                    )
                )
            chart_layout(
                fig_scatter, "Relacion Manifiestos vs Toneladas", height=500
            )
            st.plotly_chart(fig_scatter, width="stretch")


# ======================================================================
# PAGINA 2: ESTADISTICAS DE CARGA
# ======================================================================
elif pagina == "📦 Estadisticas de Carga":
    st.title("Estadisticas de Carga")

    if df_filtrado.empty:
        st.warning("No hay datos para los filtros seleccionados.")
    else:
        # -- Filtros --
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        with col_f1:
            configs_cod = sorted(
                df_filtrado["COD_CONFIG_VEHICULO"].dropna().unique().tolist()
            )
            configs_cod = [c for c in configs_cod if c.strip()]
            config_sel = st.selectbox(
                "Configuracion", ["Todos"] + configs_cod, key="est_config"
            )
        with col_f2:
            if not df_merc_filtrado.empty:
                mercancias = ["Todos"] + sorted(
                    df_merc_filtrado["MERCANCIA"].dropna().unique().tolist()
                )
            else:
                mercancias = ["Todos"]
            mercancia_sel = st.selectbox(
                "Mercancia", mercancias, key="est_merc"
            )
        with col_f3:
            deptos_orig = ["Todos"] + sorted(
                df_filtrado["DEPARTAMENTOORIGEN"].dropna().unique().tolist()
            )
            depto_orig_sel = st.selectbox(
                "Departamento origen", deptos_orig, key="est_depto_o"
            )
        with col_f4:
            deptos_dest = ["Todos"] + sorted(
                df_filtrado["DEPARTAMENTODESTINO"].dropna().unique().tolist()
            )
            depto_dest_sel = st.selectbox(
                "Departamento destino", deptos_dest, key="est_depto_d"
            )

        col_f5, _, _, _ = st.columns(4)
        with col_f5:
            nat_options = ["Todos"] + sorted(
                df_filtrado["NATURALEZACARGA"].dropna().unique().tolist()
            )
            nat_sel = st.selectbox(
                "Naturaleza de la carga", nat_options, key="est_nat"
            )

        # Aplicar filtros al core
        df_f = df_filtrado.copy()
        if config_sel != "Todos":
            df_f = df_f[df_f["COD_CONFIG_VEHICULO"] == config_sel]
        if depto_orig_sel != "Todos":
            df_f = df_f[df_f["DEPARTAMENTOORIGEN"] == depto_orig_sel]
        if depto_dest_sel != "Todos":
            df_f = df_f[df_f["DEPARTAMENTODESTINO"] == depto_dest_sel]
        if nat_sel != "Todos":
            df_f = df_f[df_f["NATURALEZACARGA"] == nat_sel]

        # Aplicar filtros al merc (solo config y naturaleza aplican)
        df_mf = df_merc_filtrado.copy() if not df_merc_filtrado.empty else pd.DataFrame()
        if not df_mf.empty and mercancia_sel != "Todos":
            df_mf = df_mf[df_mf["MERCANCIA"] == mercancia_sel]

        # -- KPIs --
        total_viajes = df_f["VIAJESTOTALES"].sum()
        total_tons = df_f["TONELADAS"].sum()
        total_flete = df_f["VALORESPAGADOS"].sum()
        viajes_con_valor = df_f["VIAJES_CON_VALOR"].sum()
        flete_prom = total_flete / max(viajes_con_valor, 1)

        df_prom_mes = df_f.groupby("MES", observed=True).agg(
            V=("VALORESPAGADOS", "sum"), VC=("VIAJES_CON_VALOR", "sum"),
        )
        df_prom_mes["prom"] = df_prom_mes["V"] / df_prom_mes["VC"].replace(0, 1)
        flete_prom_mensual = (
            df_prom_mes["prom"].mean() if len(df_prom_mes) > 0 else 0
        )

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Viajes", "{:,.0f}".format(total_viajes))
        col2.metric("Toneladas totales", "{:,.0f}".format(total_tons))
        col3.metric("Flete promedio", "${:,.0f}".format(flete_prom))
        col4.metric(
            "Flete promedio mes", "${:,.0f}".format(flete_prom_mensual)
        )

        st.divider()

        # -- Grafico 1: Flete promedio por mes --
        df_flete_trend = df_f.groupby(
            ["ANO", "MES_NUM"], as_index=False, observed=True,
        ).agg(
            VALORESPAGADOS=("VALORESPAGADOS", "sum"),
            VIAJES_CON_VALOR=("VIAJES_CON_VALOR", "sum"),
        )
        df_flete_trend["Flete_Prom"] = (
            df_flete_trend["VALORESPAGADOS"]
            / df_flete_trend["VIAJES_CON_VALOR"].replace(0, 1)
        )
        df_flete_trend["Mes_Label"] = df_flete_trend["MES_NUM"].map(
            MESES_NOMBRE
        )
        df_flete_trend = df_flete_trend.sort_values(["ANO", "MES_NUM"])

        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            fig_flete = go.Figure()
            for ano in sorted(df_flete_trend["ANO"].unique()):
                df_ano = df_flete_trend[df_flete_trend["ANO"] == ano]
                color = YEAR_COLORS.get(str(ano), COLORS["violet"])
                fig_flete.add_trace(
                    go.Scatter(
                        x=df_ano["Mes_Label"],
                        y=df_ano["Flete_Prom"],
                        name=str(ano),
                        mode="lines+markers+text",
                        text=[
                            "{:,.0f}".format(v) for v in df_ano["Flete_Prom"]
                        ],
                        textposition="top center",
                        textfont=dict(size=9, color=color),
                        line=dict(color=color, width=2),
                        marker=dict(size=6),
                        hovertemplate=(
                            "<b>{} - %{{x}}</b><br>"
                            "Flete Prom: $%{{y:,.0f}}<extra></extra>".format(ano)
                        ),
                    )
                )
            chart_layout(fig_flete, "Flete promedio", height=420)
            fig_flete.update_layout(
                xaxis=dict(
                    categoryorder="array",
                    categoryarray=list(MESES_NOMBRE.values()),
                )
            )
            st.plotly_chart(fig_flete, width="stretch")

        # -- Grafico 2: Cantidad de viajes por mes --
        df_viajes_trend = df_f.groupby(
            ["ANO", "MES_NUM"], as_index=False, observed=True,
        ).agg(Viajes=("VIAJESTOTALES", "sum"))
        df_viajes_trend["Mes_Label"] = df_viajes_trend["MES_NUM"].map(
            MESES_NOMBRE
        )
        df_viajes_trend = df_viajes_trend.sort_values(["ANO", "MES_NUM"])

        with col_chart2:
            fig_viajes = go.Figure()
            for ano in sorted(df_viajes_trend["ANO"].unique()):
                df_ano = df_viajes_trend[df_viajes_trend["ANO"] == ano]
                color = YEAR_COLORS.get(str(ano), COLORS["violet"])
                fig_viajes.add_trace(
                    go.Scatter(
                        x=df_ano["Mes_Label"],
                        y=df_ano["Viajes"],
                        name=str(ano),
                        mode="lines+markers+text",
                        text=[
                            "{:,.0f}".format(v) for v in df_ano["Viajes"]
                        ],
                        textposition="top center",
                        textfont=dict(size=9, color=color),
                        line=dict(color=color, width=2),
                        marker=dict(size=6),
                        hovertemplate=(
                            "<b>{} - %{{x}}</b><br>"
                            "Viajes: %{{y:,.0f}}<extra></extra>".format(ano)
                        ),
                    )
                )
            chart_layout(fig_viajes, "Cantidad de viajes", height=420)
            fig_viajes.update_layout(
                xaxis=dict(
                    categoryorder="array",
                    categoryarray=list(MESES_NOMBRE.values()),
                )
            )
            st.plotly_chart(fig_viajes, width="stretch")

        st.divider()

        # -- Fila 2: Mercancia + Naturaleza + Config --
        col_a, col_b, col_c = st.columns(3)

        with col_a:
            if not df_mf.empty:
                df_merc_chart = df_mf.groupby(
                    "MERCANCIA", as_index=False, observed=True,
                )["TONELADAS"].sum()
                df_merc_chart = df_merc_chart.nlargest(10, "TONELADAS")
                fig_merc = px.bar(
                    df_merc_chart.sort_values("TONELADAS"),
                    y="MERCANCIA", x="TONELADAS", orientation="h",
                    color_discrete_sequence=[COLORS["blue"]],
                )
                fig_merc.update_traces(
                    marker=dict(cornerradius=4),
                    hovertemplate=(
                        "<b>%{y}</b><br>Toneladas: %{x:,.0f}<extra></extra>"
                    ),
                )
                chart_layout(
                    fig_merc, "Toneladas totales por Mercancia", height=380
                )
                st.plotly_chart(fig_merc, width="stretch")
            else:
                st.info("Sin datos de mercancia para los filtros seleccionados.")

        with col_b:
            df_nat = df_f.groupby(
                "NATURALEZACARGA", as_index=False, observed=True,
            )["VIAJESTOTALES"].sum()
            df_nat = df_nat.sort_values("VIAJESTOTALES", ascending=False)
            fig_nat = px.pie(
                df_nat, names="NATURALEZACARGA", values="VIAJESTOTALES",
                color_discrete_sequence=CAT_COLORS, hole=0.4,
            )
            fig_nat.update_traces(
                textposition="inside", textinfo="percent+label",
                hovertemplate=(
                    "<b>%{label}</b><br>Viajes: %{value:,.0f}"
                    "<br>%{percent}<extra></extra>"
                ),
                marker=dict(line=dict(color=SURFACE, width=2)),
            )
            chart_layout(fig_nat, "Naturaleza de la carga", height=380)
            st.plotly_chart(fig_nat, width="stretch")

        with col_c:
            df_cfg = df_f.groupby(
                "COD_CONFIG_VEHICULO", as_index=False, observed=True,
            )["VIAJESTOTALES"].sum()
            df_cfg = df_cfg.nlargest(8, "VIAJESTOTALES")
            fig_cfg = px.pie(
                df_cfg, names="COD_CONFIG_VEHICULO", values="VIAJESTOTALES",
                color_discrete_sequence=CAT_COLORS, hole=0.4,
            )
            fig_cfg.update_traces(
                textposition="inside", textinfo="percent+label",
                hovertemplate=(
                    "<b>%{label}</b><br>Viajes: %{value:,.0f}"
                    "<br>%{percent}<extra></extra>"
                ),
                marker=dict(line=dict(color=SURFACE, width=2)),
            )
            chart_layout(fig_cfg, "Configuracion vehiculo", height=380)
            st.plotly_chart(fig_cfg, width="stretch")


# ======================================================================
# PAGINA 3: COMPARATIVO FLETES
# ======================================================================
elif pagina == "💰 Comparativo FP y FM":
    st.title("Comparativo de Fletes")
    st.caption(
        "Flete Mercado (Estadisticas RNDC) - Nuestro Flete (sin cargue ni descargue) - Tarifa SICETAC"
    )

    # Aplicar filtro global de ano/mes a los 3 datasets de pagina 3
    # -- MUNI (flete mercado) --
    if not df_muni.empty and ano_sel:
        _muni_mask = df_muni["ANO"].isin(ano_sel)
        if mes_sel:
            _muni_mask = _muni_mask & df_muni["MES_NUM"].isin(mes_sel)
        df_muni_filt = df_muni[_muni_mask]
    else:
        df_muni_filt = df_muni

    # -- Construir set de periodos permitidos (formato YYYYMM) --
    _periodos_ok = set()
    if ano_sel and mes_sel:
        for a in ano_sel:
            for m in mes_sel:
                _periodos_ok.add("{}{}".format(str(a), str(int(m)).zfill(2)))

    # -- SICETAC --
    if not df_sicetac.empty and _periodos_ok:
        df_sicetac_filt = df_sicetac[
            df_sicetac["PERIODO"].astype(str).isin(_periodos_ok)
        ]
    else:
        df_sicetac_filt = df_sicetac

    # -- FP (costos flota propia) --
    if (
        not df_costos.empty
        and "MES_FP" in df_costos.columns
        and _periodos_ok
    ):
        df_costos_filt = df_costos[
            df_costos["MES_FP"].astype(str).isin(_periodos_ok)
        ]
    else:
        df_costos_filt = df_costos

    has_fm = not df_muni_filt.empty
    has_fp = not df_costos_filt.empty and "COD_MUNI_ORIG" in df_costos_filt.columns
    has_sic = not df_sicetac_filt.empty

    if not has_fm and not has_fp and not has_sic:
        st.warning("No se encontraron datos para la comparacion.")
    else:
        # -- Construir mapeo DANE -> nombre de municipio --
        dane_to_name_orig = {}
        dane_to_name_dest = {}
        if has_fm:
            _o = df_muni[
                ["CODMUNICIPIOORIGEN", "MUNICIPIOORIGEN"]
            ].drop_duplicates()
            _o = _o.dropna(subset=["CODMUNICIPIOORIGEN", "MUNICIPIOORIGEN"])
            _o_codes = pd.to_numeric(
                _o["CODMUNICIPIOORIGEN"], errors="coerce"
            ).fillna(0)
            _o = _o[_o_codes > 0]
            dane_to_name_orig = dict(
                zip(
                    _o["CODMUNICIPIOORIGEN"].astype(int),
                    _o["MUNICIPIOORIGEN"].astype(str),
                )
            )
            _d = df_muni[
                ["CODMUNICIPIODESTINO", "MUNICIPIODESTINO"]
            ].drop_duplicates()
            _d = _d.dropna(subset=["CODMUNICIPIODESTINO", "MUNICIPIODESTINO"])
            _d_codes = pd.to_numeric(
                _d["CODMUNICIPIODESTINO"], errors="coerce"
            ).fillna(0)
            _d = _d[_d_codes > 0]
            dane_to_name_dest = dict(
                zip(
                    _d["CODMUNICIPIODESTINO"].astype(int),
                    _d["MUNICIPIODESTINO"].astype(str),
                )
            )
            del _o, _d
        if has_sic:
            _o = df_sicetac[["ORIGEN", "NOMORIGEN"]].drop_duplicates()
            _o = _o.dropna(subset=["ORIGEN", "NOMORIGEN"])
            _o = _o[
                pd.to_numeric(_o["ORIGEN"], errors="coerce").fillna(0) > 0
            ]
            for code, name in zip(
                _o["ORIGEN"].astype(int), _o["NOMORIGEN"].astype(str)
            ):
                dane_to_name_orig.setdefault(code, name)
            _d = df_sicetac[["DESTINO", "NOMDESTINO"]].drop_duplicates()
            _d = _d.dropna(subset=["DESTINO", "NOMDESTINO"])
            _d = _d[
                pd.to_numeric(_d["DESTINO"], errors="coerce").fillna(0) > 0
            ]
            for code, name in zip(
                _d["DESTINO"].astype(int), _d["NOMDESTINO"].astype(str)
            ):
                dane_to_name_dest.setdefault(code, name)
            del _o, _d

        dane_to_name = {**dane_to_name_orig, **dane_to_name_dest}
        name_to_dane_orig = {v: k for k, v in dane_to_name_orig.items()}
        name_to_dane_dest = {v: k for k, v in dane_to_name_dest.items()}

        # -- Filtros de configuracion, mercancia y naturaleza --
        col_fc1, col_fc2, col_fc3 = st.columns(3)

        with col_fc1:
            if has_fm:
                configs_comp = sorted(
                    df_muni["COD_CONFIG_VEHICULO"].dropna().unique().tolist()
                )
                configs_comp = [c for c in configs_comp if c.strip()]
                default_idx = (
                    configs_comp.index("3S3") + 1
                    if "3S3" in configs_comp
                    else 0
                )
            else:
                configs_comp = []
                default_idx = 0
            config_comp_sel = st.selectbox(
                "Configuracion",
                ["Todos"] + configs_comp,
                index=default_idx,
                key="comp_config",
            )

        with col_fc2:
            # Mercancia no se usa para filtrar en page 3 (no esta en MUNI)
            st.text("")  # placeholder

        with col_fc3:
            if has_fm:
                nat_comp_options = sorted(
                    df_muni["NATURALEZACARGA"].dropna().unique().tolist()
                )
                nat_normal = [
                    n for n in nat_comp_options if "NORMAL" in n.upper()
                ]
                default_nat_idx = (
                    nat_comp_options.index(nat_normal[0]) + 1
                    if nat_normal
                    else 0
                )
            else:
                nat_comp_options = []
                default_nat_idx = 0
            nat_comp_sel = st.selectbox(
                "Naturaleza de la carga",
                ["Todos"] + nat_comp_options,
                index=default_nat_idx,
                key="comp_nat",
            )

        # -- Aplicar filtros base --
        if has_fm:
            df_fm_base = df_muni_filt.copy()
            if config_comp_sel != "Todos":
                df_fm_base = df_fm_base[
                    df_fm_base["COD_CONFIG_VEHICULO"] == config_comp_sel
                ]
            if nat_comp_sel != "Todos":
                df_fm_base = df_fm_base[
                    df_fm_base["NATURALEZACARGA"] == nat_comp_sel
                ]
        else:
            df_fm_base = pd.DataFrame()

        if has_sic:
            df_sic_base = df_sicetac_filt.copy()
            if config_comp_sel != "Todos":
                df_sic_base = df_sic_base[
                    df_sic_base["CONFIGURACION"] == config_comp_sel
                ]
        else:
            df_sic_base = pd.DataFrame()

        if has_fp:
            df_fp_base = df_costos_filt.copy()
            if (
                config_comp_sel != "Todos"
                and "CONFIG_FP" in df_fp_base.columns
            ):
                df_fp_base = df_fp_base[
                    df_fp_base["CONFIG_FP"] == config_comp_sel
                ]
            if (
                nat_comp_sel != "Todos"
                and "NATURALEZA_FP" in df_fp_base.columns
            ):
                nat_fp_upper = (
                    df_fp_base["NATURALEZA_FP"].str.upper().str.strip()
                )
                nat_sel_upper = nat_comp_sel.upper().strip()
                df_fp_base = df_fp_base[
                    nat_fp_upper.apply(
                        lambda x: x in nat_sel_upper or nat_sel_upper in x
                        if pd.notna(x)
                        else False
                    )
                ]
        else:
            df_fp_base = pd.DataFrame()

        # -- Construir listas de municipios --
        muni_orig_names = set()
        muni_dest_names = set()

        if not df_fm_base.empty:
            muni_orig_names.update(
                df_fm_base["MUNICIPIOORIGEN"].dropna().unique()
            )
            muni_dest_names.update(
                df_fm_base["MUNICIPIODESTINO"].dropna().unique()
            )
        if not df_sic_base.empty:
            muni_orig_names.update(
                df_sic_base["NOMORIGEN"].dropna().unique()
            )
            muni_dest_names.update(
                df_sic_base["NOMDESTINO"].dropna().unique()
            )
        if not df_fp_base.empty:
            for code in df_fp_base["COD_MUNI_ORIG"].dropna().unique():
                c = int(code)
                if c in dane_to_name:
                    muni_orig_names.add(dane_to_name[c])
            for code in df_fp_base["COD_MUNI_DEST"].dropna().unique():
                c = int(code)
                if c in dane_to_name:
                    muni_dest_names.add(dane_to_name[c])

        # -- Filtros de municipio --
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            muni_orig_sel = st.selectbox(
                "Municipio origen",
                ["Todos"] + sorted(muni_orig_names),
                key="comp_orig",
            )
        with col_f2:
            if muni_orig_sel != "Todos":
                dest_names = set()
                dane_orig = name_to_dane_orig.get(muni_orig_sel, 0)
                if not df_fm_base.empty:
                    dest_names.update(
                        df_fm_base[
                            df_fm_base["MUNICIPIOORIGEN"] == muni_orig_sel
                        ]["MUNICIPIODESTINO"]
                        .dropna()
                        .unique()
                    )
                if not df_sic_base.empty:
                    dest_names.update(
                        df_sic_base[
                            df_sic_base["NOMORIGEN"] == muni_orig_sel
                        ]["NOMDESTINO"]
                        .dropna()
                        .unique()
                    )
                if not df_fp_base.empty and dane_orig > 0:
                    for code in (
                        df_fp_base[df_fp_base["COD_MUNI_ORIG"] == dane_orig][
                            "COD_MUNI_DEST"
                        ]
                        .dropna()
                        .unique()
                    ):
                        c = int(code)
                        if c in dane_to_name:
                            dest_names.add(dane_to_name[c])
                muni_dest_options_comp = sorted(dest_names)
            else:
                muni_dest_options_comp = sorted(muni_dest_names)

            muni_dest_sel = st.selectbox(
                "Municipio destino",
                ["Todos"] + muni_dest_options_comp,
                key="comp_dest",
            )

        st.divider()

        dane_orig_sel = (
            name_to_dane_orig.get(muni_orig_sel, 0)
            if muni_orig_sel != "Todos"
            else 0
        )
        dane_dest_sel = (
            name_to_dane_dest.get(muni_dest_sel, 0)
            if muni_dest_sel != "Todos"
            else 0
        )

        # -- Calcular Flete Mercado --
        if not df_fm_base.empty:
            df_fm = df_fm_base.copy()
            if muni_orig_sel != "Todos":
                df_fm = df_fm[df_fm["MUNICIPIOORIGEN"] == muni_orig_sel]
            if muni_dest_sel != "Todos":
                df_fm = df_fm[df_fm["MUNICIPIODESTINO"] == muni_dest_sel]

            if not df_fm.empty:
                fm_agg = df_fm.groupby(
                    "MES", as_index=False, observed=True,
                ).agg(
                    VALOR=("VALORESPAGADOS", "sum"),
                    VIAJES_CV=("VIAJES_CON_VALOR", "sum"),
                )
                fm_agg["Flete Mercado"] = (
                    fm_agg["VALOR"] / fm_agg["VIAJES_CV"].replace(0, 1)
                )
            else:
                fm_agg = pd.DataFrame()
        else:
            fm_agg = pd.DataFrame()

        # -- Calcular Nuestro Flete (FP) --
        if (
            not df_fp_base.empty
            and "Flete_sin_CyD" in df_fp_base.columns
        ):
            df_fp = df_fp_base.copy()
            if dane_orig_sel > 0:
                df_fp = df_fp[df_fp["COD_MUNI_ORIG"] == dane_orig_sel]
            if dane_dest_sel > 0:
                df_fp = df_fp[df_fp["COD_MUNI_DEST"] == dane_dest_sel]

            if not df_fp.empty and "MES_FP" in df_fp.columns:
                fp_agg = df_fp.groupby("MES_FP", as_index=False).agg(
                    **{"Nuestro Flete": ("Flete_sin_CyD", "mean")}
                )
                fp_agg = fp_agg.rename(columns={"MES_FP": "MES"})
            else:
                fp_agg = pd.DataFrame()
        else:
            fp_agg = pd.DataFrame()

        # -- Calcular Promedio SICETAC --
        if not df_sic_base.empty:
            df_sic = df_sic_base.copy()
            if muni_orig_sel != "Todos":
                if dane_orig_sel > 0:
                    df_sic = df_sic[
                        (df_sic["NOMORIGEN"] == muni_orig_sel)
                        | (df_sic["ORIGEN"] == dane_orig_sel)
                    ]
                else:
                    df_sic = df_sic[df_sic["NOMORIGEN"] == muni_orig_sel]
            if muni_dest_sel != "Todos":
                if dane_dest_sel > 0:
                    df_sic = df_sic[
                        (df_sic["NOMDESTINO"] == muni_dest_sel)
                        | (df_sic["DESTINO"] == dane_dest_sel)
                    ]
                else:
                    df_sic = df_sic[df_sic["NOMDESTINO"] == muni_dest_sel]

            if not df_sic.empty:
                sic_agg = df_sic.groupby(
                    "PERIODO", as_index=False, observed=True,
                ).agg(
                    VALOR_SUMA=("VALOR_SUMA", "sum"),
                    CONTEO=("CONTEO", "sum"),
                )
                sic_agg["SICETAC"] = (
                    sic_agg["VALOR_SUMA"]
                    / sic_agg["CONTEO"].replace(0, 1)
                )
                sic_agg = sic_agg.rename(columns={"PERIODO": "MES"})
            else:
                sic_agg = pd.DataFrame()
        else:
            sic_agg = pd.DataFrame()

        # -- Construir tabla comparativa --
        st.subheader("Comparativo de Fletes")

        all_periodos = set()
        if not fm_agg.empty:
            all_periodos.update(fm_agg["MES"].unique())
        if not fp_agg.empty:
            all_periodos.update(fp_agg["MES"].unique())
        if not sic_agg.empty:
            all_periodos.update(sic_agg["MES"].unique())

        if not all_periodos:
            st.info(
                "No hay datos para la combinacion de filtros seleccionada. "
                "Selecciona un municipio de origen y destino."
            )
        else:
            tabla = pd.DataFrame({"MES": sorted(all_periodos)})

            if not fm_agg.empty:
                tabla = tabla.merge(
                    fm_agg[["MES", "Flete Mercado"]], on="MES", how="left"
                )
            else:
                tabla["Flete Mercado"] = float("nan")

            if not fp_agg.empty:
                tabla = tabla.merge(
                    fp_agg[["MES", "Nuestro Flete"]], on="MES", how="left"
                )
            else:
                tabla["Nuestro Flete"] = float("nan")

            if not sic_agg.empty:
                tabla = tabla.merge(
                    sic_agg[["MES", "SICETAC"]], on="MES", how="left"
                )
            else:
                tabla["SICETAC"] = float("nan")

            tabla = tabla.sort_values("MES")

            tabla["Periodo"] = tabla["MES"].apply(
                lambda x: "{} {}".format(
                    MESES_NOMBRE.get(int(str(x)[4:6]), str(x)[4:6]),
                    str(x)[:4],
                )
                if pd.notna(x) and len(str(x)) >= 6
                else str(x)
            )

            ruta_label = ""
            if muni_orig_sel != "Todos" and muni_dest_sel != "Todos":
                ruta_label = "**Ruta:** {} -> {}".format(
                    muni_orig_sel, muni_dest_sel
                )
            elif muni_orig_sel != "Todos":
                ruta_label = "**Origen:** {}".format(muni_orig_sel)
            elif muni_dest_sel != "Todos":
                ruta_label = "**Destino:** {}".format(muni_dest_sel)
            if ruta_label:
                st.markdown(ruta_label)

            tabla_display = tabla[
                ["Periodo", "Flete Mercado", "Nuestro Flete", "SICETAC"]
            ].copy()

            total_dict = {"Periodo": "Promedio"}
            for col in ["Flete Mercado", "Nuestro Flete", "SICETAC"]:
                vals = tabla_display[col].dropna()
                total_dict[col] = vals.mean() if len(vals) > 0 else None
            tabla_con_total = pd.concat(
                [tabla_display, pd.DataFrame([total_dict])],
                ignore_index=True,
            )

            format_dict = {
                c: "${:,.0f}"
                for c in ["Flete Mercado", "Nuestro Flete", "SICETAC"]
            }

            col_tabla, col_chart = st.columns([1, 1])

            with col_tabla:
                st.dataframe(
                    tabla_con_total.style.format(format_dict, na_rep="-")
                    .apply(
                        lambda row: ["font-weight: bold"] * len(row)
                        if row["Periodo"] == "Promedio"
                        else [""] * len(row),
                        axis=1,
                    ),
                    width="stretch",
                    hide_index=True,
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
                        fig_comp.add_trace(
                            go.Scatter(
                                x=df_line["Periodo"],
                                y=df_line[col],
                                name=name,
                                mode="lines+markers+text",
                                text=[
                                    "${:,.0f}".format(v)
                                    if pd.notna(v)
                                    else ""
                                    for v in df_line[col]
                                ],
                                textposition="top center",
                                textfont=dict(size=9, color=color),
                                line=dict(color=color, width=2.5),
                                marker=dict(size=8),
                                hovertemplate=(
                                    "<b>%{{x}}</b><br>{}: $%{{y:,.0f}}"
                                    "<extra></extra>".format(name)
                                ),
                            )
                        )
                chart_layout(
                    fig_comp, "Comparativo de Fletes por Mes", height=450
                )
                st.plotly_chart(fig_comp, width="stretch")

        st.divider()

        # -- Incremento SICETAC periodo a periodo --
        if has_sic and not df_sicetac_filt.empty:
            st.subheader("Incremento SICETAC mes a mes (3S3)")
            st.caption(
                "Variacion porcentual del valor promedio SICETAC "
                "respecto al periodo anterior (configuracion 3S3)"
            )

            # Filtrar solo configuracion 3S3
            _sic_3s3 = df_sicetac_filt[
                df_sicetac_filt["CONFIGURACION"].astype(str).str.strip() == "3S3"
            ]
            if _sic_3s3.empty:
                st.info("No hay datos SICETAC para configuracion 3S3.")
            _sic_src = _sic_3s3 if not _sic_3s3.empty else df_sicetac_filt

            # Agregar SICETAC 3S3 por periodo
            sic_trend = _sic_src.groupby(
                "PERIODO", as_index=False, observed=True,
            ).agg(
                VALOR_SUMA=("VALOR_SUMA", "sum"),
                CONTEO=("CONTEO", "sum"),
            )
            sic_trend["Tarifa_Prom"] = (
                sic_trend["VALOR_SUMA"]
                / sic_trend["CONTEO"].replace(0, 1)
            )
            sic_trend = sic_trend.sort_values("PERIODO").reset_index(drop=True)

            # Calcular variacion vs periodo anterior
            sic_trend["Tarifa_Ant"] = sic_trend["Tarifa_Prom"].shift(1)
            sic_trend["Var_Abs"] = (
                sic_trend["Tarifa_Prom"] - sic_trend["Tarifa_Ant"]
            )
            sic_trend["Var_Pct"] = (
                sic_trend["Var_Abs"]
                / sic_trend["Tarifa_Ant"].replace(0, float("nan"))
                * 100
            )

            # Etiqueta legible del periodo
            sic_trend["Periodo"] = sic_trend["PERIODO"].apply(
                lambda x: "{} {}".format(
                    MESES_NOMBRE.get(int(str(x)[4:6]), str(x)[4:6]),
                    str(x)[:4],
                )
                if pd.notna(x) and len(str(x)) >= 6
                else str(x)
            )

            # Tabla de incremento
            sic_disp = sic_trend[
                ["Periodo", "Tarifa_Prom", "Var_Abs", "Var_Pct"]
            ].copy()
            sic_disp = sic_disp.rename(columns={
                "Tarifa_Prom": "Tarifa Promedio",
                "Var_Abs": "Variacion $",
                "Var_Pct": "Variacion %",
            })

            # Promedio de variacion (excluyendo el primer registro que es NaN)
            prom_var_pct = sic_disp["Variacion %"].dropna().mean()
            prom_var_abs = sic_disp["Variacion $"].dropna().mean()

            # Fila de promedio
            fila_prom = {
                "Periodo": "Promedio",
                "Tarifa Promedio": sic_disp["Tarifa Promedio"].mean(),
                "Variacion $": prom_var_abs,
                "Variacion %": prom_var_pct,
            }
            sic_con_prom = pd.concat(
                [sic_disp, pd.DataFrame([fila_prom])],
                ignore_index=True,
            )

            col_t_sic, col_g_sic = st.columns([1, 1])

            with col_t_sic:
                def _color_var(val):
                    if pd.isna(val):
                        return ""
                    if val > 0:
                        return "color: #e34948"
                    elif val < 0:
                        return "color: #1baf7a"
                    return ""

                styled = sic_con_prom.style.format(
                    {
                        "Tarifa Promedio": "${:,.0f}",
                        "Variacion $": "${:+,.0f}",
                        "Variacion %": "{:+.2f}%",
                    },
                    na_rep="-",
                ).map(
                    _color_var,
                    subset=["Variacion $", "Variacion %"],
                ).apply(
                    lambda row: ["font-weight: bold"] * len(row)
                    if row["Periodo"] == "Promedio"
                    else [""] * len(row),
                    axis=1,
                )
                st.dataframe(
                    styled,
                    width="stretch",
                    hide_index=True,
                    height=min(500, (len(sic_con_prom) + 1) * 38),
                )

            with col_g_sic:
                # Grafico de barras con variacion %
                sic_chart = sic_trend[sic_trend["Var_Pct"].notna()].copy()
                if not sic_chart.empty:
                    bar_colors = [
                        COLORS["red"] if v > 0 else COLORS["aqua"]
                        for v in sic_chart["Var_Pct"]
                    ]
                    fig_sic = go.Figure(
                        go.Bar(
                            x=sic_chart["Periodo"],
                            y=sic_chart["Var_Pct"],
                            marker=dict(
                                color=bar_colors, cornerradius=4
                            ),
                            text=[
                                "{:+.2f}%".format(v)
                                for v in sic_chart["Var_Pct"]
                            ],
                            textposition="outside",
                            textfont=dict(size=10),
                            hovertemplate=(
                                "<b>%{x}</b><br>"
                                "Variacion: %{y:+.2f}%<extra></extra>"
                            ),
                        )
                    )
                    # Linea de promedio
                    fig_sic.add_hline(
                        y=prom_var_pct,
                        line_dash="dash",
                        line_color=COLORS["yellow"],
                        line_width=2,
                        annotation_text="Prom: {:+.2f}%".format(
                            prom_var_pct
                        ),
                        annotation_position="top left",
                        annotation_font_color=COLORS["yellow"],
                    )
                    chart_layout(
                        fig_sic,
                        "Variacion % SICETAC mes a mes",
                        height=450,
                    )
                    fig_sic.update_layout(
                        yaxis_title="Variacion %",
                        yaxis_ticksuffix="%",
                    )
                    st.plotly_chart(fig_sic, width="stretch")
                else:
                    st.info("Se necesitan al menos 2 periodos para calcular la variacion.")

            # KPI resumen
            if pd.notna(prom_var_pct):
                col_k1, col_k2, col_k3 = st.columns(3)
                col_k1.metric(
                    "Incremento promedio mensual",
                    "{:+.2f}%".format(prom_var_pct),
                )
                col_k2.metric(
                    "Variacion promedio $",
                    "${:+,.0f}".format(prom_var_abs),
                )
                # Ultimo periodo
                last = sic_trend.iloc[-1]
                if pd.notna(last["Var_Pct"]):
                    col_k3.metric(
                        "Ultimo periodo ({})".format(last["Periodo"]),
                        "${:,.0f}".format(last["Tarifa_Prom"]),
                        "{:+.2f}%".format(last["Var_Pct"]),
                    )

        st.divider()

        # -- Detalle de rutas con datos FP --
        if has_fp and "Flete_sin_CyD" in df_costos_filt.columns:
            with st.expander("Detalle Nuestro Flete por Ruta"):
                df_fp_det = (
                    df_fp_base.copy()
                    if not df_fp_base.empty
                    else df_costos_filt.copy()
                )

                df_fp_det["Origen"] = df_fp_det["COD_MUNI_ORIG"].map(
                    lambda c: dane_to_name.get(int(c), str(int(c)))
                    if pd.notna(c) and c > 0
                    else "Desconocido"
                )
                df_fp_det["Destino"] = df_fp_det["COD_MUNI_DEST"].map(
                    lambda c: dane_to_name.get(int(c), str(int(c)))
                    if pd.notna(c) and c > 0
                    else "Desconocido"
                )

                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    origenes_fp = ["Todos"] + sorted(
                        df_fp_det["Origen"].dropna().unique().tolist()
                    )
                    orig_fp_sel = st.selectbox(
                        "Municipio Origen FP", origenes_fp, key="fp_muni_orig"
                    )

                if orig_fp_sel != "Todos":
                    df_fp_det = df_fp_det[df_fp_det["Origen"] == orig_fp_sel]

                col1, col2 = st.columns(2)
                flete_sin_cyd_prom = (
                    df_fp_det["Flete_sin_CyD"].mean()
                    if not df_fp_det.empty
                    else 0
                )
                col1.metric("Rutas", "{:,.0f}".format(len(df_fp_det)))
                col2.metric(
                    "Flete Prom. sin CyD",
                    "${:,.0f}".format(flete_sin_cyd_prom),
                )

                if not df_fp_det.empty:
                    df_rutas = (
                        df_fp_det.groupby(
                            ["Origen", "Destino"], as_index=False
                        )
                        .agg(
                            Rutas=("Flete_sin_CyD", "count"),
                            **{"Flete sin CyD": ("Flete_sin_CyD", "mean")},
                        )
                        .sort_values("Flete sin CyD", ascending=False)
                    )

                    st.dataframe(
                        df_rutas.style.format(
                            {
                                "Rutas": "{:,.0f}",
                                "Flete sin CyD": "${:,.0f}",
                            }
                        ),
                        width="stretch",
                        hide_index=True,
                        height=min(500, (len(df_rutas) + 1) * 38),
                    )


# ======================================================================
# PAGINA 4: TABLA CONSOLIDADA
# ======================================================================
elif pagina == "📋 Tabla Consolidada":
    st.title("Tabla Consolidada")

    if df_filtrado.empty:
        st.warning("No hay datos para los filtros seleccionados.")
    else:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            configs_tc = ["Todos"] + sorted(
                df_filtrado["CONFIG_VEHICULO"].dropna().unique().tolist()
            )
            config_tc_sel = st.selectbox(
                "Configuracion", configs_tc, key="tc_config"
            )

        df_tc = df_filtrado.copy()
        if config_tc_sel != "Todos":
            df_tc = df_tc[df_tc["CONFIG_VEHICULO"] == config_tc_sel]

        df_consol = (
            df_tc.groupby(
                ["MES_NOMBRE", "PERIODO"], as_index=False, observed=True,
            )
            .agg(
                Viajes=("VIAJESTOTALES", "sum"),
                Viajes_con_valor=("VIAJES_CON_VALOR", "sum"),
                Flete_pagado=("VALORESPAGADOS", "sum"),
                Toneladas=("TONELADAS", "sum"),
            )
            .sort_values("PERIODO")
        )

        df_consol["Flete Promedio"] = (
            df_consol["Flete_pagado"]
            / df_consol["Viajes_con_valor"].replace(0, 1)
        ).round(0)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric(
            "Total Viajes", "{:,.0f}".format(df_consol["Viajes"].sum())
        )
        col2.metric(
            "Viajes con Valor",
            "{:,.0f}".format(df_consol["Viajes_con_valor"].sum()),
        )
        col3.metric(
            "Flete Pagado Total",
            "${:,.0f}".format(df_consol["Flete_pagado"].sum()),
        )
        col4.metric(
            "Toneladas Total",
            "{:,.0f}".format(df_consol["Toneladas"].sum()),
        )

        st.divider()

        df_display = df_consol[
            ["MES_NOMBRE", "Viajes", "Viajes_con_valor", "Flete_pagado", "Toneladas"]
        ].copy()
        df_display.columns = [
            "Mes", "Viajes", "Viajes con Valor", "Flete Pagado", "Toneladas",
        ]

        st.dataframe(
            df_display.style.format(
                {
                    "Viajes": "{:,.0f}",
                    "Viajes con Valor": "{:,.0f}",
                    "Flete Pagado": "${:,.0f}",
                    "Toneladas": "{:,.0f}",
                }
            ),
            width="stretch",
            height=400,
            hide_index=True,
        )

        fig_consol = go.Figure()
        fig_consol.add_trace(
            go.Bar(
                x=df_consol["MES_NOMBRE"],
                y=df_consol["Viajes"],
                name="Viajes",
                marker=dict(color=COLORS["blue"], cornerradius=4),
                hovertemplate=(
                    "<b>%{x}</b><br>Viajes: %{y:,.0f}<extra></extra>"
                ),
            )
        )
        fig_consol.add_trace(
            go.Scatter(
                x=df_consol["MES_NOMBRE"],
                y=df_consol["Toneladas"],
                name="Toneladas",
                yaxis="y2",
                mode="lines+markers",
                line=dict(color=COLORS["orange"], width=2),
                marker=dict(size=8),
                hovertemplate=(
                    "<b>%{x}</b><br>Toneladas: %{y:,.0f}<extra></extra>"
                ),
            )
        )
        fig_consol.update_layout(
            yaxis2=dict(
                overlaying="y",
                side="right",
                gridcolor="rgba(0,0,0,0)",
                tickfont=dict(color=COLORS["orange"]),
            )
        )
        chart_layout(fig_consol, "Viajes y Toneladas por Mes", height=420)
        st.plotly_chart(fig_consol, width="stretch")


# --- Footer ---
st.sidebar.divider()
st.sidebar.caption("Datos: RNDC - Ministerio de Transporte")
st.sidebar.caption("Desarrollado para Edinsa")

with st.sidebar.expander("Diagnostico"):
    data_dir = _get_data_dir()
    st.write("**Carpeta data:** `{}`".format(data_dir))
    st.write("**Existe:** {}".format(os.path.isdir(data_dir)))
    if os.path.isdir(data_dir):
        archivos = os.listdir(data_dir)
        st.write("**Archivos encontrados:** {}".format(len(archivos)))
        for a in sorted(archivos):
            size_kb = os.path.getsize(os.path.join(data_dir, a)) / 1024
            st.write("- {} ({:.0f} KB)".format(a, size_kb))
    st.divider()
    st.write(
        "**Core:** {} filas".format(
            df_core.shape[0] if not df_core.empty else 0
        )
    )
    st.write(
        "**Merc:** {} filas".format(
            df_merc.shape[0] if not df_merc.empty else 0
        )
    )
    st.write(
        "**Muni:** {} filas".format(
            df_muni.shape[0] if not df_muni.empty else 0
        )
    )
    st.write("**Ranking:** {} filas".format(df_ranking.shape[0]))
    st.write(
        "**SICETAC:** {} filas".format(
            df_sicetac.shape[0] if not df_sicetac.empty else 0
        )
    )
    st.write("**Costos FP:** {} filas".format(df_costos.shape[0]))
    if _load_log:
        st.divider()
        st.write("**Log de carga:**")
        for msg in _load_log:
            st.write("- {}".format(msg))
