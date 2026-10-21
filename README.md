# Zenith APK Editor

![icono](app/src/main/res/mipmap-xxxhdpi/ic_launcher.png?raw=true)

[![Compilar APK](https://github.com/ZenithUzu/Android-SDK-/actions/workflows/android.yml/badge.svg)](https://github.com/ZenithUzu/Android-SDK-/actions/workflows/android.yml)
![Licencia](https://img.shields.io/badge/licencia-GPL--3.0-blue)
![Android](https://img.shields.io/badge/Android-6.0%20a%2017-green)

App para **Android** que decompila aplicaciones, te deja editarlas, las vuelve a compilar y firmar, y además
**sube su SDK para que se puedan instalar y ejecutar en Android 16**, todo desde el teléfono, sin PC.

Está basada en [APK Explorer & Editor (AEE)](https://github.com/apk-editor/APK-Explorer-Editor) v0.36,
un proyecto libre y activo; este fork añade la función **Compatibilidad Android 16** y corrige dos errores del
alineado de ZIP.

## Qué puede hacer

**Decompilar y explorar**
* Abrir una app instalada o un `.apk` / `.apks` / `.xapk` / `.apkm` del almacenamiento.
* *Decompilación simple* (rápida) o *completa* (convierte `classes.dex` a código **smali**).
* Ver y editar `AndroidManifest.xml` y cualquier XML binario, ver `resources.arsc`, imágenes, fuentes, etc.
* Exportar, borrar o reemplazar archivos y recursos.

**Compilar y firmar**
* Volver a ensamblar el smali modificado a `classes.dex`.
* Reconstruir el APK, alinearlo (zipalign) y firmarlo con esquemas **v1 + v2 + v3** (y v4 en Android 11+).
* Firmar con la clave propia de la app o con tu propio keystore; firmar APK o bundles por lotes.
* Instalador integrado de APK y APK divididos (split / bundles).

**Edición rápida**
* Cambiar nombre, paquete, versión y minSdk sin decompilar todo.

**Compatibilidad Android 16** *(nuevo en este fork)*
* Sube `targetSdkVersion` a **36 (Android 16)**, al **mínimo instalable (24)** o al valor que elijas.
* Añade `android:exported="true"` a las actividades/servicios/receivers con `intent-filter`
  (obligatorio desde API 31; sin esto Android rechaza instalar la app).
* Quita `maxSdkVersion` si bloqueaba la instalación y, opcionalmente, sube `minSdkVersion` a 24.
* Elimina la firma vieja, guarda `resources.arsc` sin comprimir y alinea a 4 bytes y las `.so` a **16 KB**
  (requisitos de Android 11+ y Android 15+).
* Revisa las librerías nativas de 64 bits y avisa si están compiladas para páginas de 4 KB.
* Funciona con apps divididas (split APK): parchea el APK base y vuelve a firmar todos juntos.
* Conserva las referencias a recursos (tema, icono, nombre traducido de la app).
* Al final muestra un informe de lo que cambió y de los cambios de comportamiento a revisar.

## Por qué hace falta

Desde Android 14 el sistema se niega a instalar apps "viejas": en **Android 15, 16 y 17 el mínimo es
`targetSdkVersion` 24** (Android 7.0). Muchas apps y juegos antiguos fallan con
`INSTALL_FAILED_DEPRECATED_SDK_VERSION`. Subir el SDK objetivo, añadir `exported` y realinear es justo lo que
hace este parche.

## Cómo usarlo

1. Abre la app y elige una app instalada (pestaña *Apps*) o un APK (pestaña *APKs*).
2. En el menú que aparece, toca **Compatibilidad Android 16 (subir SDK)**.
3. Elige el modo:
   * **Android 16 (API 36)** – lo recomendado si la app es reciente o la vas a mantener.
   * **Mínimo instalable (API 24)** – el que menos cambia el comportamiento; ideal para apps/juegos viejos.
   * **Personalizado** – cualquier valor entre 24 y 99.
4. Toca **Parchear, alinear y firmar**. El APK queda en `Download/AEE/` con el sufijo `_api36` / `_api24`
   (una carpeta con todos los APK si la app es dividida).
5. **Desinstala la app original** (la firma es distinta) y toca **Instalar**.

> Si en *Ajustes → On Exploring an App* elegiste una opción fija, vuelve a *Prompt* para que aparezca el menú.

### Lo que el parche *no* puede arreglar

Subir el SDK cambia cómo Android trata a la app. Esto depende del código de la app y no se arregla editando
el manifest (la app te avisa en el informe):

| Desde | Cambio | Síntoma típico |
|---|---|---|
| API 23 | Permisos en tiempo de ejecución | La app no tiene cámara/ubicación → concédelos en Ajustes |
| API 24 | `file://` prohibido al compartir | Crash al compartir archivos |
| API 30 | Almacenamiento con alcance | No encuentra archivos en `/sdcard` |
| API 31 | `PendingIntent` necesita `FLAG_IMMUTABLE` | Crash al mostrar notificaciones/alarmas |
| API 34 | `foregroundServiceType`, `RECEIVER_EXPORTED` | Crash al iniciar servicios |
| API 35/36 | Edge-to-edge obligatorio | La interfaz queda debajo de las barras |

Si una app se cierra con API 36, vuelve a parchear el APK **original** con el modo **API 24**. Para corregir
el código puedes usar la *decompilación completa*, editar el smali y recompilar desde la misma app.

Las librerías `.so` compiladas para páginas de 4 KB solo se pueden arreglar recompilándolas desde su código
fuente; en la mayoría de teléfonos (páginas de 4 KB) funcionan igual.

## Descargar

* **Última compilación:** pestaña [Actions](https://github.com/ZenithUzu/Android-SDK-/actions) → la ejecución
  más reciente → artefacto `ZenithAPKEditor-…` (contiene `ZenithAPKEditor-debug.apk`, listo para instalar).
* **Versiones:** cuando se publica un tag `v*` el APK aparece en
  [Releases](https://github.com/ZenithUzu/Android-SDK-/releases).

Se instala junto a AEE original sin reemplazarlo (paquete `io.github.zenithuzu.apkeditor`).

## Compilar tú mismo

Requisitos: JDK 17 o más nuevo y Android SDK con *platform 37* (Gradle lo descarga si falta).

```bash
git clone https://github.com/ZenithUzu/Android-SDK-.git
cd Android-SDK-
echo "sdk.dir=/ruta/a/Android/Sdk" > local.properties   # o define ANDROID_HOME
./gradlew assembleFullDebug
# APK: app/build/outputs/apk/full/debug/app-full-debug.apk
```

También se abre tal cual en Android Studio. Sabores: `full` (todas las funciones) y `play` (solo explorar).

### Dónde está el código nuevo

| Archivo | Qué hace |
|---|---|
| `app/src/main/java/com/apk/editor/utils/SdkUpgrader.java` | Núcleo del parche: manifest, reempaquetado, alineado, chequeo ELF de 16 KB |
| `app/src/main/java/com/apk/editor/activities/Android16Activity.java` | Pantalla "Compatibilidad Android 16" |
| `app/src/main/res/layout/activity_android16.xml` | Diseño de la pantalla |
| `app/src/full/java/com/apk/editor/utils/menu/ExploreOptionsMenu.java` | Entrada en el menú |
| `app/src/main/java/com/apk/editor/utils/ZipAlign.java` | Corregido: leía el *tamaño* del directorio central como su *posición* y podía fallar al buscar el final del ZIP, así que el APK salía sin alinear |

## Uso responsable

Modifica solo apps que sean tuyas, libres o que tengas derecho a modificar, y no redistribuyas apps de
terceros parcheadas. Las apps reempaquetadas pierden la firma original: no reciben actualizaciones de la tienda.

## Créditos

* [APK Explorer & Editor](https://github.com/apk-editor/APK-Explorer-Editor) y
  [sunilpaulmathew](https://github.com/sunilpaulmathew) — la base de toda la app.
* Lista completa de colaboradores y librerías: [Credits.md](Credits.md).
* Función *Compatibilidad Android 16* y correcciones: [ZenithUzu](https://github.com/ZenithUzu).

## Licencia

    Copyright (C) 2021-2026 APK Explorer & Editor <apkeditor@protonmail.com>
    Copyright (C) 2026 ZenithUzu (modificaciones de este fork)

    Este programa es software libre: puedes redistribuirlo y/o modificarlo bajo los términos de la
    GNU General Public License publicada por la Free Software Foundation, versión 3 o (a tu elección)
    cualquier versión posterior.

    Se distribuye con la esperanza de que sea útil, pero SIN NINGUNA GARANTÍA; ni siquiera la garantía
    implícita de COMERCIABILIDAD o IDONEIDAD PARA UN PROPÓSITO PARTICULAR. Consulta la GNU General Public
    License para más detalles. Deberías haber recibido una copia junto con este programa (archivo LICENSE);
    si no, visita <https://www.gnu.org/licenses/>.
