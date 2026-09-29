"""Persistencia final: red de notas Markdown para Obsidian.

No se usa SQLite, MongoDB ni Neo4j. Cada noticia y cada entidad debe
tener su propia nota, enlazada con [[wiki-links]].
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from pathlib import Path

from src.config import DIR_VAULT
from src.excepciones import EtapaPendienteAlumno
from src.conocimiento.utilidades import slugify, enlace_obsidian

CARPETAS_ENTIDADES = ["Delitos", "Personas", "Organizaciones", "Lugares", "Objetos", "Relaciones"]


class EscritorObsidian(ABC):
    """Contrato para generar la bóveda a partir de JSON validado."""

    @abstractmethod
    def escribir_noticia(self, data: dict) -> Path:
        """Crea obsidian_vault/Noticias/{id_noticia}.md con frontmatter y enlaces."""

    @abstractmethod
    def escribir_entidades(self, noticias: list[dict]) -> None:
        """Agrega notas de delitos, personas, organizaciones, lugares y objetos."""

    @abstractmethod
    def escribir_indice(self, noticias: list[dict]) -> Path:
        """Crea obsidian_vault/00_Indice.md."""

    @abstractmethod
    def escribir_vault(self, noticias: list[dict]) -> None:
        """Orquesta noticia + entidades + índice."""


class EscritorVaultObsidian(EscritorObsidian):
    """Implementación objetivo del laboratorio.

    Use src.conocimiento.utilidades.slugify y enlace_obsidian.
    Jerarquía esperada:
        obsidian_vault/
        ├── 00_Indice.md
        ├── Noticias/
        ├── Delitos/
        ├── Personas/
        ├── Organizaciones/
        ├── Lugares/
        ├── Objetos/
        └── Relaciones/
    """

    def __init__(self, vault: Path = DIR_VAULT) -> None:
        self.vault = Path(vault)



    def escribir_noticia(self, data: dict) -> Path:
        id_noticia = data["id_noticia"]
        titulo = data.get("titulo") or id_noticia

        lineas = [
            "---",
            f"id_noticia: {id_noticia}",
            f"fuente: {data.get('fuente') or 'desconocida'}",
            f"fecha_publicacion: {data.get('fecha_publicacion') or 'sin fecha'}",
            f"url: {data.get('url') or ''}",
            "---",
            "",
            f"# {titulo}",
            "",
            data.get("resumen") or "_Sin resumen disponible._",
            "",
        ]
        lineas += self._seccion(
            "Delitos", [(d, None) for d in (data.get("delitos") or []) if d]
        )
        lineas += self._seccion(
            "Personas",
            [(p["nombre"], p.get("rol")) for p in (data.get("personas") or []) if p.get("nombre")],
        )
        lineas += self._seccion(
            "Organizaciones", [(o, None) for o in (data.get("organizaciones") or []) if o]
        )
        lineas += self._seccion(
            "Lugares", [(l, None) for l in (data.get("lugares") or []) if l]
        )
        lineas += self._seccion(
            "Objetos",
            [
                (o.get("nombre") or o.get("tipo"), f"cantidad: {o['cantidad']}" if o.get("cantidad") else None)
                for o in (data.get("objetos") or [])
                if (o.get("nombre") or o.get("tipo"))
            ],
        )

        relaciones = [r for r in (data.get("relaciones") or []) if r.get("origen") and r.get("destino")]
        if relaciones:
            lineas += ["## Relaciones", ""]
            for r in relaciones:
                origen = enlace_obsidian(slugify(r["origen"]))
                destino = enlace_obsidian(slugify(r["destino"]))
                tipo = r.get("tipo") or "relacionado_con"
                lineas.append(f"- {origen} —{tipo}→ {destino} ({enlace_obsidian(slugify(tipo))})")
            lineas.append("")

        ruta = self.vault / "Noticias" / f"{id_noticia}.md"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
        return ruta

    @staticmethod
    def _seccion(titulo: str, pares: list[tuple[str, str | None]]) -> list[str]:
        if not pares:
            return []
        lineas = [f"## {titulo}", ""]
        for nombre, extra in pares:
            sufijo = f" ({extra})" if extra else ""
            lineas.append(f"- {enlace_obsidian(slugify(nombre))}{sufijo}")
        lineas.append("")
        return lineas



 
    def escribir_entidades(self, noticias: list[dict]) -> None:
        apariciones: dict[str, dict[str, list[str]]] = {
            c: defaultdict(list) for c in CARPETAS_ENTIDADES
        }
        nombres_originales: dict[str, dict[str, str]] = {c: {} for c in CARPETAS_ENTIDADES}

        for noticia in noticias:
            id_noticia = noticia["id_noticia"]

            for delito in noticia.get("delitos") or []:
                self._acumular(apariciones, nombres_originales, "Delitos", delito, id_noticia)

            for persona in noticia.get("personas") or []:
                nombre = persona.get("nombre")
                if not nombre:
                    continue
                rol = persona.get("rol") or "rol desconocido"
                self._acumular(
                    apariciones, nombres_originales, "Personas", nombre, id_noticia, extra=f"({rol})"
                )

            for org in noticia.get("organizaciones") or []:
                self._acumular(apariciones, nombres_originales, "Organizaciones", org, id_noticia)

            for lugar in noticia.get("lugares") or []:
                self._acumular(apariciones, nombres_originales, "Lugares", lugar, id_noticia)

            for objeto in noticia.get("objetos") or []:
                nombre = objeto.get("nombre") or objeto.get("tipo")
                if not nombre:
                    continue
                self._acumular(apariciones, nombres_originales, "Objetos", nombre, id_noticia)

            for rel in noticia.get("relaciones") or []:
                tipo = rel.get("tipo")
                if not tipo:
                    continue
                detalle = f"{enlace_obsidian(slugify(rel.get('origen') or ''))} → {enlace_obsidian(slugify(rel.get('destino') or ''))}"
                self._acumular(
                    apariciones, nombres_originales, "Relaciones", tipo, id_noticia, extra=detalle
                )

        for carpeta in CARPETAS_ENTIDADES:
            carpeta_path = self.vault / carpeta
            carpeta_path.mkdir(parents=True, exist_ok=True)
            for slug, lineas_apariciones in apariciones[carpeta].items():
                nombre_original = nombres_originales[carpeta][slug]
                contenido = [f"# {nombre_original}", "", "## Apariciones", ""]
                contenido.extend(lineas_apariciones)
                contenido.append("")
                (carpeta_path / f"{slug}.md").write_text("\n".join(contenido) + "\n", encoding="utf-8")

    @staticmethod
    def _acumular(apariciones, nombres_originales, carpeta, nombre, id_noticia, extra=None):
        slug = slugify(nombre)
        nombres_originales[carpeta][slug] = nombre
        sufijo = f" — {extra}" if extra else ""
        apariciones[carpeta][slug].append(f"- {enlace_obsidian(id_noticia)}{sufijo}")



    def escribir_indice(self, noticias: list[dict]) -> Path:
        lineas = ["# Índice — Laboratorio Noticias Delictuales", "", "## Noticias", ""]
        for noticia in sorted(noticias, key=lambda n: n["id_noticia"]):
            lineas.append(f"- {enlace_obsidian(noticia['id_noticia'])} — {noticia.get('titulo') or ''}")
        lineas.append("")

        for carpeta in CARPETAS_ENTIDADES:
            carpeta_path = self.vault / carpeta
            lineas.append(f"## {carpeta}")
            lineas.append("")
            if carpeta_path.exists():
                for ruta in sorted(carpeta_path.glob("*.md")):
                    lineas.append(f"- {enlace_obsidian(ruta.stem)}")
            lineas.append("")

        ruta = self.vault / "00_Indice.md"
        ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
        return ruta




    def escribir_vault(self, noticias: list[dict]) -> None:
        self.vault.mkdir(parents=True, exist_ok=True)
        for carpeta in ["Noticias", *CARPETAS_ENTIDADES]:
            (self.vault / carpeta).mkdir(parents=True, exist_ok=True)

        for noticia in noticias:
            self.escribir_noticia(noticia)

        self.escribir_entidades(noticias)
        self.escribir_indice(noticias)