# rcordr

Capturas de imagen y vídeo de pantalla para Windows, desde la bandeja del sistema.
Al abrirlo queda como un icono (una **r** blanca con un punto rojo) abajo a la derecha,
junto al reloj, y todo se maneja con atajos de teclado.

## Uso

| Atajo | Acción |
|---|---|
| `Ctrl+Shift+1` | **Captura de imagen**: la pantalla se congela; arrastra para seleccionar (clic simple = pantalla completa, `Esc`/clic derecho = cancelar). Se copia al portapapeles y aparece un botón flotante **Guardar** (PNG). |
| `Ctrl+Shift+2` | **Grabar vídeo**: arrastra para elegir la zona (clic simple = pantalla completa, `Esc` = cancelar). La zona queda rodeada por un marco rojo y abajo a la derecha aparece `● REC 00:12` con botón *Detener* (ninguno de los dos sale en el vídeo). Vuelve a pulsarlo para **detener**. |
| `Ctrl+Shift+3` | **Grabar vídeo y editar**: igual que `Ctrl+Shift+2`, pero al detener se abre el editor. |

### Sonido

En el clic derecho del icono → **Configuración** se marca qué se graba:

- **Grabar sonido del ordenador** (activado por defecto): lo que suena por los altavoces
  o auriculares predeterminados.
- **Grabar micrófono**: la entrada predeterminada de Windows (*Configuración de sonido →
  Entrada*). Si están las dos, se mezclan en una sola pista.

> Si el micrófono predeterminado son unos auriculares Bluetooth (AirPods, etc.), Windows
> los pasa a modo «manos libres» mientras se graba y el sonido del ordenador baja de calidad.

### Editor de vídeo

Ventana flotante con vista previa (con sonido) y una línea de tiempo:

- Arrastra los **extremos azules** para elegir dónde empieza y dónde acaba el vídeo
  (o pulsa `I` / `O` para marcar inicio / fin en la posición actual).
- `Espacio` o clic en la imagen: reproducir / pausa. Clic en la barra: ir a ese punto.
- **Mezclador**: un deslizador de volumen (0–200 %) para el ordenador y otro para el
  micrófono; se escucha al momento en la vista previa. Los volúmenes elegidos se recuerdan
  y se aplican también a las grabaciones con `Ctrl+Shift+2`.
- **Quitar audio**: el vídeo se guarda sin sonido.
- **Guardar** sustituye la grabación por la versión editada. **Descartar** (dos clics)
  borra la grabación. Cerrar la ventana conserva el vídeo entero con la mezcla inicial.

Al grabar para editar, el ordenador y el micrófono van en pistas separadas (ya
sincronizadas), así que cambiar sus volúmenes no afecta a la sincronía. Al guardar se
mezclan en una sola pista, que es la que reproduce WhatsApp.

Recortar recodifica el vídeo (corte exacto al fotograma; tarda unos segundos y se ve el
porcentaje). Sin recorte, el vídeo se copia tal cual y solo se procesa el audio.

Al terminar un vídeo se guarda como `.mp4` y **se copia al portapapeles como archivo**:
en WhatsApp Desktop/Web basta con `Ctrl+V` en el chat.

- Capturas: `Imágenes\rcordr\captura_AAAAMMDD_HHMMSS.png`
- Vídeos: `Vídeos\rcordr\video_AAAAMMDD_HHMMSS.mp4`

Clic derecho en el icono de la bandeja: mismas acciones, abrir carpetas, configuración y salir.
Los atajos, carpetas y FPS se cambian en `%USERPROFILE%\.rcordr\config.json`
(hay que reiniciar la app).

## Formato de vídeo (WhatsApp)

Se usa **MP4 con vídeo H.264 (yuv420p) y audio AAC estéreo**, con `faststart`. Es el
formato nativo de WhatsApp en Android, iPhone, Web y Desktop: se envía y reproduce
sin conversión. Además el vídeo se reduce a 1080p como máximo y con CRF 26 para que
ocupe poco (≈ 2–10 MB por minuto según cuánto movimiento haya en pantalla).

Otros formatos posibles y por qué no se usan por defecto:

| Formato | Compatible con WhatsApp | Comentario |
|---|---|---|
| **MP4 (H.264 + AAC)** | ✅ Sí, en todas partes | El elegido. |
| 3GP (H.263/H.264 + AMR/AAC) | ✅ Sí | Formato antiguo, peor calidad. |
| MOV (H.264 + AAC) | ⚠️ Normalmente | Mismo contenido que MP4, pero en Android/Web a veces lo manda como documento. |
| MP4 (H.265/HEVC) | ⚠️ Depende del móvil | Ocupa menos, pero algunos Android/Web no lo reproducen. |
| WebM / MKV | ❌ No como vídeo | Se envía como documento. |

Límites de WhatsApp: hasta ~2 GB por vídeo (WhatsApp lo recomprime al enviarlo como vídeo).

## Instalación

Requisitos: Windows 10 (2004+) u 11 y Python 3.10+.

```powershell
powershell -ExecutionPolicy Bypass -File instalar.ps1              # crea .venv + acceso en menú Inicio
powershell -ExecutionPolicy Bypass -File instalar.ps1 -Escritorio  # además, icono en el escritorio
powershell -ExecutionPolicy Bypass -File instalar.ps1 -Inicio      # además, arrancar con Windows
```

Para anclarlo a la barra de tareas: clic derecho en el icono del escritorio (o en
*rcordr* del menú Inicio) → *Mostrar más opciones* → **Anclar a la barra de tareas**.
Si rcordr ya está abierto, pulsar el icono muestra el aviso con los atajos.

Tras actualizar el código no hace falta reinstalar: basta con cerrar rcordr (*Salir*
en la bandeja) y volver a abrirlo. Solo hay que repetir el instalador si cambia
`requirements.txt`.

O a mano:

```powershell
python -m venv .venv
.venv\Scripts\pip install --require-hashes --only-binary=:all: -r requirements.txt
.venv\Scripts\pythonw rcordr.pyw
```

No hace falta instalar ffmpeg: viene incluido con `imageio-ffmpeg`.

## Empaquetar para enviar

Genera `dist\rcordr-<versión>-windows.zip`: carpeta portable con `rcordr.exe` (no necesita
Python) y el manual en PDF (estilo manual de videocámara de los 80–90).

```powershell
uv venv .venv-build --python 3.13 --python-preference only-managed
uv pip install --python .venv-build\Scripts\python.exe --require-hashes -r scripts\requirements-build.txt
.venv-build\Scripts\python.exe scripts\empaquetar.py
```

- Se compila con un Python gestionado por `uv` (no el de Microsoft Store) y PyInstaller.
- `scripts\manual.py` genera solo el manual (`--solo-manual` en `empaquetar.py`).
- El ejecutable no está firmado: la primera vez Windows SmartScreen pide «Ejecutar de todas formas».

**Diagnóstico:** `rcordr.exe --selftest` (o `pythonw rcordr.pyw --selftest`) comprueba la
ventana, ffmpeg y el audio grabando 2 s, y deja el resultado en
`%USERPROFILE%\.rcordr\rcordr-selftest.log`.

## Seguridad y privacidad

- Funciona sin permisos de administrador y **no usa la red**: no envía nada ni abre puertos.
- Los atajos usan `RegisterHotKey`: la app solo recibe sus tres combinaciones, no ve el
  resto de lo que escribes (no es un gancho de teclado).
- `requirements.txt` fija versiones exactas con **hashes SHA-256** y el instalador usa
  `--require-hashes --only-binary=:all:`: pip rechaza cualquier paquete alterado y no
  ejecuta código de compilación. Para actualizar: editar `requirements.in` y ejecutar
  `uv pip compile requirements.in --generate-hashes --python-platform windows -o requirements.txt`.
- Siempre se usa el ffmpeg incluido en el paquete verificado; no se busca en el `PATH`
  ni se acepta `IMAGEIO_FFMPEG_EXE`.
- Al arrancar se vacía `%USERPROFILE%\.rcordr\tmp`. Si quedó un vídeo a medias por un cierre
  inesperado, se recupera (sin sonido) como `video_recuperado_*.mp4` en la carpeta de vídeos.
- Ten en cuenta que si tienes activado el historial del portapapeles (`Win+V`) o su
  sincronización, Windows guarda ahí las capturas. Y que el sonido del ordenador incluye
  la voz de los demás en una llamada.

## Cómo funciona

```
rcordr/
  app.py         bandeja (pystray) + bucle Tk + coordinación
  hotkeys.py     atajos globales con RegisterHotKey (Win32, sin admin)
  screenshot.py  overlay de selección sobre la pantalla congelada (mss + Tk)
  recorder.py    vídeo con ffmpeg gdigrab + audio del ordenador (loopback) y micrófono
  editor.py      editor: vista previa, recorte, mezclador de volumen, quitar audio
  ui.py          paneles flotantes: Guardar, indicador REC, avisos
  winapi.py      portapapeles, DPI, instancia única, ocultar ventanas en capturas
  icon.py        dibuja el icono (python -m rcordr.icon regenera assets/)
  config.py      config.json
```

- El vídeo se graba a un `.mkv` temporal (H.264, `veryfast`) y el audio a un `.raw`;
  al parar se combinan en el `.mp4` sin recodificar el vídeo, así que es casi instantáneo.
- Sincronía: ffmpeg informa la hora real del primer fotograma (`start:`) y se compara con
  la hora de inicio del audio para recortar/retrasar el audio.
- El loopback de WASAPI no da datos cuando no suena nada; para que el audio no se
  desincronice se reproduce silencio en la misma salida mientras se graba.
- Los paneles flotantes usan `WDA_EXCLUDEFROMCAPTURE`, así que no aparecen en capturas
  ni vídeos.
