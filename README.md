# Zenith APK Tool

Programa de **PC** (Windows, Linux o macOS) con interfaz para **decompilar** un APK, **aplicar mejoras**
(SDK para Android 16, FPS, pantalla ancha…), dejarlo **desempaquetado** para que edites lo que quieras, y
**volver a armarlo** firmado y listo para instalar.

Es un solo archivo de Python (`zenith_apk.py`). Usa [apktool](https://apktool.org) para desempaquetar y
armar, y las herramientas oficiales del Android SDK (`zipalign`, `apksigner`) para alinear y firmar.

## Requisitos (una vez)

1. [Python 3.8+](https://www.python.org/downloads/). En Windows marca *"Add python.exe to PATH"*.
2. [Android Studio](https://developer.android.com/studio): trae Java y el Android SDK. Ábrelo una vez para
   que descargue el SDK.
3. apktool se descarga solo la primera vez. Si falla, baja el `.jar` de [apktool.org](https://apktool.org) y
   guárdalo como `apktool.jar` junto a `zenith_apk.py`.

## Uso con interfaz

Doble clic en **`Zenith APK Tool.bat`** (o `python zenith_apk.py`).

1. **Elegir…** el APK.
2. Elige el **SDK objetivo** y marca las **mejoras**.
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
python zenith_apk.py juego.apk --target 36 --fps --widescreen --notch
python zenith_apk.py juego.apk --target 24 --solo-decompilar
python zenith_apk.py --help
```

## Qué hace cada opción

| Opción | Cambio en el APK |
|---|---|
| **Android 16 (API 36)** | Sube `targetSdkVersion`, quita `maxSdkVersion` y añade `android:exported` a los componentes con `intent-filter`. Sin eso, Android 12+ no instala la app. |
| **Mínimo instalable (API 24)** | Lo mínimo que Android 15, 16 y 17 aceptan instalar. Es el que menos cambia el comportamiento: úsalo con juegos viejos. |
| **FPS dinámicos / 60+ fps** | Marca la app como juego (`isGame`, `appCategory=game`) y añade la configuración de *modo juego* con `allowGameFpsOverride`. Así, en Android 13+, el Game Dashboard o el modo juego del fabricante pueden cambiar los FPS y el modo rendimiento/batería. |
| **Pantalla ancha** | `resizeableActivity=true`, `android.max_aspect=3.0` y quita `maxAspectRatio`. Se acaban las franjas negras en pantallas 19.5:9, 20:9 y 21:9. |
| **Notch / cámara** | `windowLayoutInDisplayCutoutMode=shortEdges` en el tema, más los ajustes de Huawei y Xiaomi. |
| **Girar en ambos sentidos** | `landscape` → `sensorLandscape` (y lo mismo en vertical). |
| **Aceleración por hardware** | `hardwareAccelerated=true` en toda la app. Los juegos viejos con Canvas van más fluidos. |

Siempre: alinea a 4 bytes y las `.so` a **16 KB** (Android 15+) y firma v1+v2+v3 con tu `debug.keystore` de
Android Studio (lo crea si no existe).

### Límites (léelo)

* **FPS:** si el juego tiene el límite de FPS escrito en su código (por ejemplo `Application.targetFrameRate = 30`
  en Unity), el modo juego no lo puede pasar por encima. Hay que cambiarlo a mano: en juegos Java/smali, busca el
  número en `smali\` entre los pasos 2 y 3. En Unity IL2CPP está dentro de `libil2cpp.so` y no se puede editar
  así.
* **Pantalla ancha:** quita el límite del sistema. Si el juego dibuja a 16:9 fijo, se verá estirado o con bordes
  propios.
* **Subir a 36** puede romper apps viejas. Lo que dice Logcat y cómo arreglarlo:

| Error en Logcat (Android Studio) | Arreglo con el paso 2 → editar → 3 |
|---|---|
| `Targeting S+ ... FLAG_IMMUTABLE` | En el smali, antes de `PendingIntent;->get…`: `or-int/lit32 vN, vN, 0x4000000` (vN = registro de *flags*) |
| `MissingForegroundServiceTypeException` | En el manifest: `android:foregroundServiceType="dataSync"` en el `<service>` y el permiso `FOREGROUND_SERVICE_DATA_SYNC` |
| `One of RECEIVER_EXPORTED…` | Bajar a SDK 33 (*Otro: 33*) |
| La interfaz queda bajo las barras | SDK 35 y, en el tema, `<item name="android:windowOptOutEdgeToEdgeEnforcement">true</item>` |
| Crash en `lib….so` en teléfonos de 16 KB | Recompilar esa librería con NDK r28+. Sin su código fuente no tiene arreglo. |

Si no quieres pelear con esto, usa **API 24**.

## Uso responsable

Modifica solo apps tuyas, libres o que tengas derecho a modificar, y no redistribuyas APKs de terceros. Una app
re-firmada no recibe actualizaciones de la tienda.
