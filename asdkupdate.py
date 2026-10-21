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

IMPROVEMENTS = {
    "fps": "FPS dinámicos / 60+ fps (modo juego Android 13+, permite al sistema cambiar los FPS)",
    "widescreen": "Pantalla ancha (sin franjas negras, cualquier relación de aspecto)",
    "notch": "Usar el área del notch / cámara",
    "rotation": "Girar en ambos sentidos (horizontal y vertical invertidas)",
    "hwaccel": "Aceleración por hardware (juegos viejos van más fluidos)",
}


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
    root.geometry("760x620")
    apk_var, src_var = tk.StringVar(), tk.StringVar()
    target_var, custom_var = tk.StringVar(value="36"), tk.StringVar(value="35")
    checks = {k: tk.BooleanVar(value=k in ("widescreen", "fps")) for k in IMPROVEMENTS}
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

    sdk = ttk.LabelFrame(frm, text="SDK objetivo", padding=6)
    sdk.grid(row=2, column=0, columnspan=3, sticky="ew", pady=6)
    ttk.Radiobutton(sdk, text="Android 16 (API 36)", variable=target_var, value="36").pack(side="left")
    ttk.Radiobutton(sdk, text="Mínimo instalable (API 24)", variable=target_var, value="24").pack(side="left", padx=10)
    ttk.Radiobutton(sdk, text="No cambiar", variable=target_var, value="0").pack(side="left")
    ttk.Radiobutton(sdk, text="Otro:", variable=target_var, value="custom").pack(side="left", padx=(10, 0))
    ttk.Spinbox(sdk, from_=MIN_INSTALLABLE, to=99, width=4, textvariable=custom_var).pack(side="left")

    imp = ttk.LabelFrame(frm, text="Mejoras", padding=6)
    imp.grid(row=3, column=0, columnspan=3, sticky="ew")
    for k, text in IMPROVEMENTS.items():
        ttk.Checkbutton(imp, text=text, variable=checks[k]).pack(anchor="w")

    btns = ttk.Frame(frm)
    btns.grid(row=4, column=0, columnspan=3, pady=8, sticky="ew")
    log_box = scrolledtext.ScrolledText(frm, height=14, font=("Consolas", 9))
    log_box.grid(row=5, column=0, columnspan=3, sticky="nsew")
    frm.rowconfigure(5, weight=1)

    def log(msg):
        root.after(0, lambda: (log_box.insert("end", msg + "\n"), log_box.see("end")))

    def target():
        return int(custom_var.get()) if target_var.get() == "custom" else int(target_var.get())

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
        t = target()
        if t and t < MIN_INSTALLABLE:
            raise RuntimeError(f"Android 15/16/17 no instalan apps con targetSdk menor a {MIN_INSTALLABLE}")
        patch(src_var.get(), t, [k for k, v in checks.items() if v.get()], log)
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
    for k, text in IMPROVEMENTS.items():
        p.add_argument("--" + k, action="store_true", help=text)
    p.add_argument("--solo-decompilar", action="store_true", help="decompila y aplica mejoras, sin armar")
    a = p.parse_args()
    if a.target and a.target < MIN_INSTALLABLE:
        p.error(f"--target debe ser 0 o >= {MIN_INSTALLABLE}")
    src = decompile(a.apk, print)
    patch(src, a.target, [k for k in IMPROVEMENTS if getattr(a, k)], print)
    if not a.solo_decompilar:
        build(src, print)


if __name__ == "__main__":
    main()
