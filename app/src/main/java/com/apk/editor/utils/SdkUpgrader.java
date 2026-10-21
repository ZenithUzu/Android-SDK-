package com.apk.editor.utils;

import com.apk.axml.ResourceTableParser;
import com.apk.axml.aXMLDecoder;
import com.apk.axml.aXMLEncoder;
import com.apk.axml.serializables.ResEntry;
import com.apk.axml.serializables.XMLEntry;

import net.lingala.zip4j.ZipFile;
import net.lingala.zip4j.model.FileHeader;
import net.lingala.zip4j.model.ZipParameters;
import net.lingala.zip4j.model.enums.CompressionMethod;

import org.w3c.dom.Attr;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.NamedNodeMap;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;
import org.xml.sax.InputSource;

import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.RandomAccessFile;
import java.io.StringReader;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;

import javax.xml.parsers.DocumentBuilderFactory;

/*
 * Parchea un APK para que se pueda instalar y ejecutar en Android 16 (API 36):
 *  - sube targetSdkVersion (y minSdkVersion si es necesario),
 *  - añade android:exported a los componentes con <intent-filter> (obligatorio desde API 31),
 *  - quita la firma vieja, guarda resources.arsc sin comprimir y alinea (4 bytes / 16 KB para .so),
 *  - revisa si las librerías nativas soportan páginas de 16 KB.
 * El resultado queda SIN firmar; se firma después con APKData.signApks().
 *
 * Parte de Zenith APK Editor (fork de APK Explorer & Editor), GPL-3.0.
 */
public class SdkUpgrader {

    public static final String ANDROID_NS = "http://schemas.android.com/apk/res/android";
    public static final int ANDROID_16_API = 36;
    /* Android 15, 16 y 17 se niegan a instalar apps con targetSdk menor a 24 */
    public static final int MIN_INSTALLABLE_API = 24;

    private static final List<String> COMPONENTS = Arrays.asList("activity", "activity-alias", "service", "receiver");

    public static class Options {
        public int targetSdk = ANDROID_16_API;
        public boolean fixExported = true;
        public boolean raiseMinSdk = false;
    }

    public static class Report {
        public final List<String> changes = new ArrayList<>();
        public final List<String> warnings = new ArrayList<>();
        public String packageName;
        public int oldMinSdk = -1, oldTargetSdk = -1, newTargetSdk = -1;
        public boolean isSplit = false;
    }

    /* Info rápida del manifest, para mostrarla antes de parchear */
    public static Report inspect(File apk) throws Exception {
        Report report = new Report();
        try (ZipFile zip = new ZipFile(apk)) {
            Document doc = parseManifest(zip, new ArrayList<>());
            Element manifest = doc.getDocumentElement();
            report.packageName = manifest.getAttribute("package");
            report.isSplit = manifest.hasAttribute("split");
            Element usesSdk = firstChild(manifest, "uses-sdk");
            report.oldMinSdk = readInt(usesSdk, "minSdkVersion", 1);
            report.oldTargetSdk = readInt(usesSdk, "targetSdkVersion", report.oldMinSdk);
        }
        return report;
    }

    public static Report upgrade(File inApk, File outUnsignedApk, Options options, File tmpDir) throws Exception {
        Report report = new Report();
        File tmpZip = File.createTempFile("sdkupgrade", ".zip", tmpDir);
        //noinspection ResultOfMethodCallIgnored
        tmpZip.delete();

        try (ZipFile inZip = new ZipFile(inApk); ZipFile outZip = new ZipFile(tmpZip)) {
            List<ResEntry> resEntries = new ArrayList<>();
            Document doc = parseManifest(inZip, resEntries);
            restoreStringReferences(doc.getDocumentElement(), resEntries);
            byte[] newManifest = patchManifest(doc, options, report);

            for (FileHeader header : inZip.getFileHeaders()) {
                String name = header.getFileName();
                if (header.isDirectory() || isOldSignature(name)) {
                    continue;
                }
                ZipParameters params = new ZipParameters();
                params.setFileNameInZip(name);
                if (name.equals("AndroidManifest.xml")) {
                    try (InputStream is = new ByteArrayInputStream(newManifest)) {
                        outZip.addStream(is, params);
                    }
                    continue;
                }
                // Android 11+ exige resources.arsc sin comprimir; las .so sin comprimir permiten cargarlas
                // directo del APK. Lo que ya venía sin comprimir (assets/raw de audio, etc.) se respeta.
                boolean store = name.equals("resources.arsc") || name.endsWith(".so")
                        || header.getCompressionMethod() == CompressionMethod.STORE;
                if (store) {
                    params.setCompressionMethod(CompressionMethod.STORE);
                    params.setEntrySize(header.getUncompressedSize());
                }
                try (InputStream is = inZip.getInputStream(header)) {
                    if (name.endsWith(".so")) {
                        checkElf16k(name, inZip, header, report);
                    }
                    outZip.addStream(is, params);
                }
            }
        }

        // zipalign: 4 bytes para todo lo guardado sin comprimir y 16 KB para las .so (Android 15+)
        try (RandomAccessFile unaligned = new RandomAccessFile(tmpZip, "r");
             OutputStream aligned = new FileOutputStream(outUnsignedApk)) {
            ZipAlign.alignZip(unaligned, aligned, 4, 16384);
        } finally {
            //noinspection ResultOfMethodCallIgnored
            tmpZip.delete();
        }
        report.changes.add(tr("Firma anterior eliminada, resources.arsc sin comprimir, APK alineado (4 B / 16 KB)",
                "Old signature removed, resources.arsc stored uncompressed, APK aligned (4 B / 16 KB)"));
        return report;
    }

    /* ---------------------------------- Manifest ---------------------------------- */

    static Document parseManifest(ZipFile zip, List<ResEntry> resOut) throws Exception {
        FileHeader manifestHeader = zip.getFileHeader("AndroidManifest.xml");
        if (manifestHeader == null) {
            throw new IOException(tr("El archivo no tiene AndroidManifest.xml (¿es un APK?)", "No AndroidManifest.xml found (is this an APK?)"));
        }
        List<ResEntry> resEntries = null;
        FileHeader arsc = zip.getFileHeader("resources.arsc");
        if (arsc != null) {
            try (InputStream is = zip.getInputStream(arsc)) {
                resEntries = new ResourceTableParser(is).parse();
            } catch (Exception ignored) {
                resEntries = null;
            }
        }
        if (resEntries != null) resOut.addAll(resEntries);
        List<XMLEntry> entries;
        try (InputStream is = zip.getInputStream(manifestHeader)) {
            entries = (resEntries != null && !resEntries.isEmpty())
                    ? new aXMLDecoder(is, resEntries).decode()
                    : new aXMLDecoder(is).decode();
        }
        // Igual que XMLEditor.xmlEntriesToXML: se descartan debuggable y testOnly (testOnly impide instalar)
        StringBuilder sb = new StringBuilder();
        for (XMLEntry entry : entries) {
            String tag = entry.getTag().trim();
            if (entry.isEmpty() || tag.equals("android:debuggable") || tag.equals("android:testOnly")) continue;
            sb.append(resEntries != null && !resEntries.isEmpty() ? entry.getText(resEntries) : entry.getText()).append("\n");
        }
        String xml = sb.toString().trim();
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        factory.setNamespaceAware(true);
        return factory.newDocumentBuilder().parse(new InputSource(new StringReader(xml)));
    }

    static byte[] patchManifest(Document doc, Options options, Report report) throws Exception {
        Element manifest = doc.getDocumentElement();
        report.packageName = manifest.getAttribute("package");
        report.isSplit = manifest.hasAttribute("split");
        if (!manifest.hasAttribute("xmlns:android")) {
            manifest.setAttributeNS("http://www.w3.org/2000/xmlns/", "xmlns:android", ANDROID_NS);
        }

        Element usesSdk = firstChild(manifest, "uses-sdk");
        report.oldMinSdk = readInt(usesSdk, "minSdkVersion", 1);
        report.oldTargetSdk = readInt(usesSdk, "targetSdkVersion", report.oldMinSdk);
        report.newTargetSdk = report.oldTargetSdk;

        if (report.isSplit) {
            // Los splits (config.arm64_v8a, etc.) heredan el SDK del APK base: solo se reempaquetan.
            report.changes.add(tr("APK dividido (split): manifest sin cambios, solo se reempaqueta y alinea",
                    "Split APK: manifest untouched, only repacked and aligned"));
            return new aXMLEncoder().encode(serialize(doc));
        }

        if (usesSdk == null) {
            usesSdk = doc.createElement("uses-sdk");
            manifest.insertBefore(usesSdk, manifest.getFirstChild());
        }

        if (options.targetSdk > report.oldTargetSdk) {
            usesSdk.setAttributeNS(ANDROID_NS, "android:targetSdkVersion", String.valueOf(options.targetSdk));
            report.newTargetSdk = options.targetSdk;
            report.changes.add("targetSdkVersion: " + report.oldTargetSdk + " → " + options.targetSdk);
        } else {
            report.changes.add(tr("targetSdkVersion ya era " + report.oldTargetSdk + " (no se baja)",
                    "targetSdkVersion was already " + report.oldTargetSdk + " (not lowered)"));
        }

        if (!hasAndroidAttr(usesSdk, "minSdkVersion")) {
            // Sin minSdk el sistema asume 1; lo dejamos explícito para que no cambie el comportamiento.
            usesSdk.setAttributeNS(ANDROID_NS, "android:minSdkVersion", String.valueOf(report.oldMinSdk));
        }
        if (options.raiseMinSdk && report.oldMinSdk < MIN_INSTALLABLE_API) {
            usesSdk.setAttributeNS(ANDROID_NS, "android:minSdkVersion", String.valueOf(MIN_INSTALLABLE_API));
            report.changes.add("minSdkVersion: " + report.oldMinSdk + " → " + MIN_INSTALLABLE_API);
        }
        // maxSdkVersion impediría instalarlo en versiones nuevas
        if (hasAndroidAttr(usesSdk, "maxSdkVersion")) {
            usesSdk.removeAttributeNS(ANDROID_NS, "maxSdkVersion");
            report.changes.add(tr("Se quitó maxSdkVersion (bloqueaba la instalación en Android nuevos)",
                    "Removed maxSdkVersion (it blocked installing on newer Android)"));
        }

        if (options.fixExported && report.newTargetSdk >= 31) {
            int fixed = 0;
            Element application = firstChild(manifest, "application");
            if (application != null) {
                NodeList children = application.getChildNodes();
                for (int i = 0; i < children.getLength(); i++) {
                    if (!(children.item(i) instanceof Element)) continue;
                    Element component = (Element) children.item(i);
                    if (COMPONENTS.contains(component.getTagName()) && !hasAndroidAttr(component, "exported")
                            && firstChild(component, "intent-filter") != null) {
                        // Antes de API 31, tener intent-filter implicaba exported=true: se conserva igual.
                        component.setAttributeNS(ANDROID_NS, "android:exported", "true");
                        fixed++;
                    }
                }
            }
            if (fixed > 0) {
                report.changes.add(tr("android:exported=\"true\" añadido a " + fixed + " componente(s) con intent-filter",
                        "Added android:exported=\"true\" to " + fixed + " component(s) with intent-filter"));
            }
        }

        addBehaviourWarnings(report);
        return new aXMLEncoder().encode(serialize(doc));
    }

    private static void addBehaviourWarnings(Report report) {
        int from = report.oldTargetSdk, to = report.newTargetSdk;
        if (from < 23 && to >= 23) {
            report.warnings.add(tr("API 23+: los permisos peligrosos (cámara, ubicación, almacenamiento…) ahora se piden en tiempo de ejecución; si la app no los pide, concédelos en Ajustes.",
                    "API 23+: dangerous permissions (camera, location, storage…) are now runtime permissions; if the app never asks, grant them in Settings."));
        }
        if (from < 24 && to >= 24) {
            report.warnings.add(tr("API 24+: compartir archivos con file:// lanza FileUriExposedException.",
                    "API 24+: sharing file:// URIs throws FileUriExposedException."));
        }
        if (from < 29 && to >= 29) {
            report.warnings.add(tr("API 29/30+: almacenamiento con alcance (scoped storage); el acceso libre a /sdcard puede fallar.",
                    "API 29/30+: scoped storage; free access to /sdcard may fail."));
        }
        if (from < 31 && to >= 31) {
            report.warnings.add(tr("API 31+: PendingIntent sin FLAG_IMMUTABLE/MUTABLE provoca un crash (notificaciones, alarmas, widgets).",
                    "API 31+: a PendingIntent without FLAG_IMMUTABLE/MUTABLE crashes (notifications, alarms, widgets)."));
        }
        if (from < 34 && to >= 34) {
            report.warnings.add(tr("API 34+: los servicios en primer plano necesitan foregroundServiceType; registerReceiver necesita RECEIVER_EXPORTED/NOT_EXPORTED.",
                    "API 34+: foreground services need foregroundServiceType; registerReceiver needs RECEIVER_EXPORTED/NOT_EXPORTED."));
        }
        if (from < 35 && to >= 35) {
            report.warnings.add(tr("API 35/36: edge-to-edge obligatorio; la interfaz puede quedar debajo de las barras del sistema.",
                    "API 35/36: edge-to-edge is enforced; the UI may draw under the system bars."));
        }
        if (to >= 31) {
            report.warnings.add(tr("Si la app se cierra al abrir, prueba de nuevo con el modo \"Mínimo instalable (API " + MIN_INSTALLABLE_API + ")\".",
                    "If the app crashes on launch, try again with the \"Minimum installable (API " + MIN_INSTALLABLE_API + ")\" mode."));
        }
    }

    /*
     * El decodificador resuelve @string/... a su texto (p. ej. el nombre de la app). Si se re-codifica así,
     * el nombre queda fijo y se pierden las traducciones; aquí se vuelve a poner la referencia al recurso.
     */
    static void restoreStringReferences(Element element, List<ResEntry> resEntries) {
        if (resEntries.isEmpty()) return;
        for (String attr : new String[] {"label", "description"}) {
            if (!element.hasAttributeNS(ANDROID_NS, attr)) continue;
            String value = element.getAttributeNS(ANDROID_NS, attr);
            if (value.isEmpty() || value.startsWith("@") || value.startsWith("?")) continue;
            for (ResEntry entry : resEntries) {
                if (entry.getName() != null && entry.getName().startsWith("@string/") && value.equals(entry.getValue())) {
                    element.setAttributeNS(ANDROID_NS, "android:" + attr, entry.getResAttr());
                    break;
                }
            }
        }
        NodeList nodes = element.getChildNodes();
        for (int i = 0; i < nodes.getLength(); i++) {
            if (nodes.item(i) instanceof Element) restoreStringReferences((Element) nodes.item(i), resEntries);
        }
    }

    /* Serializador simple: el manifest solo tiene elementos y atributos */
    static String serialize(Document doc) {
        StringBuilder sb = new StringBuilder("<?xml version=\"1.0\" encoding=\"utf-8\"?>\n");
        writeElement(doc.getDocumentElement(), sb, 0);
        return sb.toString();
    }

    private static void writeElement(Element element, StringBuilder sb, int depth) {
        indent(sb, depth);
        sb.append('<').append(element.getTagName());
        NamedNodeMap attrs = element.getAttributes();
        for (int i = 0; i < attrs.getLength(); i++) {
            Attr attr = (Attr) attrs.item(i);
            sb.append(' ').append(attr.getName()).append("=\"").append(escape(attr.getValue())).append('"');
        }
        List<Element> children = new ArrayList<>();
        NodeList nodes = element.getChildNodes();
        for (int i = 0; i < nodes.getLength(); i++) {
            if (nodes.item(i).getNodeType() == Node.ELEMENT_NODE) {
                children.add((Element) nodes.item(i));
            }
        }
        if (children.isEmpty()) {
            sb.append(" />\n");
            return;
        }
        sb.append(">\n");
        for (Element child : children) {
            writeElement(child, sb, depth + 1);
        }
        indent(sb, depth);
        sb.append("</").append(element.getTagName()).append(">\n");
    }

    private static void indent(StringBuilder sb, int depth) {
        for (int i = 0; i < depth; i++) sb.append("    ");
    }

    private static String escape(String value) {
        return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;");
    }

    private static Element firstChild(Element parent, String tag) {
        if (parent == null) return null;
        NodeList nodes = parent.getChildNodes();
        for (int i = 0; i < nodes.getLength(); i++) {
            Node node = nodes.item(i);
            if (node instanceof Element && tag.equals(((Element) node).getTagName())) {
                return (Element) node;
            }
        }
        return null;
    }

    private static boolean hasAndroidAttr(Element element, String name) {
        return element != null && (element.hasAttributeNS(ANDROID_NS, name) || element.hasAttribute("android:" + name));
    }

    private static int readInt(Element element, String name, int fallback) {
        if (!hasAndroidAttr(element, name)) return fallback;
        String value = element.hasAttributeNS(ANDROID_NS, name)
                ? element.getAttributeNS(ANDROID_NS, name) : element.getAttribute("android:" + name);
        try {
            return Integer.decode(value.trim());
        } catch (NumberFormatException e) {
            // Codenames de preview ("VanillaIceCream", etc.)
            return fallback;
        }
    }

    private static boolean isOldSignature(String name) {
        if (!name.startsWith("META-INF/")) return false;
        String upper = name.toUpperCase(Locale.ROOT);
        return upper.equals("META-INF/MANIFEST.MF") || upper.endsWith(".SF") || upper.endsWith(".RSA")
                || upper.endsWith(".DSA") || upper.endsWith(".EC") || upper.startsWith("META-INF/SIG-");
    }

    private static String tr(String es, String en) {
        return "es".equals(Locale.getDefault().getLanguage()) ? es : en;
    }

    /* ------------------------------ 16 KB page size ------------------------------ */

    private static void checkElf16k(String name, ZipFile zip, FileHeader header, Report report) {
        // Solo importan las ABIs de 64 bits; es donde hay dispositivos con páginas de 16 KB.
        if (!name.startsWith("lib/arm64-v8a/") && !name.startsWith("lib/x86_64/")) return;
        try (InputStream is = zip.getInputStream(header)) {
            long minAlign = minLoadAlignment(is);
            if (minAlign > 0 && minAlign < 16384) {
                String lib = name.substring(name.lastIndexOf('/') + 1);
                report.warnings.add(tr(lib + ": compilada para páginas de 4 KB; en teléfonos con páginas de 16 KB puede fallar (necesita recompilarse desde el código fuente).",
                        lib + ": built for 4 KB pages; it may fail on 16 KB page-size phones (needs a rebuild from source)."));
            }
        } catch (Exception ignored) {
        }
    }

    /* Lee las cabeceras del ELF y devuelve la menor alineación de los segmentos PT_LOAD (-1 si no aplica) */
    static long minLoadAlignment(InputStream is) throws IOException {
        byte[] head = readUpTo(is, 1 << 20);
        if (head.length < 64 || head[0] != 0x7f || head[1] != 'E' || head[2] != 'L' || head[3] != 'F' || head[4] != 2) {
            return -1;
        }
        ByteBuffer bb = ByteBuffer.wrap(head).order(head[5] == 2 ? ByteOrder.BIG_ENDIAN : ByteOrder.LITTLE_ENDIAN);
        long phoff = bb.getLong(0x20);
        int phentsize = bb.getShort(0x36) & 0xffff;
        int phnum = bb.getShort(0x38) & 0xffff;
        long min = -1;
        for (int i = 0; i < phnum; i++) {
            long off = phoff + (long) i * phentsize;
            if (off + 56 > head.length) break;
            if (bb.getInt((int) off) == 1 /* PT_LOAD */) {
                long align = bb.getLong((int) off + 48);
                if (min < 0 || align < min) min = align;
            }
        }
        return min;
    }

    private static byte[] readUpTo(InputStream is, int max) throws IOException {
        byte[] buf = new byte[max];
        int total = 0, n;
        while (total < max && (n = is.read(buf, total, max - total)) > 0) {
            total += n;
        }
        return Arrays.copyOf(buf, total);
    }

}
