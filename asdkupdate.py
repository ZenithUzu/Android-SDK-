"""
aSDKupdate - programa de PC para decompilar APKs, aplicar mejoras y volver a armarlos.

  python asdkupdate.py                         -> abre la interfaz
  python asdkupdate.py juego.apk [opciones]    -> todo de una vez, sin interfaz (ver --help)

Necesita: Python 3.8+, Java y el Android SDK (los trae Android Studio). apktool se descarga solo.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import threading
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ANDROID = "http://schemas.android.com/apk/res/android"
A = "{%s}" % ANDROID
for prefix, uri in {"android": ANDROID, "tools": "http://schemas.android.com/tools",
                    "app": "http://schemas.android.com/apk/res-auto",
                    "dist": "http://schemas.android.com/apk/distribution"}.items():
    ET.register_namespace(prefix, uri)

HERE = Path(__file__).resolve().parent
MIN_INSTALLABLE = 24  # Android 15, 16 y 17 no instalan apps con targetSdk < 24
COMPONENTS = ("activity", "activity-alias", "service", "receiver")

ANDROID_VERSIONS = [("No cambiar el SDK", 0)] + [(f"Android {n} (API {api})", api) for n, api in (
    ("17", 37), ("16", 36), ("15", 35), ("14", 34), ("13", 33), ("12L", 32), ("12", 31), ("11", 30),
    ("10", 29), ("9", 28), ("8.1", 27), ("8.0", 26), ("7.1", 25), ("7.0", 24))]

FIXES = {
    "pendingintent": "Notificaciones/alarmas: PendingIntent sin FLAG_IMMUTABLE (crash desde Android 12)",
    "receiver": "registerReceiver sin RECEIVER_EXPORTED (crash desde Android 14)",
    "fgs": "Servicios en primer plano sin tipo (crash desde Android 14)",
    "fileuri": "Compartir archivos file:// (crash desde Android 7)",
    "edge": "Interfaz debajo de las barras (edge-to-edge; solo hasta Android 15 / API 35)",
}

IMPROVEMENTS = {
    "fps": "FPS dinámicos / 60+ fps (modo juego Android 13+, permite al sistema cambiar los FPS)",
    "widescreen": "Pantalla ancha (sin franjas negras, cualquier relación de aspecto)",
    "notch": "Usar el área del notch / cámara",
    "rotation": "Girar en ambos sentidos (horizontal y vertical invertidas)",
    "hwaccel": "Aceleración por hardware (juegos viejos van más fluidos)",
}


# Clase que se mete en el APK: compilada de Java con javac + d8 y pasada a smali con apktool.
FIX_SMALI = """.class public final Lasdkupdate/Fix;
.super Ljava/lang/Object;
# direct methods
.method public constructor <init>()V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    return-void
.end method
.method private static flags(ILandroid/content/Intent;)I
    .locals 2
    sget v0, Landroid/os/Build$VERSION;->SDK_INT:I
    const/16 v1, 0x1f
    if-lt v0, v1, :cond_3
    const/high16 v0, 0x6000000
    and-int/2addr v0, p0
    if-nez v0, :cond_3
    if-eqz p1, :cond_1
    invoke-virtual {p1}, Landroid/content/Intent;->getComponent()Landroid/content/ComponentName;
    move-result-object v0
    if-nez v0, :cond_0
    invoke-virtual {p1}, Landroid/content/Intent;->getPackage()Ljava/lang/String;
    move-result-object p1
    if-eqz p1, :cond_1
    :cond_0
    const/4 p1, 0x1
    goto :goto_0
    :cond_1
    const/4 p1, 0x0
    :goto_0
    if-eqz p1, :cond_2
    const/high16 p1, 0x2000000
    goto :goto_1
    :cond_2
    const/high16 p1, 0x4000000
    :goto_1
    or-int/2addr p0, p1
    :cond_3
    return p0
.end method
.method public static getActivities(Landroid/content/Context;I[Landroid/content/Intent;I)Landroid/app/PendingIntent;
    .locals 1
    const/4 v0, 0x0
    invoke-static {p3, v0}, Lasdkupdate/Fix;->flags(ILandroid/content/Intent;)I
    move-result p3
    invoke-static {p0, p1, p2, p3}, Landroid/app/PendingIntent;->getActivities(Landroid/content/Context;I[Landroid/content/Intent;I)Landroid/app/PendingIntent;
    move-result-object p0
    return-object p0
.end method
.method public static getActivities(Landroid/content/Context;I[Landroid/content/Intent;ILandroid/os/Bundle;)Landroid/app/PendingIntent;
    .locals 1
    const/4 v0, 0x0
    invoke-static {p3, v0}, Lasdkupdate/Fix;->flags(ILandroid/content/Intent;)I
    move-result p3
    invoke-static {p0, p1, p2, p3, p4}, Landroid/app/PendingIntent;->getActivities(Landroid/content/Context;I[Landroid/content/Intent;ILandroid/os/Bundle;)Landroid/app/PendingIntent;
    move-result-object p0
    return-object p0
.end method
.method public static getActivity(Landroid/content/Context;ILandroid/content/Intent;I)Landroid/app/PendingIntent;
    .locals 0
    invoke-static {p3, p2}, Lasdkupdate/Fix;->flags(ILandroid/content/Intent;)I
    move-result p3
    invoke-static {p0, p1, p2, p3}, Landroid/app/PendingIntent;->getActivity(Landroid/content/Context;ILandroid/content/Intent;I)Landroid/app/PendingIntent;
    move-result-object p0
    return-object p0
.end method
.method public static getActivity(Landroid/content/Context;ILandroid/content/Intent;ILandroid/os/Bundle;)Landroid/app/PendingIntent;
    .locals 0
    invoke-static {p3, p2}, Lasdkupdate/Fix;->flags(ILandroid/content/Intent;)I
    move-result p3
    invoke-static {p0, p1, p2, p3, p4}, Landroid/app/PendingIntent;->getActivity(Landroid/content/Context;ILandroid/content/Intent;ILandroid/os/Bundle;)Landroid/app/PendingIntent;
    move-result-object p0
    return-object p0
.end method
.method public static getBroadcast(Landroid/content/Context;ILandroid/content/Intent;I)Landroid/app/PendingIntent;
    .locals 0
    invoke-static {p3, p2}, Lasdkupdate/Fix;->flags(ILandroid/content/Intent;)I
    move-result p3
    invoke-static {p0, p1, p2, p3}, Landroid/app/PendingIntent;->getBroadcast(Landroid/content/Context;ILandroid/content/Intent;I)Landroid/app/PendingIntent;
    move-result-object p0
    return-object p0
.end method
.method public static getForegroundService(Landroid/content/Context;ILandroid/content/Intent;I)Landroid/app/PendingIntent;
    .locals 0
    invoke-static {p3, p2}, Lasdkupdate/Fix;->flags(ILandroid/content/Intent;)I
    move-result p3
    invoke-static {p0, p1, p2, p3}, Landroid/app/PendingIntent;->getForegroundService(Landroid/content/Context;ILandroid/content/Intent;I)Landroid/app/PendingIntent;
    move-result-object p0
    return-object p0
.end method
.method public static getService(Landroid/content/Context;ILandroid/content/Intent;I)Landroid/app/PendingIntent;
    .locals 0
    invoke-static {p3, p2}, Lasdkupdate/Fix;->flags(ILandroid/content/Intent;)I
    move-result p3
    invoke-static {p0, p1, p2, p3}, Landroid/app/PendingIntent;->getService(Landroid/content/Context;ILandroid/content/Intent;I)Landroid/app/PendingIntent;
    move-result-object p0
    return-object p0
.end method
.method public static init()V
    .locals 1
    new-instance v0, Landroid/os/StrictMode$VmPolicy$Builder;
    invoke-direct {v0}, Landroid/os/StrictMode$VmPolicy$Builder;-><init>()V
    invoke-virtual {v0}, Landroid/os/StrictMode$VmPolicy$Builder;->build()Landroid/os/StrictMode$VmPolicy;
    move-result-object v0
    invoke-static {v0}, Landroid/os/StrictMode;->setVmPolicy(Landroid/os/StrictMode$VmPolicy;)V
    return-void
.end method
.method public static registerReceiver(Landroid/content/Context;Landroid/content/BroadcastReceiver;Landroid/content/IntentFilter;)Landroid/content/Intent;
    .locals 2
    sget v0, Landroid/os/Build$VERSION;->SDK_INT:I
    const/16 v1, 0x21
    if-lt v0, v1, :cond_0
    const/4 v0, 0x2
    invoke-virtual {p0, p1, p2, v0}, Landroid/content/Context;->registerReceiver(Landroid/content/BroadcastReceiver;Landroid/content/IntentFilter;I)Landroid/content/Intent;
    move-result-object p0
    goto :goto_0
    :cond_0
    invoke-virtual {p0, p1, p2}, Landroid/content/Context;->registerReceiver(Landroid/content/BroadcastReceiver;Landroid/content/IntentFilter;)Landroid/content/Intent;
    move-result-object p0
    :goto_0
    return-object p0
.end method
.method public static registerReceiver(Landroid/content/Context;Landroid/content/BroadcastReceiver;Landroid/content/IntentFilter;Ljava/lang/String;Landroid/os/Handler;)Landroid/content/Intent;
    .locals 8
    sget v0, Landroid/os/Build$VERSION;->SDK_INT:I
    const/16 v1, 0x21
    if-lt v0, v1, :cond_0
    const/4 v7, 0x2
    move-object v2, p0
    move-object v3, p1
    move-object v4, p2
    move-object v5, p3
    move-object v6, p4
    invoke-virtual/range {v2 .. v7}, Landroid/content/Context;->registerReceiver(Landroid/content/BroadcastReceiver;Landroid/content/IntentFilter;Ljava/lang/String;Landroid/os/Handler;I)Landroid/content/Intent;
    move-result-object p0
    goto :goto_0
    :cond_0
    move-object v2, p0
    move-object v3, p1
    move-object v4, p2
    move-object v5, p3
    move-object v6, p4
    invoke-virtual {v2, v3, v4, v5, v6}, Landroid/content/Context;->registerReceiver(Landroid/content/BroadcastReceiver;Landroid/content/IntentFilter;Ljava/lang/String;Landroid/os/Handler;)Landroid/content/Intent;
    move-result-object p0
    :goto_0
    return-object p0
.end method
"""
FIX_PI_SIGS = re.findall(r"public static (get\w+\([^)]*\)Landroid/app/PendingIntent;)", FIX_SMALI)
RECEIVER_RE = re.compile(r"invoke-virtual(/range)? \{([^}]*)\}, L[^;]+;->registerReceiver\("
                         r"(Landroid/content/BroadcastReceiver;Landroid/content/IntentFilter;(?:Ljava/lang/String;Landroid/os/Handler;)?)"
                         r"\)Landroid/content/Intent;")


# ------------------------------------------------------------------ herramientas

def find_java():
    candidates = [Path(os.environ["JAVA_HOME"]) / "bin" / "java"] if os.environ.get("JAVA_HOME") else []
    candidates += [Path(r"C:\Program Files\Android\Android Studio\jbr\bin\java.exe"),
                   Path("/Applications/Android Studio.app/Contents/jbr/Contents/Home/bin/java")]
    for c in candidates:
        if c.exists() or c.with_suffix(".exe").exists():
            return str(c)
    if shutil.which("java"):
        return "java"
    raise RuntimeError("No encuentro Java. Instala Android Studio o un JDK 17+.")


def find_build_tools():
    roots = [os.environ.get("ANDROID_HOME"), os.environ.get("ANDROID_SDK_ROOT"),
             os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk"),
             os.path.expanduser("~/Library/Android/sdk"), os.path.expanduser("~/Android/Sdk")]
    for root in filter(None, roots):
        bt = Path(root) / "build-tools"
        if bt.is_dir():
            versions = sorted((d for d in bt.iterdir() if d.is_dir()),
                              key=lambda d: [int(x) for x in re.findall(r"\d+", d.name)])
            if versions:
                return versions[-1]
    raise RuntimeError("No encuentro el Android SDK (build-tools). Instálalo desde el SDK Manager de Android Studio.")


def sdk_tool(name):
    bt = find_build_tools()
    for ext in (".exe", ".bat", ""):
        if (bt / (name + ext)).exists():
            return str(bt / (name + ext))
    raise RuntimeError(f"Falta {name} en {bt}")


def ensure_apktool(log):
    jar = HERE / "apktool.jar"
    if not jar.exists():
        log("Descargando apktool (solo la primera vez)...")
        # /releases/latest redirige a /releases/tag/vX.Y.Z (sin la API de GitHub, que tiene límite de uso)
        try:
            with urllib.request.urlopen("https://github.com/iBotPeaches/Apktool/releases/latest") as r:
                version = r.geturl().rstrip("/").rsplit("/", 1)[1]
            url = f"https://github.com/iBotPeaches/Apktool/releases/download/{version}/apktool_{version.lstrip('v')}.jar"
            urllib.request.urlretrieve(url, str(jar) + ".part")
        except OSError as e:
            raise RuntimeError(f"No pude descargar apktool ({e}). Descárgalo de https://apktool.org "
                               f"y guárdalo como {jar}")
        os.replace(str(jar) + ".part", jar)  # no dejar un .jar a medias si se corta la descarga
    return str(jar)


def run(cmd, log):
    log("> " + " ".join(Path(c).name if i == 0 else c for i, c in enumerate(cmd)))
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                       errors="replace", shell=cmd[0].endswith(".bat"))
    for line in p.stdout.splitlines():
        log("  " + line)
    if p.returncode != 0:
        raise RuntimeError(f"{Path(cmd[0]).name} falló (código {p.returncode})")


# ------------------------------------------------------------------ pasos

def src_dir(apk):
    return Path(apk).with_name(Path(apk).stem + "-src")


def decompile(apk, log):
    out = src_dir(apk)
    run([find_java(), "-jar", ensure_apktool(log), "d", "-f", "-o", str(out), str(apk)], log)
    log(f"Decompilado en: {out}")
    return out


def patch(src, target, improvements, log):
    src = Path(src)
    changes = []

    # SDK: apktool guarda minSdk/targetSdk en apktool.yml, no en el manifest
    yml = src / "apktool.yml"
    text = yml.read_text(encoding="utf-8")
    m = re.search(r"targetSdkVersion:\s*'?(\d+)", text)
    current = int(m.group(1)) if m else 0
    if target and target > current:
        text = (re.sub(r"targetSdkVersion:\s*'?\d+'?", f"targetSdkVersion: {target}", text) if m
                else re.sub(r"sdkInfo:\s*\n", f"sdkInfo:\n  targetSdkVersion: {target}\n", text))
        changes.append(f"targetSdkVersion {current} -> {target}")
    if re.search(r"(?m)^\s*maxSdkVersion:", text):
        text = re.sub(r"(?m)^\s*maxSdkVersion:.*\n", "", text)
        changes.append("quitado maxSdkVersion (bloqueaba Android nuevos)")
    yml.write_text(text, encoding="utf-8")
    target = max(target or 0, current)

    manifest_path = src / "AndroidManifest.xml"
    tree = ET.parse(manifest_path)
    app = tree.getroot().find("application")
    activities = [c for c in app if c.tag in ("activity", "activity-alias")]

    if target >= 31:
        n = 0
        for c in app:
            if c.tag in COMPONENTS and A + "exported" not in c.attrib and c.find("intent-filter") is not None:
                c.set(A + "exported", "true")  # antes de API 31, intent-filter implicaba exported=true
                n += 1
        if n:
            changes.append(f"android:exported en {n} componente(s) (obligatorio desde API 31)")

    def meta(name, value=None, resource=None):
        el = next((m for m in app.findall("meta-data") if m.get(A + "name") == name), None)
        if el is None:
            el = ET.SubElement(app, "meta-data", {A + "name": name})
        el.set(A + "resource" if resource else A + "value", resource or value)

    if "widescreen" in improvements:
        app.set(A + "resizeableActivity", "true")
        meta("android.max_aspect", "3.0")  # apps con targetSdk < 26 se limitaban a 16:9
        for a in activities:
            a.attrib.pop(A + "maxAspectRatio", None)
            a.attrib.pop(A + "minAspectRatio", None)
            a.attrib.pop(A + "resizeableActivity", None)
        changes.append("pantalla ancha: sin límite de relación de aspecto")

    if "notch" in improvements:
        meta("android.notch_support", "true")                # Huawei/Honor
        meta("notch.config", "portrait|landscape")           # Xiaomi
        themes = {app.get(A + "theme")} | {a.get(A + "theme") for a in activities}
        styled = _add_style_item(src, themes, "android:windowLayoutInDisplayCutoutMode", "shortEdges")
        changes.append(f"notch: usa el área de la cámara ({styled} tema(s))")

    if "rotation" in improvements:
        swap = {"landscape": "sensorLandscape", "portrait": "sensorPortrait", "userLandscape": "sensorLandscape"}
        n = 0
        for a in activities:
            o = a.get(A + "screenOrientation")
            if o in swap:
                a.set(A + "screenOrientation", swap[o])
                n += 1
        changes.append(f"rotación libre en {n} pantalla(s)")

    if "hwaccel" in improvements:
        app.set(A + "hardwareAccelerated", "true")
        for a in activities:
            a.attrib.pop(A + "hardwareAccelerated", None)
        changes.append("aceleración por hardware activada")

    if "fps" in improvements:
        app.set(A + "appCategory", "game")
        app.set(A + "isGame", "true")
        (src / "res" / "xml").mkdir(parents=True, exist_ok=True)
        (src / "res" / "xml" / "asdkupdate_game_mode.xml").write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<game-mode-config xmlns:android="http://schemas.android.com/apk/res/android"\n'
            '    android:supportsPerformanceGameMode="true"\n'
            '    android:supportsBatteryGameMode="true"\n'
            '    android:allowGameFpsOverride="true"\n'
            '    android:allowGameDownscaling="false" />\n', encoding="utf-8")
        meta("android.game_mode_config", resource="@xml/asdkupdate_game_mode")
        changes.append("modo juego: el sistema / Game Dashboard puede cambiar los FPS (Android 13+)")

    if "fgs" in improvements:
        perms = tree.getroot().findall("uses-permission")
        if any(u.get(A + "name") == "android.permission.FOREGROUND_SERVICE" for u in perms):
            n = 0
            for svc in app.findall("service"):
                if A + "foregroundServiceType" not in svc.attrib:
                    svc.set(A + "foregroundServiceType", "specialUse")  # sin límite de tiempo, a diferencia de dataSync
                    ET.SubElement(svc, "property", {A + "name": "android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE",
                                                    A + "value": "legacy"})
                    n += 1
            special = "android.permission.FOREGROUND_SERVICE_SPECIAL_USE"
            if n and not any(u.get(A + "name") == special for u in perms):
                tree.getroot().insert(list(tree.getroot()).index(app), ET.Element("uses-permission", {A + "name": special}))
            changes.append(f"tipo de servicio en primer plano en {n} servicio(s)")
        else:
            changes.append("servicios en primer plano: la app no los usa, nada que cambiar")

    if "edge" in improvements:
        themes = {app.get(A + "theme")} | {a.get(A + "theme") for a in activities}
        styled = _add_style_item(src, themes, "android:windowOptOutEdgeToEdgeEnforcement", "true")
        changes.append(f"edge-to-edge desactivado en {styled} tema(s)"
                       + (" (Android 16+ lo ignora: usa API 35 o menos)" if target > 35 else ""))

    smali_fixes = [f for f in ("pendingintent", "receiver", "fileuri") if f in improvements]
    if smali_fixes:
        changes += _patch_smali(src, tree.getroot(), smali_fixes)

    tree.write(manifest_path, encoding="utf-8", xml_declaration=True)
    for c in changes:
        log("  + " + c)
    return changes


def _add_style_item(src, theme_refs, item, value):
    """Añade <item name=...> a los estilos usados como tema en res/values*/styles.xml."""
    names = {t.split("/", 1)[1] for t in theme_refs if t and t.startswith("@style/")}
    count = 0
    for styles in (Path(src) / "res").glob("values*/styles.xml"):
        tree = ET.parse(styles)
        touched = False
        for style in tree.getroot().findall("style"):
            if style.get("name") in names and not any(i.get("name") == item for i in style.findall("item")):
                ET.SubElement(style, "item", {"name": item}).text = value
                touched = True
                count += 1
        if touched:
            tree.write(styles, encoding="utf-8", xml_declaration=True)
    return count


def _patch_smali(src, manifest, fixes):
    """Redirige llamadas peligrosas a Lasdkupdate/Fix; (mismos registros, sin tocar la lógica del juego)."""
    changes, pi, rr = [], 0, 0
    # sin la propia Fix.smali: si no, sus llamadas a PendingIntent se redirigirían a sí misma (recursión infinita)
    files = [f for f in Path(src).glob("smali*/**/*.smali") if not f.as_posix().endswith("/asdkupdate/Fix.smali")]
    for f in files:
        text = f.read_text(encoding="utf-8")
        new = text
        if "pendingintent" in fixes:
            for sig in FIX_PI_SIGS:
                new = new.replace("Landroid/app/PendingIntent;->" + sig, "Lasdkupdate/Fix;->" + sig)
        if "receiver" in fixes:
            new = RECEIVER_RE.sub(r"invoke-static\1 {\2}, Lasdkupdate/Fix;->registerReceiver(Landroid/content/Context;\3)"
                                  r"Landroid/content/Intent;", new)
        if new != text:
            pi += new.count("Lasdkupdate/Fix;->get") - text.count("Lasdkupdate/Fix;->get")
            rr += new.count("Lasdkupdate/Fix;->registerReceiver") - text.count("Lasdkupdate/Fix;->registerReceiver")
            f.write_text(new, encoding="utf-8")
    if "pendingintent" in fixes:
        changes.append(f"PendingIntent corregido en {pi} llamada(s)")
    if "receiver" in fixes:
        changes.append(f"registerReceiver corregido en {rr} llamada(s)")
    injected = False
    if "fileuri" in fixes:
        msg, injected = _inject_init(src, manifest, files)
        changes.append(msg)

    if not (pi or rr or injected):
        return changes
    fix = next(Path(src).glob("smali*/asdkupdate/Fix.smali"), None)
    if fix is None:
        # en un dex nuevo para no pasar el límite de 64K métodos del dex principal
        n = 2
        while (Path(src) / f"smali_classes{n}").exists():
            n += 1
        fix = Path(src) / f"smali_classes{n}" / "asdkupdate" / "Fix.smali"
        fix.parent.mkdir(parents=True)
    fix.write_text(FIX_SMALI, encoding="utf-8")
    return changes


def _inject_init(src, manifest, files):
    """Llama a Fix.init() al arrancar: en Application.onCreate o en onCreate de la actividad principal."""
    pkg = manifest.get("package", "")
    app = manifest.find("application")
    targets = []
    if app.get(A + "name"):
        targets.append((app.get(A + "name"), ".method public onCreate()V"))
    for a in app:
        if a.tag in ("activity", "activity-alias") and any(c.get(A + "name") == "android.intent.category.LAUNCHER"
                                                           for c in a.iter("category")):
            name = a.get(A + "targetActivity") or a.get(A + "name")
            targets.append((name, ".method public onCreate(Landroid/os/Bundle;)V"))
            targets.append((name, ".method protected onCreate(Landroid/os/Bundle;)V"))
    for cls, method in targets:
        cls = pkg + cls if cls.startswith(".") else cls
        path = "/".join(cls.split(".")) + ".smali"
        for f in files:
            if f.as_posix().endswith("/" + path):
                text = f.read_text(encoding="utf-8")
                if "Lasdkupdate/Fix;->init()V" in text:
                    return "file:// ya estaba corregido", False
                m = re.search(re.escape(method) + r"\n\s*\.(locals|registers) \d+\n", text)
                if m:
                    f.write_text(text[:m.end()] + "    invoke-static {}, Lasdkupdate/Fix;->init()V\n" + text[m.end():],
                                 encoding="utf-8")
                    return f"file:// corregido al iniciar ({cls.rsplit('.', 1)[-1]})", True
    return "file://: no encontré onCreate de la app ni de la actividad principal (no se cambió)", False


def build(src, log):
    src = Path(src)
    out = src.with_name(src.name[:-4] + "_mod.apk") if src.name.endswith("-src") else src.with_suffix(".apk")
    unsigned, aligned = src / "build-unsigned.apk", src / "build-aligned.apk"
    java = find_java()
    run([java, "-jar", ensure_apktool(log), "b", "-f", "-o", str(unsigned), str(src)], log)
    run([sdk_tool("zipalign"), "-f", "-P", "16", "4", str(unsigned), str(aligned)], log)  # .so a 16 KB

    ks = Path.home() / ".android" / "debug.keystore"
    if not ks.exists():
        ks.parent.mkdir(parents=True, exist_ok=True)
        keytool = "keytool" if java == "java" else str(Path(java).with_name("keytool"))
        run([keytool, "-genkeypair", "-keystore", str(ks), "-storepass", "android", "-keypass", "android",
             "-alias", "androiddebugkey", "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000",
             "-dname", "CN=Android Debug,O=Android,C=US"], log)
    run([sdk_tool("apksigner"), "sign", "--ks", str(ks), "--ks-pass", "pass:android",
         "--out", str(out), str(aligned)], log)
    for f in (unsigned, aligned, Path(str(out) + ".idsig")):
        f.unlink(missing_ok=True)
    log(f"APK listo: {out}")
    return out


def install(apk, log):
    adb = shutil.which("adb") or str(find_build_tools().parent.parent / "platform-tools" / "adb")
    run([adb, "install", "-r", str(apk)], log)


# ------------------------------------------------------------------ interfaz

def gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk

    root = tk.Tk()
    root.title("aSDKupdate")
    root.geometry("780x820")
    apk_var, src_var = tk.StringVar(), tk.StringVar()
    version_var = tk.StringVar(value="Android 16 (API 36)")
    checks = {k: tk.BooleanVar(value=k in ("widescreen", "fps")) for k in IMPROVEMENTS}
    checks.update({k: tk.BooleanVar(value=True) for k in FIXES})
    state = {"out": None}

    frm = ttk.Frame(root, padding=10)
    frm.pack(fill="both", expand=True)
    frm.columnconfigure(1, weight=1)

    def pick_apk():
        f = filedialog.askopenfilename(filetypes=[("APK", "*.apk"), ("Todos", "*.*")])
        if f:
            apk_var.set(f)
            src_var.set(str(src_dir(f)) if src_dir(f).exists() else "")

    def pick_src():
        d = filedialog.askdirectory()
        if d:
            src_var.set(d)

    ttk.Label(frm, text="APK:").grid(row=0, column=0, sticky="w")
    ttk.Entry(frm, textvariable=apk_var).grid(row=0, column=1, sticky="ew", padx=5)
    ttk.Button(frm, text="Elegir…", command=pick_apk).grid(row=0, column=2)
    ttk.Label(frm, text="Carpeta decompilada:").grid(row=1, column=0, sticky="w")
    ttk.Entry(frm, textvariable=src_var).grid(row=1, column=1, sticky="ew", padx=5)
    ttk.Button(frm, text="Elegir…", command=pick_src).grid(row=1, column=2)

    sdk = ttk.LabelFrame(frm, text="Versión de Android para la que se arma", padding=6)
    sdk.grid(row=2, column=0, columnspan=3, sticky="ew", pady=6)
    ttk.Combobox(sdk, textvariable=version_var, values=[v for v, _ in ANDROID_VERSIONS],
                 state="readonly", width=24).pack(side="left")
    ttk.Label(sdk, text="  (API 24 = la que menos cambia; Android 15/16/17 no instalan menos de 24)").pack(side="left")

    for row, (title, options) in enumerate((("Mejoras", IMPROVEMENTS),
                                            ("Correcciones automáticas (para que no se cierre al subir el SDK)", FIXES)), 3):
        box = ttk.LabelFrame(frm, text=title, padding=6)
        box.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        for k, text in options.items():
            ttk.Checkbutton(box, text=text, variable=checks[k]).pack(anchor="w")

    btns = ttk.Frame(frm)
    btns.grid(row=5, column=0, columnspan=3, pady=8, sticky="ew")
    log_box = scrolledtext.ScrolledText(frm, height=14, font=("Consolas", 9))
    log_box.grid(row=6, column=0, columnspan=3, sticky="nsew")
    frm.rowconfigure(6, weight=1)

    def log(msg):
        root.after(0, lambda: (log_box.insert("end", msg + "\n"), log_box.see("end")))

    def target():
        return dict(ANDROID_VERSIONS)[version_var.get()]

    def task(fn):
        def worker():
            for b in btns.winfo_children():
                b.state(["disabled"])
            try:
                fn()
            except Exception as e:
                log("ERROR: " + str(e))
                root.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally:
                root.after(0, lambda: [b.state(["!disabled"]) for b in btns.winfo_children()])
        threading.Thread(target=worker, daemon=True).start()

    def do_decompile():
        if not apk_var.get():
            raise RuntimeError("Elige un APK primero")
        src_var.set(str(decompile(apk_var.get(), log)))

    def do_patch():
        if not src_var.get():
            raise RuntimeError("Primero decompila (o elige una carpeta decompilada)")
        patch(src_var.get(), target(), [k for k, v in checks.items() if v.get()], log)
        log("Mejoras aplicadas. Puedes editar la carpeta a mano antes de armar.")

    def do_build():
        if not src_var.get():
            raise RuntimeError("Elige la carpeta decompilada")
        state["out"] = build(src_var.get(), log)

    def do_all():
        do_decompile()
        do_patch()
        do_build()

    def open_folder():
        if src_var.get():
            if sys.platform == "win32":
                os.startfile(src_var.get())
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", src_var.get()])

    def do_install():
        if not state["out"]:
            raise RuntimeError("Primero arma el APK")
        install(state["out"], log)

    for text, fn in (("1. Decompilar", do_decompile), ("2. Aplicar mejoras", do_patch),
                     ("3. Armar y firmar", do_build), ("Todo (1+2+3)", do_all),
                     ("Instalar (adb)", do_install)):
        ttk.Button(btns, text=text, command=lambda f=fn: task(f)).pack(side="left", padx=2)
    ttk.Button(btns, text="Abrir carpeta", command=open_folder).pack(side="right")

    log("Elige un APK y pulsa 1, 2 y 3 (o 'Todo'). Entre 2 y 3 puedes editar smali/res a mano.")
    log("Desinstala la app original antes de instalar la modificada (la firma cambia).")
    root.mainloop()


def main():
    if len(sys.argv) == 1:
        return gui()
    p = argparse.ArgumentParser(description="Decompila, mejora y vuelve a armar un APK.")
    p.add_argument("apk")
    p.add_argument("--target", type=int, default=36, help="targetSdkVersion (0 = no cambiar). Defecto 36")
    for k, text in {**IMPROVEMENTS, **FIXES}.items():
        p.add_argument("--" + k, action="store_true", help=text)
    p.add_argument("--todo", action="store_true", help="todas las mejoras y correcciones")
    p.add_argument("--solo-decompilar", action="store_true", help="decompila y aplica mejoras, sin armar")
    a = p.parse_args()
    if a.target and a.target < MIN_INSTALLABLE:
        p.error(f"--target debe ser 0 o >= {MIN_INSTALLABLE}")
    src = decompile(a.apk, print)
    patch(src, a.target, [k for k in {**IMPROVEMENTS, **FIXES} if a.todo or getattr(a, k)], print)
    if not a.solo_decompilar:
        build(src, print)


if __name__ == "__main__":
    main()
