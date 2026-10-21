# aSDKupdate

Programa de **PC** (Windows, Linux o macOS) con interfaz para **decompilar** un APK, **aplicar mejoras**
(SDK para Android 16, FPS, pantalla ancha…), dejarlo **desempaquetado** para que edites lo que quieras, y
**volver a armarlo** firmado y listo para instalar.

Es un solo archivo de Python (`asdkupdate.py`). Usa [apktool](https://apktool.org) para desempaquetar y
armar, y las herramientas oficiales del Android SDK (`zipalign`, `apksigner`) para alinear y firmar.

## Requisitos (una vez)

1. [Python 3.8+](https://www.python.org/downloads/). En Windows marca *"Add python.exe to PATH"*.
2. [Android Studio](https://developer.android.com/studio): trae Java y el Android SDK. Ábrelo una vez para
   que descargue el SDK.
3. apktool se descarga solo la primera vez. Si falla, baja el `.jar` de [apktool.org](https://apktool.org) y
   guárdalo como `apktool.jar` junto a `asdkupdate.py`.

## Uso con interfaz

Doble clic en **`aSDKupdate.bat`** (o `python asdkupdate.py`).

1. **Elegir…** el APK.
2. Elige la **versión de Android** para la que se arma (de Android 7 a 17) y marca las **mejoras** y
   **correcciones**.
3. Pulsa **1. Decompilar**. Queda todo desempaquetado en `juego-src\` junto al APK.
4. Pulsa **2. Aplicar mejoras**. Ahora puedes editar a mano: **Abrir carpeta**, o ábrela en Android Studio
   (*File → Open*), y cambia `smali\`, `res\`, `assets\` o `AndroidManifest.xml`.
5. Pulsa **3. Armar y firmar**. Sale `juego_mod.apk`.
6. **Instalar (adb)** con el teléfono conectado y la depuración USB activada. Antes desinstala la app
   original: la firma es distinta.

**Todo (1+2+3)** hace los tres pasos de una vez. Si ya tienes una carpeta decompilada, elígela en
*Carpeta decompilada* y pulsa solo 3.

## Uso por consola

```bat
python asdkupdate.py juego.apk --target 36 --todo
python asdkupdate.py juego.apk --target 24 --solo-decompilar
python asdkupdate.py --help
```

## Qué hace cada opción

**Versión de Android** (lista desplegable): sube `targetSdkVersion` a esa versión, quita `maxSdkVersion` y, desde
Android 12, añade `android:exported` donde hace falta. Android 15, 16 y 17 no instalan nada por debajo de
Android 7.0 (API 24), que además es la opción que menos cambia la app.

**Mejoras**

| Opción | Cambio en el APK |
|---|---|
| **FPS dinámicos / 60+ fps** | Marca la app como juego y activa el *modo juego* con `allowGameFpsOverride`. En Android 13+, el Game Dashboard o el modo juego del fabricante pueden subir o bajar los FPS. |
| **Pantalla ancha** | `resizeableActivity=true`, `android.max_aspect=3.0` y quita `maxAspectRatio`: sin franjas negras en 20:9 o 21:9. |
| **Notch / cámara** | `windowLayoutInDisplayCutoutMode=shortEdges` en el tema, más los ajustes de Huawei y Xiaomi. |
| **Girar en ambos sentidos** | `landscape` → `sensorLandscape` (y lo mismo en vertical). |
| **Aceleración por hardware** | `hardwareAccelerated=true`: los juegos viejos con Canvas van más fluidos. |

**Correcciones automáticas** (evitan que la app se cierre al subir el SDK; sin editar nada a mano)

| Opción | Cómo lo corrige |
|---|---|
| **PendingIntent** (Android 12+) | Redirige `PendingIntent.get…` a una clase de ayuda que añade `FLAG_MUTABLE` como antes, o `FLAG_IMMUTABLE` si el intent es implícito (Android 14 no deja otra cosa). |
| **registerReceiver** (Android 14+) | Redirige `registerReceiver` para pasar `RECEIVER_EXPORTED`, que era el comportamiento antiguo. |
| **Servicios en primer plano** (Android 14+) | Si la app usa servicios en primer plano, les pone el tipo `specialUse` (sin límite de tiempo) y su permiso. |
| **file://** (Android 7+) | Al arrancar la app desactiva la comprobación que lanza `FileUriExposedException`. |
| **Edge-to-edge** | Desactiva el dibujo debajo de las barras del sistema en el tema. Android 16+ lo ignora: elige Android 15 (API 35) si lo necesitas. |

La clase de ayuda (`asdkupdate.Fix`) va en un `classesN.dex` nuevo para no tocar el límite de 64K métodos.
Puedes aplicar el paso 2 varias veces sin duplicar cambios.

Siempre: alinea a 4 bytes y las `.so` a **16 KB** (Android 15+) y firma v1+v2+v3 con tu `debug.keystore` de
Android Studio (lo crea si no existe).

### Lo que sigue sin poder hacerse automático

* **FPS escritos en el código del juego** (por ejemplo `Application.targetFrameRate = 30` en Unity): el modo
  juego no los pasa por encima. En juegos Java se puede buscar el número en `smali\` entre los pasos 2 y 3; en
  Unity IL2CPP está dentro de `libil2cpp.so`.
* **Pantalla ancha** quita el límite del sistema; si el juego dibuja a 16:9 fijo, se verá estirado o con bordes.
* **Permisos** (cámara, ubicación…): desde Android 6 se piden al usarlos; si el juego nunca los pide,
  concédelos en *Ajustes → Apps → Permisos*.
* **Librerías `.so` de 4 KB** en teléfonos con páginas de 16 KB: solo se arreglan recompilando la librería con
  NDK r28+.
* Si aun así se cierra, mira el motivo en **Logcat** de Android Studio y prueba con **Android 7.0 (API 24)**.

## Uso responsable

Modifica solo apps tuyas, libres o que tengas derecho a modificar, y no redistribuyas APKs de terceros. Una app
re-firmada no recibe actualizaciones de la tienda.
