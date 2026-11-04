#!/usr/bin/env python3
"""Red de Huellitas: CSV de la Sheet privada -> casos.json público (+ fotos).

Uso (desde la raíz del repo):
  python3 herramientas/sheet_to_json.py ~/Downloads/respuestas.csv
  python3 herramientas/sheet_to_json.py ~/Downloads/respuestas.csv --fotos ~/ruta/fotos-casos

- Sólo publica filas con `aprobado = sí` y con `id_caso`.
- Reportes de rescate/perdida crean el caso; "La vi por aquí" y "Novedades" se suman al caso
  con el mismo `id_caso`. La novedad más reciente fija el estado.
- Nunca escribe: nombre ni WhatsApp de quien reporta, quién lo compartió, nota_interna,
  consentimientos ni Privacidad. El contacto de quien cuida sólo si `contacto_publico = sí`.
- Fotos: sólo si el caso autorizó foto. Con --fotos copia `<id_caso>/foto-*.jpg` a `casos/`;
  borra de `casos/` las carpetas de casos que ya no se publican o sin permiso de foto.
- Si encuentra un número de teléfono fuera de un contacto público, NO escribe nada y avisa.

Sólo usa la librería estándar de Python (3.9+).
"""
import argparse
import csv
import json
import re
import shutil
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "casos.json"
FOTOS_WEB = RAIZ / "casos"

# Encabezado de la Sheet (texto de la pregunta) -> clave interna.
# "¿Cómo está ahora?" aparece dos veces: la 1.ª es P10 (sección 2), la 2.ª es P19 (novedades).
PREGUNTAS = {
    "marca temporal": "fecha_reporte",
    "¿qué quieres reportar?": "tipo",
    "¿es perrito, gatito u otra mascota?": "especie",
    "¿cómo se llama? (si tiene nombre)": "nombre",
    "¿cómo es?": "descripcion",
    "¿es macho o hembra?": "sexo",
    "¿qué edad tiene más o menos?": "edad",
    "¿cómo está de salud?": "salud",
    "¿cuándo fue rescatada o cuándo se perdió? (si lo sabes)": "fecha_evento",
    "¿en qué zona o privada está o se perdió? (si lo sabes)": "zona",
    "¿cómo está ahora? (novedades)": "estado_novedad",
    "¿dónde está ahora?": "ubicacion",
    "¿quién la cuida ahora?": "contacto_cuidador",
    "¿se canalizó a apaqro?": "canalizado_apaqro",
    "¿a qué mascota viste?": "caso_referido",
    "¿dónde la viste?": "zona_vista",
    "¿cuándo la viste?": "fecha_vista",
    "¿cómo la viste?": "comentario_vista",
    "¿de qué mascota se trata?": "caso_referido",
    "¿desde cuándo?": "fecha_novedad",
    "cuéntanos más": "comentario_novedad",
    "si este caso lo viste en el grupo, ¿quién lo compartió?": "compartido_por",
    "¿qué día lo compartió?": "fecha_compartido",
    "foto de la mascota": "consentimiento_foto",
    "aprobado": "aprobado",
    "id_caso": "id_caso",
    "contacto_publico": "contacto_publico",
    "fecha_cierre": "fecha_cierre",
}
# Lo que nunca sale del script (se lee sólo para decidir).
PRIVADAS = {"compartido_por", "consentimiento_foto", "aprobado", "contacto_publico", "caso_referido"}

ESTADOS = [  # (prefijo de la opción del Form, etiqueta en la página)
    ("perdida", "Perdida"),
    ("en recuperación", "En recuperación"),
    ("en seguimiento", "En seguimiento"),
    ("buscando familia", "Buscando familia"),
    ("en proceso de adopción", "En proceso de adopción"),
    ("adoptada", "Adoptada"),
    ("ya volvió a casa", "Ya volvió a casa"),
]
SIN_ESTADO = "Por confirmar"
TELEFONO = re.compile(r"(?:\+?52[\s-]*)?(?:\d[\s-]*){10}")


def norm(s):
    return unicodedata.normalize("NFC", (s or "").strip()).lower()


def si(valor):
    return norm(valor) in {"sí", "si", "x", "yes", "true", "1"}


def fecha_iso(valor):
    """'02/10/2026', '2/10/2026 20:24:00' o '2026-10-02' -> '2026-10-02'. Vacío si no se entiende."""
    v = (valor or "").strip()
    if not v:
        return ""
    v = v.split(" ")[0]
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(v, fmt).date().isoformat()
        except ValueError:
            pass
    print(f"  ⚠ fecha que no entiendo: {valor!r} (queda vacía)")
    return ""


def estado(valor):
    v = norm(valor)
    for prefijo, etiqueta in ESTADOS:
        if v.startswith(prefijo):
            return etiqueta
    return ""


def tipo(valor):
    v = norm(valor)
    if v.startswith("una mascota rescatada"):
        return "rescate"
    if v.startswith("mi mascota está perdida"):
        return "perdida"
    if v.startswith("vi a una mascota"):
        return "avistamiento"
    if v.startswith("novedades"):
        return "novedad"
    return ""


def leer_csv(ruta):
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        filas = list(csv.reader(f))
    if not filas:
        sys.exit("El CSV está vacío.")
    claves, vistos_estado = [], 0
    for h in filas[0]:
        n = norm(h)
        if n.startswith("¿cómo está ahora?") and n != "¿cómo está ahora? (novedades)":
            vistos_estado += 1
            claves.append("estado" if vistos_estado == 1 else "estado_novedad")
        else:
            claves.append(PREGUNTAS.get(n, ""))  # columnas no listadas se ignoran
    faltan = {"tipo", "aprobado", "id_caso"} - set(claves)
    if faltan:
        sys.exit(f"Al CSV le faltan columnas: {sorted(faltan)}. ¿Es el export de la Sheet?")
    salida = []
    for fila in filas[1:]:
        r = {}
        for clave, valor in zip(claves, fila):
            if clave and valor.strip() and not r.get(clave):
                r[clave] = valor.strip()
        salida.append(r)
    return salida


def construir(filas):
    casos, extras, avisos = {}, [], []
    for i, r in enumerate(filas, start=2):
        if not si(r.get("aprobado")):
            continue
        idc = r.get("id_caso", "")
        t = tipo(r.get("tipo"))
        if not idc:
            avisos.append(f"fila {i}: aprobada pero sin id_caso (no se publica)")
            continue
        if t in ("rescate", "perdida"):
            if idc in casos:
                avisos.append(f"fila {i}: id_caso {idc} repetido en otro reporte de caso (se ignora)")
                continue
            c = {
                "id_caso": idc,
                "tipo_reporte": t,
                "especie": r.get("especie", ""),
                "nombre": r.get("nombre", ""),
                "descripcion": r.get("descripcion", ""),
                "sexo": r.get("sexo", ""),
                "edad": r.get("edad", ""),
                "salud": [s.strip() for s in r.get("salud", "").split(",") if s.strip()],
                "zona": r.get("zona", ""),
                "estado": "Perdida" if t == "perdida" else (estado(r.get("estado")) or SIN_ESTADO),
                "ubicacion": r.get("ubicacion", ""),
                "canalizado_apaqro": r.get("canalizado_apaqro", ""),
                "fecha_reporte": fecha_iso(r.get("fecha_reporte")),
                "fecha_cierre": fecha_iso(r.get("fecha_cierre")),
                "contacto_cuidador": r.get("contacto_cuidador", "") if si(r.get("contacto_publico")) else "",
                "fotos": [],
                "avistamientos": [],
                "novedades": [],
                "_foto_ok": bool(r.get("consentimiento_foto")),
            }
            # Fecha que se muestra: la del evento; si no, cuándo se compartió; si no, el reporte.
            for campo, fuente in (("fecha_evento", "evento"), ("fecha_compartido", "compartido"),
                                  ("fecha_reporte", "reporte")):
                f = fecha_iso(r.get(campo))
                if f:
                    c["fecha"], c["fecha_tipo"] = f, fuente
                    break
            else:
                c["fecha"], c["fecha_tipo"] = "", ""
            casos[idc] = c
        elif t in ("avistamiento", "novedad"):
            extras.append((i, t, idc, r))
        else:
            avisos.append(f"fila {i}: no entiendo '¿Qué quieres reportar?' = {r.get('tipo')!r}")

    for i, t, idc, r in extras:
        c = casos.get(idc)
        if not c:
            avisos.append(f"fila {i}: {t} para {idc}, pero ese caso no está publicado")
            continue
        if t == "avistamiento":
            c["avistamientos"].append({
                "fecha": fecha_iso(r.get("fecha_vista")) or fecha_iso(r.get("fecha_reporte")),
                "zona": r.get("zona_vista", ""),
                "comentario": r.get("comentario_vista", ""),
            })
        else:
            c["novedades"].append({
                "fecha": fecha_iso(r.get("fecha_novedad")) or fecha_iso(r.get("fecha_reporte")),
                "estado": estado(r.get("estado_novedad")),
                "comentario": r.get("comentario_novedad", ""),
            })
        if r.get("fecha_cierre") and not c["fecha_cierre"]:
            c["fecha_cierre"] = fecha_iso(r.get("fecha_cierre"))

    for c in casos.values():
        c["avistamientos"].sort(key=lambda a: a["fecha"])
        c["novedades"].sort(key=lambda n: n["fecha"])
        con_estado = [n for n in c["novedades"] if n["estado"]]
        if con_estado:
            c["estado"] = con_estado[-1]["estado"]
    return casos, avisos


def sincronizar_fotos(casos, fotos_origen):
    FOTOS_WEB.mkdir(exist_ok=True)
    for c in casos.values():
        destino = FOTOS_WEB / c["id_caso"]
        if not c["_foto_ok"]:
            continue
        if fotos_origen:
            origen = fotos_origen / c["id_caso"]
            nuevas = sorted(origen.glob("foto-*.jpg")) if origen.is_dir() else []
            if nuevas:
                destino.mkdir(exist_ok=True)
                for f in nuevas:
                    shutil.copy2(f, destino / f.name)
        if destino.is_dir():
            c["fotos"] = [f"casos/{c['id_caso']}/{f.name}" for f in sorted(destino.glob("foto-*.jpg"))]
    publicadas = {c["id_caso"] for c in casos.values() if c["fotos"]}
    for carpeta in FOTOS_WEB.iterdir():
        if carpeta.is_dir() and carpeta.name not in publicadas:
            shutil.rmtree(carpeta)
            print(f"  fotos quitadas de la página: casos/{carpeta.name}/")


def revisar_privacidad(casos):
    """Devuelve los textos con algo que parece teléfono fuera de contacto_cuidador."""
    hallazgos = []
    for c in casos.values():
        textos = [c["descripcion"], c["nombre"], c["zona"], c["edad"], c["ubicacion"]]
        textos += [x["comentario"] for x in c["avistamientos"] + c["novedades"]]
        textos += [x["zona"] for x in c["avistamientos"]]
        for t in textos:
            if t and TELEFONO.search(t):
                hallazgos.append(f"{c['id_caso']}: {t[:80]}")
    return hallazgos


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("csv", type=Path, help="CSV exportado de la Sheet privada (fuera de este repo)")
    p.add_argument("--fotos", type=Path, help="carpeta con <id_caso>/foto-N.jpg para copiar")
    a = p.parse_args()

    if RAIZ in a.csv.resolve().parents:
        print("  ⚠ El CSV está dentro del repo público. Muévelo fuera (por ejemplo a Descargas).")

    casos, avisos = construir(leer_csv(a.csv))
    for av in avisos:
        print(f"  ⚠ {av}")

    malos = revisar_privacidad(casos)
    if malos:
        print("\n✋ Encontré algo que parece teléfono fuera de un contacto público. No escribí nada:")
        for m in malos:
            print(f"   - {m}")
        sys.exit("Corrige esas celdas en la Sheet, vuelve a exportar y corre otra vez.")

    sincronizar_fotos(casos, a.fotos.expanduser() if a.fotos else None)
    publicos = []
    for c in casos.values():
        c.pop("_foto_ok")
        assert not PRIVADAS & set(c), "campo privado en la salida"
        publicos.append(c)
    publicos.sort(key=lambda c: c["id_caso"])

    datos = {"actualizado": datetime.now().strftime("%Y-%m-%dT%H:%M"), "casos": publicos}
    SALIDA.write_text(json.dumps(datos, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print(f"\ncasos.json: {len(publicos)} casos publicados")
    conteo = {}
    for c in publicos:
        conteo[c["estado"]] = conteo.get(c["estado"], 0) + 1
    for etiqueta in [e for _, e in ESTADOS] + [SIN_ESTADO]:
        if etiqueta in conteo:
            print(f"  {etiqueta}: {conteo[etiqueta]}")
    print(f"  con foto: {sum(1 for c in publicos if c['fotos'])}")


if __name__ == "__main__":
    main()
