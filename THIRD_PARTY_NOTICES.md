# Componentes de terceros

rcordr se distribuye bajo la licencia **GNU GPL v3 o posterior** (ver [LICENSE](LICENSE)).
El paquete portable (`rcordr-<versión>-windows.zip`) incluye además los componentes
siguientes, cada uno con su propia licencia. Los textos completos van en la carpeta
`licencias/` del paquete.

| Componente | Uso en rcordr | Licencia | Código fuente |
|---|---|---|---|
| **FFmpeg 7.1** (compilación «essentials» de gyan.dev, distribuida por imageio-ffmpeg) | Codificar y montar los vídeos; se ejecuta como programa aparte | GPL v3 (compilado con `--enable-gpl --enable-version3`, incluye x264 y otras bibliotecas) | <https://ffmpeg.org/releases/ffmpeg-7.1.tar.xz> · bibliotecas y opciones de compilación: <https://www.gyan.dev/ffmpeg/builds/> |
| **imageio-ffmpeg** | Proporciona el binario de FFmpeg | BSD-2-Clause | <https://github.com/imageio/imageio-ffmpeg> |
| **PyAudioWPatch** (con PortAudio) | Captura del sonido del ordenador y del micrófono | Apache-2.0 (PortAudio: MIT) | <https://github.com/s0d3s/PyAudioWPatch> · <https://github.com/PortAudio/portaudio> |
| **Pillow** | Imágenes (capturas, miniaturas, icono) | MIT-CMU (incluye avisos de sus bibliotecas) | <https://github.com/python-pillow/Pillow> |
| **mss** | Captura de pantalla | MIT | <https://github.com/BoboTiG/python-mss> |
| **pystray** | Icono de la bandeja del sistema | LGPL v3 | <https://github.com/moses-palmer/pystray> |
| **six** | Dependencia de pystray | MIT | <https://github.com/benjaminp/six> |
| **Python 3.13** (python-build-standalone) | Intérprete incluido en el ejecutable | PSF License | <https://www.python.org/downloads/source/> |
| **Tcl/Tk 8.6** | Ventanas y paneles | Licencia tipo BSD (`license.terms`) | <https://www.tcl-lang.org/software/tcltk/> |
| **OpenSSL 3** | Incluido por el intérprete de Python | Apache-2.0 | <https://github.com/openssl/openssl> |
| **libffi**, **zlib** | Incluidos por el intérprete de Python | MIT / zlib | <https://github.com/libffi/libffi> · <https://zlib.net> |
| **Microsoft Visual C++ Runtime** (`VCRUNTIME140*.dll`) | Necesario para Python | Redistribuible de Microsoft | — |
| **PyInstaller** (cargador) | Arranque de `rcordr.exe` | GPL v2 con excepción que permite distribuir el programa empaquetado con cualquier licencia | <https://github.com/pyinstaller/pyinstaller> |

rcordr usa FFmpeg lanzándolo como un proceso independiente; no lo enlaza.

## Código fuente

- **rcordr**: <https://github.com/aydearcas/rcordr>
- **Componentes de terceros**: en los enlaces de la tabla. Si necesita el código fuente
  exacto de alguno de los componentes GPL o LGPL de una versión concreta del paquete,
  abra un *issue* en el repositorio de rcordr y se lo facilitaremos.
