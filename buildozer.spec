[app]
title = Cooler Control
package.name = coolercontrol
package.domain = org.cooler

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ico
source.exclude_dirs = bin,.buildozer,build,dist,__pycache__,assets

version = 1.0.0

requirements = python3,kivy==2.2.1,pyjnius

orientation = portrait
fullscreen = 0

android.permissions = BLUETOOTH, BLUETOOTH_ADMIN, BLUETOOTH_CONNECT, BLUETOOTH_SCAN

android.api = 31
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a

android.accept_sdk_license = True
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1
