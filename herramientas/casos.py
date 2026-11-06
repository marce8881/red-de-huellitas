#!/usr/bin/env python3
"""Red de Huellitas: la carga privada de casos (privado/casos-carga.json) -> casos.json.

privado/ está en .gitignore: ahí viven la carga (todas las filas, del chat y del Form, con su
moderación), las descargas de la Sheet, los originales del chat y los recortes de fotos.

  casos.py importar-sheet XLSX        suma a la carga las respuestas del Form que aún no tiene
  casos.py agregar < caso.json        agrega un caso (o lista de casos) del chat
  casos.py editar ID campo=valor ...  corrige campos de un caso (el reporte, no sus novedades)
  casos.py recortar ORIGEN ID N X Y W H   recorta la foto N (sips -> privado/fotos/ID/foto-N.jpg)
  casos.py listar                     resumen de la carga
  casos.py comparar                   qué cambiaría en casos.json, sin escribir nada
  casos.py publicar                   escribe casos.json y copia las fotos a casos/

Las columnas son las de la Sheet; `aprobado`, `id_caso`, `contacto_publico`, `fecha_cierre` y
`nota_interna` son de moderación. Sólo usa la librería estándar (openpyxl para importar-sheet).
"""
import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import sheet_to_json as s2j

PRIVADO = s2j.PRIVADO
DATOS = PRIVADO / "casos-carga.json"
FOTOS = PRIVADO / "fotos"

# Mismo orden que la Sheet (+ moderación). La 2.ª "¿Cómo está ahora?" es la de Novedades.
COLUMNAS = [
    "Marca temporal", "¿Qué quieres reportar?", "¿Es perrito, gatito u otra mascota?",
    "¿Cómo se llama? (si tiene nombre)", "¿Cómo es?", "¿Es macho o hembra?",
    "¿Qué edad tiene más o menos?", "¿Cómo está de salud?",
    "¿Cuándo fue rescatada o cuándo se perdió? (si lo sabes)",
    "¿En qué zona o privada está o se perdió? (si lo sabes)", "¿Cómo está ahora?",
    "¿Dónde está ahora?", "¿Quién la cuida ahora?", "¿Se canalizó a APAQRO?",
    "¿A qué mascota viste?", "¿Dónde la viste?", "¿Cuándo la viste?", "¿Cómo la viste?",
    "¿De qué mascota se trata?", "¿Cómo está ahora? (novedades)", "¿Desde cuándo?", "Cuéntanos más",
    "Tu nombre", "Tu WhatsApp (no se publica)",
    "Si este caso lo viste en el grupo, ¿quién lo compartió?", "¿Qué día lo compartió?",
    "Foto de la mascota", "Privacidad",
    "aprobado", "id_caso", "contacto_publico", "fecha_cierre", "nota_interna",
]
DEFAULTS = {
    "Tu nombre": "Marcela Cadena",
    "Privacidad": "Entiendo que mis datos de contacto no se publican y que quien quiera saber de la "
                  "mascota contactará a la administradora de Red de Huellitas.",
}
FOTO_SI = ('Autorizo que se publique en la página la foto de la mascota que comparta en el grupo de '
           'WhatsApp "Mascotas Condado".')
# Encabezados de la Sheet que no están en PREGUNTAS o vienen con otro texto.
ALIAS = {"fecha_cirre": "fecha_cierre", "tu nombre": "Tu nombre",
         "tu whatsapp (no se publica)": "Tu WhatsApp (no se publica)", "privacidad": "Privacidad",
         "nota_interna": "nota_interna"}


def cargar():
    if DATOS.exists():
        return json.loads(DATOS.read_text(encoding="utf-8"))
    return {"casos": []}


def guardar(d):
    PRIVADO.mkdir(exist_ok=True)
    DATOS.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def reportes(d, id_caso):
    """Filas de rescate o pérdida con ese id (la que crea el caso, no sus novedades)."""
    return [c for c in d["casos"] if c.get("id_caso") == id_caso
            and s2j.tipo(c.get("¿Qué quieres reportar?")) in ("rescate", "perdida")]


def siguiente_id(d):
    nums = [int(c["id_caso"].rsplit("-", 1)[1]) for c in d["casos"] if c.get("id_caso")]
    return f"{datetime.now():%Y-%m}-{max(nums, default=0) + 1:03d}"


def texto(v):
    if isinstance(v, datetime):
        return v.strftime("%d/%m/%Y %H:%M:%S")
    if isinstance(v, date):
        return v.strftime("%d/%m/%Y")
    return "" if v is None else str(v).strip()


def a_filas(d):
    """Carga -> filas con las claves internas de sheet_to_json."""
    filas = []
    for c in d["casos"]:
        r = {}
        for col, valor in c.items():
            clave = s2j.claves([col])[0] if not col.startswith("_") else ""
            v = texto(valor)
            if clave and v and not r.get(clave):
                r[clave] = v
        filas.append(r)
    return filas


def cmd_importar_sheet(args):
    from openpyxl import load_workbook
    ws = load_workbook(args[0], read_only=True).worksheets[0]
    filas = list(ws.iter_rows(values_only=True))
    # Encabezado de la Sheet -> nombre de columna de la carga (por la clave interna o por alias).
    por_clave = dict(zip(s2j.claves(COLUMNAS), COLUMNAS))
    destino = []
    for h, clave in zip(filas[0], s2j.claves([texto(h) for h in filas[0]])):
        destino.append(por_clave.get(clave) if clave else ALIAS.get(s2j.norm(texto(h))))
    d = cargar()
    vistas = {c.get("Marca temporal") for c in d["casos"]}
    nuevas = 0
    for fila in filas[1:]:
        r = {col: texto(v) for col, v in zip(destino, fila) if col and texto(v)}
        if not r.get("Marca temporal") or r["Marca temporal"] in vistas:
            continue
        r["_origen"] = "form"
        d["casos"].append(r)
        nuevas += 1
        print("nueva del Form:", r["Marca temporal"], "·", r.get("¿Qué quieres reportar?", ""),
              "·", r.get("¿Cómo se llama? (si tiene nombre)") or r.get("¿De qué mascota se trata?") or "")
    guardar(d)
    print(f"{nuevas} respuestas nuevas (quedan sin aprobar hasta moderarlas)")


def cmd_agregar(_):
    entrada = json.load(sys.stdin)
    d = cargar()
    for c in entrada if isinstance(entrada, list) else [entrada]:
        desconocidos = {k for k in c if not k.startswith("_")} - set(COLUMNAS)
        if desconocidos:
            sys.exit(f"Campos que no son columnas: {sorted(desconocidos)}")
        if c.get("Foto de la mascota") in ("sí", "si", True):
            c["Foto de la mascota"] = FOTO_SI
        nuevo = {**DEFAULTS, **c}
        nuevo.setdefault("Marca temporal", f"{datetime.now():%d/%m/%Y %H:%M:%S}")
        nuevo.setdefault("id_caso", siguiente_id(d))
        nuevo.setdefault("_origen", "chat")
        d["casos"].append(nuevo)
        print(nuevo["id_caso"], nuevo.get("¿Cómo se llama? (si tiene nombre)") or "(sin nombre)")
    guardar(d)


def cmd_editar(args):
    d = cargar()
    encontrados = reportes(d, args[0])
    if len(encontrados) != 1:
        sys.exit(f"Esperaba 1 reporte para {args[0]} y encontré {len(encontrados)}")
    c = encontrados[0]
    for par in args[1:]:
        campo, _, valor = par.partition("=")
        if campo not in COLUMNAS:
            sys.exit(f"Campo desconocido: {campo}")
        c[campo] = FOTO_SI if campo == "Foto de la mascota" and valor in ("sí", "si") else valor
    guardar(d)
    print("ok", args[0])


def cmd_recortar(args):
    origen, id_caso, n, x, y, w, h = args
    destino = FOTOS / id_caso / f"foto-{n}.jpg"
    destino.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["sips", "-c", h, w, "--cropOffset", y, x, "-s", "format", "jpeg",
                    "-s", "formatOptions", "80", origen, "--out", str(destino)],
                   check=True, stdout=subprocess.DEVNULL)
    # Lado mayor a 800 px como máximo (sips -Z no agranda): la guía pide fotos de ~150 KB.
    subprocess.run(["sips", "-Z", "800", str(destino)], check=True, stdout=subprocess.DEVNULL)
    print(destino.relative_to(s2j.RAIZ), f"{destino.stat().st_size // 1024} KB")


def cmd_listar(_):
    for c in cargar()["casos"]:
        print(c.get("id_caso") or "—", s2j.tipo(c.get("¿Qué quieres reportar?")) or "?",
              c.get("¿Cómo se llama? (si tiene nombre)") or "(sin nombre)",
              "aprobado=" + (c.get("aprobado") or "—"), sep=" · ")


def cmd_comparar(_):
    nuevo = s2j.generar(a_filas(cargar()), FOTOS, escribir=False)
    actual = json.loads(s2j.SALIDA.read_text(encoding="utf-8")) if s2j.SALIDA.exists() else {"casos": []}
    viejos = {c["id_caso"]: c for c in actual["casos"]}
    nuevos = {c["id_caso"]: c for c in nuevo["casos"]}
    iguales = True
    for idc in sorted(viejos.keys() | nuevos.keys()):
        a, b = viejos.get(idc), nuevos.get(idc)
        if a == b:
            continue
        iguales = False
        if not a or not b:
            print(f"{idc}: {'NUEVO' if b else 'SE QUITARÍA'}")
            continue
        for k in sorted(a.keys() | b.keys()):
            if a.get(k) != b.get(k):
                print(f"{idc} · {k}\n   hoy:   {a.get(k)!r}\n   queda: {b.get(k)!r}")
    print("sin cambios en los casos" if iguales else "")


def cmd_publicar(_):
    s2j.generar(a_filas(cargar()), FOTOS)


COMANDOS = {"importar-sheet": cmd_importar_sheet, "agregar": cmd_agregar, "editar": cmd_editar,
            "recortar": cmd_recortar, "listar": cmd_listar, "comparar": cmd_comparar,
            "publicar": cmd_publicar}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMANDOS:
        sys.exit(__doc__)
    COMANDOS[sys.argv[1]](sys.argv[2:])
