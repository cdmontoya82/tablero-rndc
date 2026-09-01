# Tablero RNDC - Edinsa

Dashboard interactivo de estadísticas de transporte RNDC (Registro Nacional de Despachos de Carga) para **EMPRESA DE DISTRIBUCIONES INDUSTRIALES S.A. (EDINSA)**.

## Páginas

1. **Ranking Empresa** - Ranking de empresas por toneladas, con EDINSA resaltada y tabla de participación mensual
2. **Estadísticas de Carga** - Análisis por configuración vehicular, rutas, mercancías y departamentos
3. **Comparación Flete FP** - Comparación de fletes pagados vs tarifas SICETAC de referencia
4. **Tabla Consolidada** - Vista detallada y descargable de todos los datos

## Ejecución local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Datos

Colocar los archivos en la carpeta `data/`:

| Tipo | Nombre del archivo |
|------|-------------------|
| Estadísticas RNDC | `EstadisticasRNDC_AAAAMM.parquet` o `.xlsx` |
| Ranking empresa | `NombreMes AAAA.xlsx` (ej: `Junio 2026.xlsx`) |
| SICETAC | `Sicetac_AAAA_MM_DD.parquet` o `.xlsx` |
| Costos flota propia | `Costo ruta flota propia_mes_aaaa.xlsx` |
| Maestro rutas | `Rutas_Maestro (1).xlsx` |
