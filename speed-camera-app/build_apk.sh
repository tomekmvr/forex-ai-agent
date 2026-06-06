#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$SCRIPT_DIR/app"
BUILD_DIR="$SCRIPT_DIR/.build-apk"
RELEASES_DIR="$SCRIPT_DIR/releases"

VERSION_CODE=2
VERSION_NAME=1.0.1
MIN_SDK=26
TARGET_SDK=34

ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-/usr/local/lib/android/sdk}}"
BUILD_TOOLS_DIR="$(find "$ANDROID_SDK_ROOT/build-tools" -mindepth 1 -maxdepth 1 -type d | sort -V | tail -n1)"
PLATFORM_DIR="$(find "$ANDROID_SDK_ROOT/platforms" -mindepth 1 -maxdepth 1 -type d -name 'android-34*' | sort -V | head -n1)"

if [[ -z "${BUILD_TOOLS_DIR:-}" || -z "${PLATFORM_DIR:-}" ]]; then
  echo "Nie znaleziono Android SDK build-tools/platforms." >&2
  exit 1
fi

AAPT2="$BUILD_TOOLS_DIR/aapt2"
ZIPALIGN="$BUILD_TOOLS_DIR/zipalign"
APKSIGNER="$BUILD_TOOLS_DIR/apksigner"
D8="$BUILD_TOOLS_DIR/d8"
ANDROID_JAR="$PLATFORM_DIR/android.jar"
KOTLIN_LIB_DIR="$(dirname "$(readlink -f "$(command -v kotlinc)")")/../lib"

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/classes" "$BUILD_DIR/generated" "$RELEASES_DIR"

"$AAPT2" compile \
  --dir "$APP_DIR/src/main/res" \
  -o "$BUILD_DIR/compiled-res.zip"

"$AAPT2" link \
  -o "$BUILD_DIR/base-unsigned.apk" \
  -I "$ANDROID_JAR" \
  --manifest "$APP_DIR/src/main/AndroidManifest.xml" \
  --java "$BUILD_DIR/generated" \
  --auto-add-overlay \
  --min-sdk-version "$MIN_SDK" \
  --target-sdk-version "$TARGET_SDK" \
  --version-code "$VERSION_CODE" \
  --version-name "$VERSION_NAME" \
  -A "$APP_DIR/src/main/assets" \
  "$BUILD_DIR/compiled-res.zip"

javac \
  -source 17 \
  -target 17 \
  -encoding UTF-8 \
  -cp "$ANDROID_JAR" \
  -d "$BUILD_DIR/classes" \
  $(find "$BUILD_DIR/generated" -name '*.java' | sort)

kotlinc \
  $(find "$APP_DIR/src/main/kotlin" -name '*.kt' | sort) \
  -classpath "$ANDROID_JAR:$BUILD_DIR/classes" \
  -d "$BUILD_DIR/classes"

jar --create --file "$BUILD_DIR/app-classes.jar" -C "$BUILD_DIR/classes" .
mkdir -p "$BUILD_DIR/dex"

"$D8" \
  --min-api "$MIN_SDK" \
  --output "$BUILD_DIR/dex" \
  "$BUILD_DIR/app-classes.jar" \
  "$KOTLIN_LIB_DIR/kotlin-stdlib.jar" \
  "$KOTLIN_LIB_DIR/kotlin-stdlib-jdk7.jar" \
  "$KOTLIN_LIB_DIR/kotlin-stdlib-jdk8.jar"

(cd "$BUILD_DIR/dex" && zip -q -r "$BUILD_DIR/base-unsigned.apk" .)

"$ZIPALIGN" -f -p 4 "$BUILD_DIR/base-unsigned.apk" "$BUILD_DIR/base-aligned.apk"

DEBUG_KEYSTORE="${HOME}/.android/debug.keystore"
if [[ ! -f "$DEBUG_KEYSTORE" ]]; then
  mkdir -p "${HOME}/.android"
  keytool -genkeypair \
    -keystore "$DEBUG_KEYSTORE" \
    -storepass android \
    -alias androiddebugkey \
    -keypass android \
    -dname "CN=Android Debug,O=Android,C=US" \
    -keyalg RSA \
    -keysize 2048 \
    -validity 10000 >/dev/null 2>&1
fi

OUTPUT_APK="$RELEASES_DIR/FotoradaryPL-v${VERSION_NAME}.apk"
rm -f "$OUTPUT_APK"
"$APKSIGNER" sign \
  --ks "$DEBUG_KEYSTORE" \
  --ks-key-alias androiddebugkey \
  --ks-pass pass:android \
  --key-pass pass:android \
  --out "$OUTPUT_APK" \
  "$BUILD_DIR/base-aligned.apk"

"$APKSIGNER" verify --print-certs "$OUTPUT_APK"
"$AAPT2" dump badging "$OUTPUT_APK" | sed -n '1,30p'
