package com.apk.editor.activities;

import android.app.Activity;
import android.net.Uri;
import android.os.Bundle;
import android.text.TextUtils;
import android.view.View;
import android.widget.RadioGroup;

import androidx.annotation.Nullable;
import androidx.appcompat.widget.AppCompatImageButton;
import androidx.documentfile.provider.DocumentFile;

import com.apk.editor.R;
import com.apk.editor.utils.APKData;
import com.apk.editor.utils.APKPicker;
import com.apk.editor.utils.APKSigner;
import com.apk.editor.utils.SdkUpgrader;
import com.apk.editor.utils.Serializables.APKPickerItems;
import com.apk.editor.utils.SplitAPKInstaller;
import com.apk.editor.utils.dialogs.BundleInstallDialog;
import com.apk.editor.utils.dialogs.ProgressDialog;
import com.google.android.material.button.MaterialButton;
import com.google.android.material.card.MaterialCardView;
import com.google.android.material.materialswitch.MaterialSwitch;
import com.google.android.material.textfield.TextInputEditText;
import com.google.android.material.textfield.TextInputLayout;
import com.google.android.material.textview.MaterialTextView;

import java.io.File;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

import in.sunilpaulmathew.sCommon.CommonUtils.sExecutor;
import in.sunilpaulmathew.sCommon.FileUtils.sFileUtils;
import in.sunilpaulmathew.sCommon.PackageUtils.sPackageUtils;

/*
 * "Compatibilidad Android 16": sube el targetSdk de un APK (o de todos los APK de un bundle instalado),
 * corrige el manifest, lo alinea y lo firma para que se pueda instalar en Android 16.
 * Parte de Zenith APK Editor (fork de APK Explorer & Editor), GPL-3.0.
 */
public class Android16Activity extends BaseActivity {

    public static final String APK_PATH_INTENT = "apk_path", PACKAGE_NAME_INTENT = "package_name", URI_INTENT = "apk_uri";

    private final List<String> mInputs = new ArrayList<>();
    private MaterialButton mApply, mInstall;
    private MaterialCardView mReportCard;
    private MaterialSwitch mFixExported, mRaiseMin;
    private MaterialTextView mAppInfo, mReport;
    private RadioGroup mModeGroup;
    private TextInputEditText mCustomSdk;
    private TextInputLayout mCustomLayout;
    private File mOutput;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_android16, R.id.layout_root);

        AppCompatImageButton back = findViewById(R.id.back);
        mAppInfo = findViewById(R.id.app_info);
        mModeGroup = findViewById(R.id.mode_group);
        mCustomLayout = findViewById(R.id.custom_layout);
        mCustomSdk = findViewById(R.id.custom_sdk);
        mFixExported = findViewById(R.id.fix_exported);
        mRaiseMin = findViewById(R.id.raise_min);
        mApply = findViewById(R.id.apply);
        mReportCard = findViewById(R.id.report_card);
        mReport = findViewById(R.id.report);
        mInstall = findViewById(R.id.install);

        back.setOnClickListener(v -> finish());
        mModeGroup.setOnCheckedChangeListener((group, checkedId) ->
                mCustomLayout.setVisibility(checkedId == R.id.mode_custom ? View.VISIBLE : View.GONE));
        mApply.setOnClickListener(v -> {
            int target = getTargetSdk();
            if (target < SdkUpgrader.MIN_INSTALLABLE_API || target > 99) {
                mCustomLayout.setError(getString(R.string.android16_custom_error, SdkUpgrader.MIN_INSTALLABLE_API));
                return;
            }
            mCustomLayout.setError(null);
            patch(target).execute();
        });
        mInstall.setOnClickListener(v -> install());

        load().execute();
    }

    private int getTargetSdk() {
        int checked = mModeGroup.getCheckedRadioButtonId();
        if (checked == R.id.mode_min) return SdkUpgrader.MIN_INSTALLABLE_API;
        if (checked == R.id.mode_custom) {
            try {
                return Integer.parseInt(Objects.requireNonNull(mCustomSdk.getText()).toString().trim());
            } catch (Exception e) {
                return -1;
            }
        }
        return SdkUpgrader.ANDROID_16_API;
    }

    /* Resuelve la entrada (archivo, URI o app instalada) y muestra el SDK actual */
    private sExecutor load() {
        return new sExecutor() {
            private final Activity mActivity = Android16Activity.this;
            private String mInfo;

            @Override
            public void onPreExecute() {
                mAppInfo.setText(R.string.loading);
            }

            @Override
            public void doInBackground() {
                String apkPath = getIntent().getStringExtra(APK_PATH_INTENT);
                Uri uri = getIntent().getParcelableExtra(URI_INTENT);
                String packageName = getIntent().getStringExtra(PACKAGE_NAME_INTENT);

                if (apkPath == null && uri != null) {
                    String fileName = Objects.requireNonNull(DocumentFile.fromSingleUri(mActivity, uri)).getName();
                    File apkFile = new File(mActivity.getExternalFilesDir("APK"), Objects.requireNonNull(fileName));
                    sFileUtils.copy(uri, apkFile, mActivity);
                    if (apkFile.exists()) apkPath = apkFile.getAbsolutePath();
                }
                if (apkPath == null && packageName != null && sPackageUtils.isPackageInstalled(packageName, mActivity)) {
                    String sourceDir = sPackageUtils.getSourceDir(packageName, mActivity);
                    if (APKData.isAppBundle(sourceDir)) {
                        mInputs.addAll(APKData.splitApks(sourceDir));
                    } else {
                        apkPath = sourceDir;
                    }
                }
                if (apkPath != null) mInputs.add(apkPath);
                if (mInputs.isEmpty()) return;

                StringBuilder sb = new StringBuilder();
                for (String input : mInputs) {
                    try {
                        SdkUpgrader.Report r = SdkUpgrader.inspect(new File(input));
                        if (r.isSplit) continue;
                        sb.append(getString(R.string.android16_info, r.packageName, r.oldMinSdk, r.oldTargetSdk));
                        if (r.oldTargetSdk < SdkUpgrader.MIN_INSTALLABLE_API) {
                            sb.append("\n\n").append(getString(R.string.android16_blocked, SdkUpgrader.MIN_INSTALLABLE_API));
                        }
                    } catch (Exception e) {
                        sb.append(new File(input).getName()).append(": ").append(e.getMessage());
                    }
                }
                if (mInputs.size() > 1) {
                    sb.append("\n\n").append(getString(R.string.android16_bundle, mInputs.size()));
                }
                mInfo = sb.toString();
            }

            @Override
            public void onPostExecute() {
                if (mInputs.isEmpty()) {
                    mAppInfo.setText(R.string.android16_no_input);
                    return;
                }
                mAppInfo.setText(mInfo);
                mApply.setEnabled(true);
            }
        };
    }

    private sExecutor patch(int targetSdk) {
        return new sExecutor() {
            private final Activity mActivity = Android16Activity.this;
            private final StringBuilder mLog = new StringBuilder();
            private boolean mSuccess = true;
            private ProgressDialog mProgressDialog;

            @Override
            public void onPreExecute() {
                mApply.setEnabled(false);
                mInstall.setVisibility(View.GONE);
                mProgressDialog = new ProgressDialog(mActivity);
                mProgressDialog.setTitle(getString(R.string.android16_progress));
                mProgressDialog.setIcon(R.mipmap.ic_launcher);
                mProgressDialog.setIndeterminate(true);
                mProgressDialog.show();
            }

            @Override
            public void doInBackground() {
                SdkUpgrader.Options options = new SdkUpgrader.Options();
                options.targetSdk = targetSdk;
                options.fixExported = mFixExported.isChecked();
                options.raiseMinSdk = mRaiseMin.isChecked();

                boolean bundle = mInputs.size() > 1;
                String baseName = null;
                try {
                    baseName = SdkUpgrader.inspect(new File(mInputs.get(0))).packageName;
                } catch (Exception ignored) {
                }
                if (TextUtils.isEmpty(baseName)) baseName = new File(mInputs.get(0)).getName().replace(".apk", "");

                mOutput = new File(APKData.getExportPath(mActivity), baseName + "_api" + targetSdk + (bundle ? "" : ".apk"));
                if (mOutput.exists()) sFileUtils.delete(mOutput);
                if (bundle) sFileUtils.mkdir(mOutput);

                for (String input : mInputs) {
                    File in = new File(input);
                    File unsigned = new File(mActivity.getCacheDir(), "android16_unsigned.apk");
                    File out = bundle ? new File(mOutput, in.getName()) : mOutput;
                    try {
                        SdkUpgrader.Report report = SdkUpgrader.upgrade(in, unsigned, options, mActivity.getCacheDir());
                        new APKSigner().sign(unsigned, out, mActivity);
                        if (bundle) mLog.append("▸ ").append(in.getName()).append('\n');
                        for (String change : report.changes) mLog.append("✓ ").append(change).append('\n');
                        for (String warning : report.warnings) mLog.append("⚠ ").append(warning).append('\n');
                    } catch (Exception e) {
                        mSuccess = false;
                        mLog.append("✗ ").append(in.getName()).append(": ").append(e.getMessage()).append('\n');
                    } finally {
                        sFileUtils.delete(unsigned);
                    }
                }
                if (!mSuccess) {
                    sFileUtils.delete(mOutput);
                }
            }

            @Override
            public void onPostExecute() {
                try {
                    mProgressDialog.dismiss();
                } catch (IllegalArgumentException ignored) {
                }
                mApply.setEnabled(true);
                mReportCard.setVisibility(View.VISIBLE);
                String header = mSuccess ? getString(R.string.android16_done, mOutput.getAbsolutePath())
                        : getString(R.string.android16_failed);
                mReport.setText(header + "\n\n" + mLog.toString().trim());
                mInstall.setVisibility(mSuccess ? View.VISIBLE : View.GONE);
            }
        };
    }

    private void install() {
        if (mOutput == null || !mOutput.exists()) return;
        if (mOutput.isDirectory()) {
            List<APKPickerItems> apks = new ArrayList<>();
            for (File file : Objects.requireNonNull(mOutput.listFiles())) {
                if (file.isFile() && file.getName().endsWith(".apk")) {
                    apks.add(new APKPickerItems(file, APKPicker.isSelectedAPK(file, this)));
                }
            }
            new BundleInstallDialog(apks, true, this);
        } else {
            SplitAPKInstaller.installAPK(true, mOutput, this);
        }
    }

}
