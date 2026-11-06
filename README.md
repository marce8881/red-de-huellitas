# Red de Huellitas 🐾

Rescates, adopciones y mascotas perdidas de la comunidad de El Condado (Corregidora, Querétaro),
en un solo lugar y al día. Página 100 % informativa: aquí no se pide ni se maneja dinero.

Página: https://marce8881.github.io/red-de-huellitas/ ·
Reportar una mascota: https://forms.gle/DUsJKwRDwnp5ZUmSA

Proyecto de servicio social (CEFODEH, UVM) de Marcela Cadena con la comunidad de "Mascotas
Condado". #SOYVOLUNTARIOCEFODEH

## Qué hay aquí

| Archivo | Qué es |
|---|---|
| `index.html` | La página. Lee `casos.json` y muestra las tarjetas, los contadores y los filtros. |
| `casos.json` | Los casos aprobados, **sólo con datos públicos**. Lo genera el script. |
| `casos/<id_caso>/foto-N.jpg` | Fotos de las mascotas que tienen permiso de publicarse. |
| `herramientas/casos.py` | Lleva la carga privada de casos e importa la Sheet; `publicar` genera `casos.json`. |
| `herramientas/sheet_to_json.py` | Las reglas de publicación: filtra datos privados, arma `casos.json` y sincroniza las fotos. |
| `privado/` | **No se sube** (está en `.gitignore`). La carga de casos, las descargas de la Sheet, los originales del chat y los recortes de fotos. |
| `assets/banner.jpg` | El banner del cartel. |

Este repo es **público**. La Sheet con las respuestas del formulario es privada y nunca se sube
aquí: `.gitignore` bloquea `privado/` y los archivos CSV y Excel.

## Mantener la página

**Cada ronda de moderación** (Marce aprueba en el chat con Claude; nadie teclea en la Sheet)

La fuente de todos los casos es `privado/casos-carga.json`: una fila por reporte (del chat o del
Form) con su moderación (`aprobado`, `id_caso`, `contacto_publico`, `fecha_cierre`,
`nota_interna`). La Sheet sólo sirve para traer lo que llega por el Form.

1. **Respuestas del Form:** en la Sheet, *Archivo → Descargar → Microsoft Excel (.xlsx)* y guardar
   el archivo en `privado/sheet/`. Luego:
   ```
   python3 herramientas/casos.py importar-sheet "privado/sheet/<archivo>.xlsx"
   ```
   Sólo suma las respuestas que la carga aún no tiene (las reconoce por su marca temporal).
2. **Casos del chat:** las capturas y carteles van a `privado/originales/AAAA-MM-DD/`. Claude los
   revisa, recorta las fotos a `privado/fotos/<id_caso>/foto-N.jpg` y agrega las filas con
   `casos.py agregar` (o corrige con `casos.py editar`).
3. **Aprobación:** Claude muestra en el chat cómo quedaría cada tarjeta y Marce dice sí o no.
   Sólo entonces se pone `aprobado = sí`.
4. `python3 herramientas/casos.py comparar` muestra qué cambiaría sin escribir nada, y
   `python3 herramientas/casos.py publicar` escribe `casos.json` y copia las fotos a `casos/`. Si
   encuentra algo que parece un teléfono fuera de un contacto público, se detiene sin escribir.
5. Revisar `git diff casos.json`. Los únicos teléfonos que pueden aparecer son los de
   `contacto_cuidador`, y sólo si venían en un cartel público.
6. `git add` sólo de `casos.json` y las carpetas de `casos/` que cambiaron (nunca `privado/`),
   `git commit -m "Actualiza casos DD/MM"` y `git push`. La página se actualiza en 1–2 minutos.

**Respaldo:** `privado/` no está en GitHub ni en Drive. Hay que incluir esta carpeta en el
respaldo de la Mac (Time Machine o iCloud); si se pierde la carga, se pierde la moderación.

**Cerrar un caso:** cuando una mascota es adoptada o vuelve a casa, se agrega una novedad (o se
cambia su estado) y se pone la fecha en `fecha_cierre`. La tarjeta se queda como final feliz.

**Fotos:** sólo de la mascota, sin capturas del chat, sin teléfonos de vecinas y sin direcciones.
Pesan unos 150 KB y se guardan como `<id_caso>/foto-1.jpg`, `foto-2.jpg`. Si un caso no tiene
permiso de foto, el script la quita de la página.

**Si se cuela un dato privado** (el teléfono de una vecina, una dirección exacta):
1. Quitarlo de la Sheet, volver a correr el script y hacer push en ese momento.
2. El historial del repo es público y el dato sigue ahí. La opción más simple es borrar el repo en
   GitHub y crearlo de nuevo con el mismo nombre y sólo la versión limpia. Después hay que volver
   a activar *Settings → Pages*.
3. Avisarle a la persona.

**Compartir la moderación con otra vecina:**
- En GitHub, *Settings → Collaborators*: agregar su usuario.
- En la Sheet, compartirla como editora.
- Pasarle este apartado.

## Configuración

Al final de `index.html` hay dos cosas que se editan a mano:
- `WHATSAPP_ADMIN`: el WhatsApp de la administradora en formato `52` + 10 dígitos. Si está vacío,
  se ocultan los botones "Preguntar por ella" y "Escribir a la administradora".
- GoatCounter cuenta las visitas sin cookies. El panel está en https://red-de-huellitas.goatcounter.com.

## Probar en tu compu

```
cd ..
python3 -m http.server 8000
```
Luego abrir http://localhost:8000/red-de-huellitas/ (la misma ruta que en GitHub Pages).

## Reglas de la comunidad que sigue la página

- Tono de familia: "mascota", "perrito", "gatito", "su familia". Nunca "animal" ni "dueño".
- Sólo la zona o privada, nunca direcciones exactas.
- Los datos de quien reporta no se publican. El contacto pasa por la administradora, salvo el
  teléfono que quien cuida a la mascota ya publicó en su propio cartel.
- Sólo se publica la foto de una mascota con permiso de quien la resguarda.
- Cero dinero: sin donativos, pagos ni recompensas.
