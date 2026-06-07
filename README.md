# Argus SSH

<p align="center">
  <img src="logo.ico" width="150" alt="Argus SSH Logo">
</p>

<h1 align="center">Argus SSH</h1>

A modern PyQt5 desktop client for managing SSH-enabled Unix-like servers with a polished interface, built-in terminal access, SFTP file management, and remote Python process controls.

> **Target environment:** Linux/macOS-style SSH hosts. The app uses commands such as `ps`, `kill`, `nohup`, `readlink`, and `python3`, so the remote machine should support standard POSIX shell tooling.

## Highlights

- Saved SSH host profiles with password or private-key authentication
- Integrated live terminal with command history and prompt handling
- SFTP file manager with upload, download, delete, folder creation, and directory navigation
- Python App menu for running selected `.py` files in the background
- Remote Python process monitor with pause, resume, stop, and restart actions
- Animated toast notifications for success, error, and info events
- Customizable visual theme with color pickers and font size control
- Optional QR-code-based donation dialog
- Quick access button that opens the host purchase Telegram channel
- Local configuration storage inside the user’s Documents folder

## Screenshots

_Add screenshots here after packaging or releasing the project._

## Project Structure

This repository is organized as follows:

- `main/main.py` — the main PyQt5 application
- `logo.ico` — project icon
- `requirements.txt` — Python dependencies
- `README.md` — project documentation

Runtime data is stored locally here:

- `~/Documents/ssh_manager/hosts.json`
- `~/Documents/ssh_manager/settings.json`

## Requirements

- Python 3.10 or newer
- PyQt5
- Paramiko
- qrcode with Pillow support

## Installation

```bash
git clone https://github.com/wtfchampion/Argus-SSH.git
cd Argus-SSH
pip install -r requirements.txt
````

## Run

```bash
python main/main.py
```

On some systems you may need:

```bash
python3 main/main.py
```

## How It Works

1. Add a host from the sidebar.
2. Enter the host address, port, username, and either a password or SSH private key.
3. Connect to the server.
4. Use the left side for remote files and the right side for the live terminal.
5. Open **Python App** to run or monitor selected Python scripts on the remote host.

## Feature Notes

### Saved Hosts

Argus SSH stores your host entries locally so you can reconnect quickly without retyping credentials every time.

### Terminal

The integrated terminal lets you type directly into the remote shell and keeps the experience close to a real SSH session.

### SFTP Manager

The SFTP panel supports common file operations and can optionally show hidden files from the settings dialog.

### Python App Menu

The Python menu is designed for remote `.py` files. It launches scripts in the background and writes output into a log file beside the script.

### Process Monitoring

The process monitor scans running Python processes and lets you pause, resume, stop, or restart a process from its original working directory.

### Appearance Settings

The settings dialog allows color customization for the UI, font-size adjustments, and toggling hidden-file visibility.

## Security Notes

* Host key auto-acceptance is enabled in the current implementation.
* Credentials and saved host data are stored locally on the machine running the app.
* Use trusted servers and secure credentials.

## International-Ready Design

This project is a good fit for an international release because it already follows a clean, English-first UI structure and keeps the core logic independent of any single region or language.

Recommended next steps for a global release:

* add translation support with Qt Linguist or a custom i18n layer
* review all UI strings for consistency and tone
* replace placeholder branding or wallet text with your final production values
* add release builds for Windows, Linux, and macOS

## Roadmap

* stronger host-key verification
* multi-language support
* session logging and export
* improved packaging for cross-platform distribution
* optional theming presets

## License

Add your preferred license before publishing the project publicly.

## Credits

Created for **Champ Studio** and **wtfchampion**.

Telegram: [https://t.me/Champ_Studio](https://t.me/Champ_Studio)
