# 🎮 Phone Gamepad

Turn your **Android phone into a gamepad for your PC**. Games see a real virtual **Xbox 360** or **DualShock 4** controller. Free, no ads, no subscriptions, no internet needed: it works over your local Wi-Fi.

> ⚠️ **Hobby project, may contain bugs.** Sometimes the first connection to the PC is a bit glitchy. If that happens, wait a few seconds and reconnect (see [Troubleshooting](#troubleshooting)).

## ⬇️ Download

| | Direct link | Requirements |
|---|---|---|
| 📱 **Android app** | [`PhoneGamepad.apk`](https://github.com/vovakiller-2014/PhoneGamepad/releases/latest/download/PhoneGamepad.apk) | Android 8.0+ |
| 🖥️ **Windows app** | [`PhoneGamepad-PC.exe`](https://github.com/vovakiller-2014/PhoneGamepad/releases/latest/download/PhoneGamepad-PC.exe) | Windows 10/11 + [ViGEmBus driver](https://github.com/nefarius/ViGEmBus/releases) |

All versions and release notes: [Releases page](https://github.com/vovakiller-2014/PhoneGamepad/releases).

## ✨ Features

**Controller**
- Virtual **Xbox 360** or **DualShock 4** (per slot), up to **8 phones** at once
- Connect by **QR code + PIN** over Wi-Fi: same network, phone hotspot or USB tethering (no internet required)
- Force-feedback: **game rumble is forwarded to your phone**, plus haptics on buttons

**Layouts**
- Ready-made layouts: Xbox, PlayStation, Racing (wheel), Racing (tilt)
- Create unlimited custom layouts from Xbox, PlayStation or a completely empty screen
- Full editor: move, resize and recolor anything, add any text or emoji to buttons, per-element **RGB glow border**
- **Custom background**: pick any color (default pure black for AMOLED) or load your own controller image

**Elements**
- Buttons, analog sticks, sliders
- **Steering wheel** with 3 styles (ring, classic, F1), adjustable lock angle, auto-center, speed and presets (Drift / Normal / Precise)
- **Tilt steering** using the phone's gyroscope
- **H-shifter and Automatic gearbox**: hold the small button, slide your finger over the popup gate to select a gear. Gears are sent as keyboard keys you choose, so bind them in your game
- Smoothing, response curve, deadzone and sensitivity for every analog element

**Extras**
- Layout backup / restore, English and Ukrainian UI, AMOLED-friendly black design

## 🚀 Quick start

**On the PC (one time setup)**
1. Install the **ViGEmBus** driver ([download](https://github.com/nefarius/ViGEmBus/releases), file `ViGEmBus_…_x64_x86_arm64.exe`) and restart the PC.
2. Run `PhoneGamepad-PC.exe`. Allow it through the firewall for **private networks**.
   Windows may warn about an unknown publisher: click **More info → Run anyway**.

**On the phone**
1. Install `PhoneGamepad.apk` (allow installs from your browser/file manager; if Play Protect warns, choose **Install anyway**).
2. Put the phone and PC on the **same Wi-Fi** (or turn on the phone's hotspot / USB tethering).
3. Open the app → **Connect → Wi-Fi → Scan QR** and point the camera at the QR code in the PC window.
4. Pick a layout and play. In the PC window you can choose **Xbox** or **PlayStation** for each slot.

**Gearboxes:** the game window must be in focus. Set the keys in the element settings (e.g. `1`–`6`, `r`) and bind the same keys in your game.

## 🛠️ Troubleshooting

- **Can't connect / connection is glitchy:** wait a few seconds and try again. Make sure both devices are on the same network, press **Refresh address** in the PC app, then scan the QR again.
- **Driver error:** install ViGEmBus and restart the PC.
- **No rumble in a game:** enable controller vibration in the game's settings; use **Test vibration** in the PC app to check the phone.
- **Windows blocks the .exe:** SmartScreen → *More info → Run anyway*. With **Smart App Control** on Windows 11, unsigned apps are blocked until you turn it off (Windows Security → App & browser control).
- **Antivirus warning:** the exe is built with PyInstaller, which sometimes triggers false positives. The code is open.

## ⚠️ Known limitations

- This is a hobby project and **may contain bugs**.
- **PlayStation (DS4) mode** and **Bluetooth** are experimental. Wi-Fi is recommended.
- Gearbox keys work only while the game window is active.
- Games that don't send controller vibration won't vibrate the phone.

## 🔧 Building

Built automatically with GitHub Actions: branch `PhoneApp` produces the APK, branch `PCApp` produces the EXE.
