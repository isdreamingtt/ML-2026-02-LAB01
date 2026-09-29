"""Extractor Gemini: texto limpio → JSON del contrato del laboratorio.

Implementación mínima y ejecutable. El laboratorio NO inventa datos:
solo se extrae información explícita en la noticia, en JSON válido.

TODO(alumno) — mejoras opcionales, el código ya corre sin ellas:
- reintentos ante 429 / timeouts
- recorte de textos muy largos antes del prompt
"""

from __future__ import annotations

import json
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path
import logging

from src.config import DIR_JSON, GEMINI_API_KEY, GEMINI_MODEL, PAUSA_ENTRE_REQUESTS
from src.modelos import NoticiaFuente


class ExtractorLLM(ABC):
    """Interfaz de cualquier extractor basado en modelo generativo."""

    @abstractmethod
    def construir_prompt(self, noticia: NoticiaFuente) -> str:
        """Arma el prompt con el esquema JSON y el texto de la noticia."""

    @abstractmethod
    def extraer(self, noticia: NoticiaFuente) -> dict:
        """Devuelve un diccionario que cumple el contrato JSON del laboratorio."""


class ExtractorGemini(ExtractorLLM):
    """Extractor oficial del laboratorio (Gemini).

    1. Carga GEMINI_API_KEY desde .env (nunca hardcodear la clave).
    2. Usa el texto ya limpio en noticia.texto_limpio.
    3. Llama al modelo (p. ej. gemini-2.0-flash) con construir_prompt().
    4. Parsea JSON (quita fences markdown si el modelo los agrega).
    5. Guarda data/json/{id_noticia}.json.
    """

    CAMPOS_OBLIGATORIOS = [
        "id_noticia",
        "titulo",
        "fecha_publicacion",
        "fuente",
        "url",
        "resumen",
        "delitos",
        "personas",
        "organizaciones",
        "lugares",
        "objetos",
        "relaciones",
    ]

    def __init__(self, dir_json: Path = DIR_JSON) -> None:
        self.dir_json = dir_json
        self.dir_json.mkdir(parents=True, exist_ok=True)
        self._cliente = None

    def construir_prompt(self, noticia: NoticiaFuente) -> str:
        campos = ", ".join(self.CAMPOS_OBLIGATORIOS)
        texto = (noticia.texto_limpio or "").strip()[:12000]
        return (
            "Eres un analista de inteligencia experto en estructuración de datos.\n"
            "Analiza la siguiente noticia delictual y extrae solamente información explícita. "
            "Bajo ninguna circunstancia inventes o deduzcas datos, entidades, roles ni relaciones.\n"
            "Devuelve EXCLUSIVAMENTE un objeto JSON válido, sin usar markdown (sin bloques ```json), "
            "ni saludos, ni explicaciones previas o posteriores.\n\n"
            f"El JSON DEBE contener exactamente estas claves en el nivel raíz: {campos}.\n\n"
            "Reglas de formato por campo:\n"
            "- resumen: Un párrafo breve (máximo 3 líneas) resumiendo el hecho central.\n"
            "- delitos: Lista de strings con los delitos mencionados.\n"
            "- personas: Lista de objetos con claves 'nombre' y 'rol' (ej. imputado, victima, testigo).\n"
            "- organizaciones: Lista de strings (ej. Carabineros, PDI, bandas).\n"
            "- lugares: Lista de strings (comunas, regiones, calles).\n"
            "- objetos: Lista de objetos con claves 'tipo' (ej. arma, droga), 'nombre', 'cantidad' (usa null si no sale), 'unidad' (usa null si no sale).\n"
            "- relaciones: Lista de objetos con claves 'origen', 'tipo' (ej. INVESTIGADO_POR, OPERA_EN) y 'destino'. "
            "Asegúrate de que 'origen' y 'destino' coincidan exactamente con nombres extraídos en los otros campos.\n"
            "REGLA CRÍTICA: NO OMITAS NINGUNA CLAVE. Tu respuesta DEBE contener exactamente las 12 claves solicitadas en la raíz."
            "Si algún dato no aparece, la clave debe existir obligatoriamente con valor null o [].\n\n"
            "Usa estos datos predefinidos para los metadatos de la noticia:\n"
            f"id_noticia: \"{noticia.id_noticia}\"\n"
            f"fuente: \"{noticia.fuente}\"\n"
            f"url: \"{noticia.url}\"\n\n"
            "NOTICIA:\n"
            f"{texto}\n"
        )

    def extraer(self, noticia: NoticiaFuente) -> dict:
        if not GEMINI_API_KEY:
            raise RuntimeError(
                "Falta GEMINI_API_KEY. Copie .env.example a .env y complete la clave. "
                "Nunca suba .env a GitHub."
            )
        cliente = self._obtener_cliente()
        from google.genai import types
        from google.genai.errors import APIError

        # TODO(alumno): recortar textos muy largos; reintentos ante 429 / timeouts. -> Listo!
        max_intentos = 3
        intento_actual = 0
        bruto = ""

        while intento_actual < max_intentos:
            try:
                respuesta = cliente.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=self.construir_prompt(noticia),
                    config=types.GenerateContentConfig(
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(
                            disable=True
                        ),
                        response_mime_type="application/json",
                        temperature=0,
                    ),
                )
                bruto = (getattr(respuesta, "text", None) or "").strip()
                break
            except APIError as e:
                if(e.code in (429,503)):
                    intento_actual += 1
                    espera = 60 if e.code == 429 else 20
                    logging.warning(f"Error {e.code}. Reintento {intento_actual}/{max_intentos} en {espera} segundos...")
                    time.sleep(espera)
                else:
                    raise
            except Exception as e:
                intento_actual += 1
                logging.warning(f"Error inesperado: {e}. Reintento {intento_actual}/{max_intentos} en 15 segundos...")
                time.sleep(15)

        if not bruto:
            raise ValueError(
                f"Gemini devolvió una respuesta vacía o falló tras los reintentos para {noticia.id_noticia}."
            )
        data = self._parsear_json(bruto)
        data["id_noticia"] = noticia.id_noticia
        if not data.get("fuente"):
            data["fuente"] = noticia.fuente
        if not data.get("url"):
            data["url"] = noticia.url
        ruta = self.dir_json / f"{noticia.id_noticia}.json"
        ruta.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        time.sleep(PAUSA_ENTRE_REQUESTS)
        return data

    def _obtener_cliente(self):
        if self._cliente is None:
            from google import genai

            self._cliente = genai.Client(api_key=GEMINI_API_KEY)
        return self._cliente

    @staticmethod
    def _parsear_json(bruto: str) -> dict:
        texto = bruto.strip()
        cerca = re.search(r"```(?:json)?\s*(.*?)\s*```", texto, re.DOTALL)
        if cerca:
            texto = cerca.group(1)
        try:
            data = json.loads(texto)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Gemini no devolvió JSON válido: {exc}. "
                f"Respuesta: {texto[:300]!r}"
            ) from exc
        if not isinstance(data, dict):
            raise ValueError("La respuesta de Gemini no es un objeto JSON.")
        return data
