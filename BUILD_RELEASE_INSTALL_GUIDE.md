# Build, Release, and Installation Guide

This document summarizes how to build, create a release, and install the POS Printer application.

## 1. Building the application

### Quick build for non-developers
1. Run `build.ps1` with administrator privileges.
2. The script checks for Python, sets up a virtual environment and installs packages.
3. PyInstaller generates `POSPrinter.exe` and prepares install files under `C:\Pos Printer`.

### Clean build for releases
1. Execute `build_clean.ps1 -Version "<version>" -OutputPath "./release"`.
2. The script disables the USB hook temporarily, runs `deployment_guide.ps1`, then restores the hook.
3. Distribution files are generated in the specified output folder.

### Developer build
To build manually with version tagging:
```powershell
.\deployment_guide.ps1 -Version "1.0.0" -OutputPath ".\release"
```

## 2. Releasing a new version
1. Make sure your Git working tree is clean.
2. Run `release.ps1 -Version "<version>" -Message "<changelog>"`.
   - Updates `version.json`.
   - Runs `build_clean.ps1` to create `./release` files.
   - Compresses them into `POSPrinter_v<version>.zip`.
   - Tags the commit and creates a GitHub release using the `gh` CLI.
3. The GitHub Actions workflow `.github/workflows/release.yml` also builds when a tag `v*.*.*` is pushed.

## 3. Installing the program
### From a release package
1. Download `POSPrinter_v<version>.zip` from the [Releases](../../releases) page.
2. Extract the archive on the desktop.
3. Double-click `easy_install.bat` (or run `build.ps1`) to install.
4. After installation, `POSPrinter.exe` is placed in `C:\Pos Printer` and a desktop shortcut named **POS Printer** is created.

### Manual installation after building
1. After running `build.ps1`, open the generated `POS_Printer_Release` folder.
2. Execute `설치.ps1` with PowerShell (Run as administrator).
3. Follow on-screen instructions to finish the installation.

For troubleshooting and detailed steps, see [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md).
