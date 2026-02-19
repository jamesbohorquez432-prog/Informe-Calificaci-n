import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
st.write("App cargada correctamente")
from io import BytesIO
# PDF (reportlab)
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from pathlib import Path 
st.set_page_config(page_title="Calificación", layout="wide")

from pathlib import Path

# Rutas de logos (pon los archivos en la misma carpeta del app.py)

BASE_DIR = Path(__file__).parent
LOGO_COL = BASE_DIR / "images" / "logo_colombia.png"


# Encabezado con imágenes

BASE_DIR = Path(__file__).parent
LOGO_COL = BASE_DIR / "images" / "logo_colombia.png"
# Encabezado
c1, c2 = st.columns([5, 1])
with c1:
   st.markdown(
       "<h1 style='text-align: center;'>Calificación</h1>",
       unsafe_allow_html=True
   )
   st.markdown(
       "<h4 style='text-align: center;'>Periodo: Octubre – Diciembre</h4>",
       unsafe_allow_html=True
   )
with c2:
   if LOGO_COL.exists():
       st.image(str(LOGO_COL), use_container_width=True)
st.markdown("---")

# ---------------------------
# Utilidades numéricas
# ---------------------------
def _to_number(x):
   if pd.isna(x):
       return np.nan
   if isinstance(x, (int, float, np.number)):
       return float(x)
   s = str(x).strip().replace(",", ".").replace("%", "")
   try:
       return float(s)
   except:
       return np.nan
def _auto_scale_percent(series: pd.Series) -> pd.Series:
   """
   Si los valores parecen estar en 0-1 (ej: 0.92), convierte a 0-100.
   Si ya están en 0-100, no hace nada.
   """
   s = series.dropna()
   if s.empty:
       return series
   # Heurística: si el percentil 95 <= 1.2, asumimos escala 0-1
   p95 = float(np.nanpercentile(s.values, 95))
   if p95 <= 1.2:
       return series * 100.0
   return series
def _semaforo(valor: float) -> str:
   # Ajusta si quieres umbrales distintos
   if np.isnan(valor):
       return "⚪ Sin dato"
   if valor >= 90:
       return "🟢 Alto"
   if valor >= 75:
       return "🟡 Medio"
   return "🔴 Bajo"
# ---------------------------
# Lectura de hojas
# ---------------------------
def leer_hoja_abogado(xls: pd.ExcelFile, sheet_name: str) -> dict:
   raw = xls.parse(sheet_name, header=None)
   raw.columns = ["Funcion", "Peso", "Cumplimiento", "ResultadoPonderado"]
   # quitar encabezado textual
   df = raw.iloc[1:].reset_index(drop=True)
   # detectar fila final (en tu formato viene en la col "Cumplimiento")
   final_mask = df["Cumplimiento"].astype(str).str.contains("Resultado Final", case=False, na=False)
   resultado_final = None
   if final_mask.any():
       idx = df[final_mask].index[0]
       resultado_final = _to_number(df.loc[idx, "ResultadoPonderado"])
       detalle = df.loc[: idx - 1].copy()
   else:
       detalle = df.copy()
       
   # numéricos
   for c in ["Peso", "Cumplimiento", "ResultadoPonderado"]:
       detalle[c] = detalle[c].apply(_to_number)
   # autoescala (peso normalmente es 0-100; cumplimiento puede venir 0-1 o 0-100; resultado ponderado puede venir 0-1 o 0-100)
   detalle["Peso"] = _auto_scale_percent(detalle["Peso"])
   detalle["Cumplimiento"] = _auto_scale_percent(detalle["Cumplimiento"])
   detalle["ResultadoPonderado"] = _auto_scale_percent(detalle["ResultadoPonderado"])
   # si ResultadoPonderado está vacío, calcularlo
   if detalle["ResultadoPonderado"].isna().all() and detalle["Peso"].notna().any():
       detalle["ResultadoPonderado"] = (detalle["Peso"] * detalle["Cumplimiento"]) / 100.0
   # recalcular final si no está explícito
   if resultado_final is None or np.isnan(resultado_final):
       resultado_final = float(np.nansum(detalle["ResultadoPonderado"].values))
   else:
       # si venía en 0-1, convertir
       if resultado_final <= 1.2:
           resultado_final *= 100.0
   detalle["Funcion"] = detalle["Funcion"].astype(str)
   # validación rápida de pesos
   suma_pesos = float(np.nansum(detalle["Peso"].values))
   return {
       "detalle": detalle,
       "resultado_final": float(resultado_final),
       "suma_pesos": suma_pesos,
   }
def leer_calificacion_general(xls: pd.ExcelFile) -> pd.DataFrame:
   raw = xls.parse("CALIFICACIÓN", header=None)
   raw.columns = ["FUNCIONARIO", "RESULTADO_PONDERADO"]
   df = raw.iloc[1:].copy()
   df["FUNCIONARIO"] = df["FUNCIONARIO"].astype(str)
   df["RESULTADO_PONDERADO"] = df["RESULTADO_PONDERADO"].apply(_to_number)
   df["RESULTADO_PONDERADO"] = _auto_scale_percent(df["RESULTADO_PONDERADO"])
   return df
# ---------------------------
# PDF export (simple y útil)
# ---------------------------
def generar_pdf_abogado(nombre: str, periodo: str, resultado_final: float, suma_pesos: float, df: pd.DataFrame) -> bytes:
   buffer = BytesIO()
   c = canvas.Canvas(buffer, pagesize=letter)
   w, h = letter
   # Encabezado
   c.setFont("Helvetica-Bold", 16)
   c.drawString(2 * cm, h - 2 * cm, "Calificación")
   c.setFont("Helvetica", 11)
   c.drawString(2 * cm, h - 2.7 * cm, f"Abogado: {nombre}")
   c.drawString(2 * cm, h - 3.3 * cm, f"Periodo: {periodo}")
   c.drawString(2 * cm, h - 3.9 * cm, f"Resultado Final (%): {resultado_final:.2f}  |  Semáforo: {_semaforo(resultado_final)}")
   c.drawString(2 * cm, h - 4.5 * cm, f"Suma de Pesos (%): {suma_pesos:.2f}")
   # Tabla (simple)
   c.setFont("Helvetica-Bold", 10)
   y = h - 5.4 * cm
   c.drawString(2 * cm, y, "Función")
   c.drawString(10.8 * cm, y, "Peso")
   c.drawString(13.0 * cm, y, "Cumpl.")
   c.drawString(15.2 * cm, y, "Res. Pond.")
   c.setFont("Helvetica", 9)
   y -= 0.5 * cm
   # limitar filas para que no se salga (si hay muchas, corta y sigue en otra página)
   max_rows_per_page = 28
   rows = df[["Funcion", "Peso", "Cumplimiento", "ResultadoPonderado"]].copy()
   for i, r in rows.iterrows():
       if (i > 0) and (i % max_rows_per_page == 0):
           c.showPage()
           y = h - 2 * cm
           c.setFont("Helvetica-Bold", 12)
           c.drawString(2 * cm, y, "Detalle (continuación)")
           y -= 1 * cm
           c.setFont("Helvetica", 9)
       funcion = str(r["Funcion"])[:60]
       c.drawString(2 * cm, y, funcion)
       c.drawRightString(12.2 * cm, y, f"{r['Peso']:.2f}")
       c.drawRightString(14.4 * cm, y, f"{r['Cumplimiento']:.2f}")
       c.drawRightString(17.8 * cm, y, f"{r['ResultadoPonderado']:.2f}")
       y -= 0.45 * cm
   c.showPage()
   c.save()
   buffer.seek(0)
   return buffer.read()
# ---------------------------
# UI
# ---------------------------
st.title("Calificación")
st.caption("Periodo evaluado: **octubre – diciembre**")
st.sidebar.header("Entrada")
archivo = st.sidebar.file_uploader("Sube el Excel de evaluación", type=["xlsx"])
ruta_default = "Formato_Evaluacion_Ponderada.xlsx"
usar_default = st.sidebar.checkbox("Usar archivo local si existe", value=True)
xls = None
if archivo is not None:
   xls = pd.ExcelFile(archivo)
elif usar_default:
   try:
       xls = pd.ExcelFile(ruta_default)
       st.sidebar.success(f"Usando archivo local: {ruta_default}")
   except:
       xls = None
if xls is None:
   st.info("Sube el archivo Excel para iniciar el análisis.")
   st.stop()
sheets = xls.sheet_names
abogado_sheets = [s for s in sheets if s.strip().upper() != "CALIFICACIÓN"]
st.sidebar.header("Vista")
modo = st.sidebar.radio("Qué quieres ver", ["Resumen general", "Detalle por abogado", "Comparar abogados"])
periodo = "Octubre – Diciembre"
# ---------------------------
# Resumen general (incluye semáforo + top/bottom)
# ---------------------------
if modo == "Resumen general":
   if "CALIFICACIÓN" in sheets:
       df_gen = leer_calificacion_general(xls)
       df_gen["Semáforo"] = df_gen["RESULTADO_PONDERADO"].apply(_semaforo)
       col1, col2 = st.columns([2.2, 1])
       with col1:
           st.subheader("Resultados globales (hoja CALIFICACIÓN)")
           st.dataframe(df_gen, use_container_width=True)
       with col2:
           promedio = float(np.nanmean(df_gen["RESULTADO_PONDERADO"]))
           minimo = float(np.nanmin(df_gen["RESULTADO_PONDERADO"]))
           maximo = float(np.nanmax(df_gen["RESULTADO_PONDERADO"]))
           st.metric("Promedio (%)", f"{promedio:.2f}")
           st.metric("Mínimo (%)", f"{minimo:.2f}")
           st.metric("Máximo (%)", f"{maximo:.2f}")
       st.subheader("Ranking")
       df_rank = df_gen.sort_values("RESULTADO_PONDERADO", ascending=False).reset_index(drop=True)
       fig = px.bar(df_rank, x="FUNCIONARIO", y="RESULTADO_PONDERADO", title="Resultado ponderado por funcionario (%)")
       fig.update_layout(xaxis_tickangle=-45, height=520)
       st.plotly_chart(fig, use_container_width=True)
       cA, cB = st.columns(2)
       with cA:
           st.markdown("### Top 5")
           st.dataframe(df_rank.head(5), use_container_width=True)
       with cB:
           st.markdown("### Bottom 5")
           st.dataframe(df_rank.tail(5).sort_values("RESULTADO_PONDERADO"), use_container_width=True)
   else:
       st.warning("No encontré la hoja 'CALIFICACIÓN'. Puedes usar 'Comparar abogados' para construir un ranking desde las hojas.")
# ---------------------------
# Detalle por abogado + PDF
# ---------------------------
elif modo == "Detalle por abogado":
   abogado = st.sidebar.selectbox("Selecciona abogado (hoja)", abogado_sheets)
   data = leer_hoja_abogado(xls, abogado)
   df = data["detalle"]
   resultado_final = data["resultado_final"]
   suma_pesos = data["suma_pesos"]
   c1, c2 = st.columns([2.2, 1])
   with c1:
       st.subheader(f"Detalle de funciones – {abogado}")
       st.dataframe(df, use_container_width=True)
   with c2:
       st.subheader("Resultado")
       st.metric("Resultado Final (%)", f"{resultado_final:.2f}")
       st.write(f"Semáforo: **{_semaforo(resultado_final)}**")
       st.write(f"Suma de pesos: **{suma_pesos:.2f}%**")
       if abs(suma_pesos - 100) > 0.5:
           st.warning("Ojo: la suma de pesos no está cerca de 100%. Revisa si los pesos están bien en esa hoja.")
       # PDF
       pdf_bytes = generar_pdf_abogado(abogado, periodo, resultado_final, suma_pesos, df)
       st.download_button(
           "Descargar PDF del abogado",
           data=pdf_bytes,
           file_name=f"Calificacion_{abogado}.pdf",
           mime="application/pdf"
       )
   st.subheader("Gráficas del desempeño")
   colA, colB, colC = st.columns(3)
   with colA:
       fig1 = px.bar(df, x="Funcion", y="Peso", title="Peso (%) por función")
       fig1.update_layout(xaxis_tickangle=-30, height=420)
       st.plotly_chart(fig1, use_container_width=True)
   with colB:
       fig2 = px.bar(df, x="Funcion", y="Cumplimiento", title="Cumplimiento (%) por función")
       fig2.update_layout(xaxis_tickangle=-30, height=420)
       st.plotly_chart(fig2, use_container_width=True)
   with colC:
       fig3 = px.bar(df, x="Funcion", y="ResultadoPonderado", title="Resultado ponderado (%) por función")
       fig3.update_layout(xaxis_tickangle=-30, height=420)
       st.plotly_chart(fig3, use_container_width=True)
   st.markdown("### Explicación (qué hace el app)")
   st.write(
       """
- Lee la hoja del abogado y toma la tabla **Función / Peso / Cumplimiento / Resultado Ponderado**.
- Convierte textos como `30%` o `0.92` a números.
- Detecta si los valores están en escala **0–1** y los convierte automáticamente a **0–100**.
- Si el **Resultado Ponderado** viene vacío, lo calcula como: **Peso × Cumplimiento / 100**.
- Obtiene el **Resultado Final (%)** desde la fila final si existe; si no, suma los resultados ponderados.
- Genera el PDF con: encabezado, periodo, semáforo, suma de pesos y la tabla.
"""
   )
# ---------------------------
# Comparar abogados (desde hojas) + semáforo + export opcional
# ---------------------------
else:
   seleccion = st.sidebar.multiselect("Selecciona abogados", abogado_sheets, default=abogado_sheets[:5])
   if not seleccion:
       st.info("Selecciona al menos un abogado.")
       st.stop()
   filas = []
   for ab in seleccion:
       d = leer_hoja_abogado(xls, ab)
       filas.append({
           "Abogado": ab,
           "ResultadoFinal": d["resultado_final"],
           "Semáforo": _semaforo(d["resultado_final"]),
           "SumaPesos": d["suma_pesos"],
       })
   df_comp = pd.DataFrame(filas).sort_values("ResultadoFinal", ascending=False).reset_index(drop=True)
   st.subheader(f"Comparación de resultados finales ({periodo})")
   st.dataframe(df_comp, use_container_width=True)
   figc = px.bar(df_comp, x="Abogado", y="ResultadoFinal", title="Resultado Final (%) por abogado")
   figc.update_layout(xaxis_tickangle=-45, height=520)
   st.plotly_chart(figc, use_container_width=True)
   cA, cB = st.columns(2)
   with cA:
       st.markdown("### Top 5")
       st.dataframe(df_comp.head(5), use_container_width=True)
   with cB:
       st.markdown("### Bottom 5")
       st.dataframe(df_comp.tail(5).sort_values("ResultadoFinal"), use_container_width=True)
   st.caption("Nota: esta comparación se arma leyendo cada hoja de abogado (aunque no exista CALIFICACIÓN).")

   # Encabezado con imágenes
# ---------------------------
c1, c2, c3 = st.columns([1, 4, 1])



   