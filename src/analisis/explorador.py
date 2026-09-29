"""Data Understanding sobre el corpus estructurado.

TODO(alumno): las visualizaciones no son decoración; deben revelar
cobertura, sesgos y problemas de calidad (nulos, JSON inválidos, nombres
inconsistentes).
"""

from __future__ import annotations
import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

from src.config import DIR_JSON

from src.excepciones import EtapaPendienteAlumno


class ExploradorDatos:
    """Estadísticas y gráficos mínimos del laboratorio."""
    def __init__(self, dir_json: Path = DIR_JSON) -> None:
        self.dir_json = Path(dir_json)
        self.df = self._cargar_datos()

        sns.set_theme(style="whitegrid")

    def _cargar_datos(self) -> pd.DataFrame:
        datos = []
        if self.dir_json.exists():
            for ruta in self.dir_json.glob("*.json"):
                try:
                    with open(ruta, "r", encoding="utf-8") as f:
                        datos.append(json.load(f))
                except Exception as e:
                    print(f"Error cargando {ruta.name}: {e}")
        return pd.DataFrame(datos)

    def noticias_por_fuente(self) -> None:
        # TODO(alumno): gráfico de barras con pandas + matplotlib.
        if self.df.empty or "fuente" not in self.df.columns:
            return
        
        plt.figure(figsize=(10, 6))
        conteo = self.df["fuente"].value_counts()
        sns.barplot(x=conteo.values, y=conteo.index, hue=conteo.index, legend=False, palette="Blues_r")
        
        plt.title("Cobertura: Cantidad de Noticias por Fuente", fontsize=14)
        plt.xlabel("Número de Noticias")
        plt.ylabel("Medio de Comunicación")
        plt.tight_layout()
        plt.show()


    def delitos_frecuentes(self) -> None:
        # TODO(alumno): top 10 delitos a partir de data/json/*.json.
        if self.df.empty or "delitos" not in self.df.columns:
            return
            
        delitos_aplanados = self.df.explode("delitos")["delitos"].dropna()
        top_10 = delitos_aplanados.value_counts().head(10)
        
        plt.figure(figsize=(10, 6))
        sns.barplot(x=top_10.values, y=top_10.index, hue=top_10.index, legend=False, palette="Reds_r")
        
        plt.title("Top 10 Delitos Más Frecuentes", fontsize=14)
        plt.xlabel("Frecuencia de Mención")
        plt.ylabel("Tipo de Delito")
        plt.tight_layout()
        plt.show()


    def lugares_frecuentes(self) -> None:
        if self.df.empty or "lugares" not in self.df.columns:
            return
            
        lugares_aplanados = self.df.explode("lugares")["lugares"].dropna()
        top_lugares = lugares_aplanados.value_counts().head(10)

        plt.figure(figsize=(10, 6))
        sns.barplot(x=top_lugares.values, y=top_lugares.index, hue=top_lugares.index, legend=False, palette="Oranges_r")
        
        plt.title("Top 10 Lugares/Comunas Más Mencionados", fontsize=14)
        plt.xlabel("Frecuencia")
        plt.ylabel("Lugar")
        plt.tight_layout()
        plt.show()

    def campos_faltantes(self) -> None:
            if self.df.empty:
                return
                
            porcentajes = {}
            
            for col in self.df.columns:
                es_nulo = self.df[col].apply(lambda x: len(x) == 0 if isinstance(x, list) else pd.isna(x))
                
                pct = es_nulo.mean() * 100
                if pct > 0:
                    porcentajes[col] = pct
                    
            faltantes = pd.Series(porcentajes).sort_values(ascending=False)
            
            if faltantes.empty:
                print("Excelente calidad de datos: No hay campos faltantes ni vacíos.")
                return

            plt.figure(figsize=(10, 6))
            sns.barplot(x=faltantes.values, y=faltantes.index, hue=faltantes.index, legend=False, palette="magma")
            
            plt.title("Problemas de Calidad: Porcentaje de Campos Faltantes/Vacíos", fontsize=14)
            plt.xlabel("Porcentaje (%)")
            plt.ylabel("Campo del JSON")
            plt.tight_layout()
            plt.show()


    def evolucion_temporal(self) -> None:
        if self.df.empty or "fecha_publicacion" not in self.df.columns:
            return
            
        df_temp = self.df.copy()
        df_temp["fecha_publicacion"] = pd.to_datetime(df_temp["fecha_publicacion"], errors="coerce")
        df_temp = df_temp.dropna(subset=["fecha_publicacion"])
        
        if df_temp.empty:
            print("No hay fechas válidas para graficar la evolución temporal.")
            return
            
        df_temp["mes"] = df_temp["fecha_publicacion"].dt.to_period("M")
        conteo_mensual = df_temp["mes"].value_counts().sort_index()

        plt.figure(figsize=(10, 6))
        conteo_mensual.plot(kind="line", marker="o", color="teal", linewidth=2)
        
        plt.title("Evolución Temporal de las Noticias Extraídas", fontsize=14)
        plt.xlabel("Mes de Publicación")
        plt.ylabel("Cantidad de Noticias")
        plt.grid(True, linestyle="--", alpha=0.7)
        plt.tight_layout()
        plt.show()


    def ejecutar(self) -> None: #Recordar analizar los gráficos generados y documentarlos en el informe!!!
        """Corre todas las visualizaciones pedidas en la guía."""
        if self.df.empty:
            print("Error: El DataFrame está vacío. Asegurarse de haber ejecutado la etapa de extracción y que existan archivos JSON.")
            return
            
        print(f"Datos cargados: {len(self.df)} noticias. Generando gráficos...")
        
        self.noticias_por_fuente()
        self.delitos_frecuentes()
        self.lugares_frecuentes()
        self.campos_faltantes()
        self.evolucion_temporal()

        
