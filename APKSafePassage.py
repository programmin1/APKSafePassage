import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import os
import threading
import shlex
import tempfile
import zipfile
from datetime import datetime

# Configuration
BACKUP_DIR = "backups"

def run_adb_command(command):
    """Executes an adb command and returns the output."""
    try:
        result = subprocess.run(
            shlex.split(command) if isinstance(command, str) else command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False
        )
        if result.returncode:
            return result.stdout.strip(), result.stderr.strip() or f"adb exited with code {result.returncode}"
        return result.stdout.strip(), ""
    except Exception as e:
        return "", str(e)


def parse_apk_paths(output):
    """Parse the individual APK paths returned by `pm path`."""
    return [line.strip()[len("package:"):] for line in output.splitlines()
            if line.strip().startswith("package:") and line.strip()[len("package:"):]]


def backup_apks(device, package, paths):
    """Pull every APK and return the saved APK or split-APK archive name."""
    if not paths:
        raise ValueError(f"No APK paths found for {package}")
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    extension = ".apk" if len(paths) == 1 else ".apks"
    filename = f"{package.replace('.', '_')}_{timestamp}{extension}"
    # Stage all pulls so a failed split cannot leave an incomplete backup.
    with tempfile.TemporaryDirectory(dir=BACKUP_DIR) as staging:
        apk_files = []
        for path in paths:
            local_path = os.path.join(staging, os.path.basename(path))
            out, err = run_adb_command(["adb", "-s", device, "pull", path, local_path])
            if err or not os.path.isfile(local_path) or os.path.getsize(local_path) == 0:
                raise RuntimeError(err or out or f"Failed to pull {path}")
            apk_files.append(local_path)
        local_backup = os.path.join(staging, filename)
        if len(apk_files) == 1:
            os.replace(apk_files[0], local_backup)
        else:
            with zipfile.ZipFile(local_backup, "w", zipfile.ZIP_DEFLATED) as archive:
                for apk_file in apk_files:
                    archive.write(apk_file, os.path.basename(apk_file))
        os.replace(local_backup, os.path.join(BACKUP_DIR, filename))
    return filename


def restore_backup(device, file_path):
    if not file_path.lower().endswith(".apks"):
        return run_adb_command(["adb", "-s", device, "install", "-r", "-t", "-g", "-d", file_path])
    with tempfile.TemporaryDirectory() as staging:
        with zipfile.ZipFile(file_path) as archive:
            apk_files = []
            for index, entry in enumerate(archive.infolist()):
                if not entry.is_dir() and entry.filename.endswith(".apk"):
                    # Use our own names rather than extracting archive paths.
                    local_path = os.path.join(staging, f"{index}.apk")
                    with open(local_path, "wb") as apk_file:
                        apk_file.write(archive.read(entry))
                    apk_files.append(local_path)
        if not apk_files:
            raise ValueError("Backup contains no APK files")
        return run_adb_command(["adb", "-s", device, "install-multiple", "-r", *apk_files])

class AndroidSafeHarborApp:
    def __init__(self, root):
        self.root = root
        self.root.title("APKSafePassage - App Backup & Restore")
        # Set a large, natural window size
        self.root.geometry("900x800")
        self.devices = []
        self.apps = []
        self.check_vars = [] # To store Checkbutton variables
        self.all_selected_var = tk.BooleanVar()
        self.setup_styles()
        self.setup_ui()

    def setup_styles(self):
        self.colors = {
            "background": "#f3f6fb", "surface": "#ffffff",
            "text": "#17243b", "muted": "#63728a", "border": "#dce3ed",
            "accent": "#2563eb", "hover": "#1d4ed8",
        }
        c = self.colors
        self.root.configure(background=c["background"])
        self.root.minsize(760, 560)
        self.root.option_add("*Font", "{DejaVu Sans} 10")
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background=c["background"])
        style.configure("Card.TFrame", background=c["surface"])
        style.configure("TLabel", background=c["background"], foreground=c["text"])
        style.configure("Title.TLabel", font=("DejaVu Sans", 23, "bold"))
        style.configure("Muted.TLabel", foreground=c["muted"])
        style.configure("Card.TLabel", background=c["surface"])
        style.configure("Section.TLabel", background=c["surface"], font=("DejaVu Sans", 12, "bold"))
        style.configure("Header.TLabel", background=c["surface"], foreground=c["muted"], font=("DejaVu Sans", 9, "bold"))
        style.configure("TButton", font=("DejaVu Sans", 10, "bold"), padding=(18, 11),
                        background=c["surface"], foreground=c["text"],
                        bordercolor=c["border"], lightcolor=c["surface"],
                        darkcolor=c["surface"], relief="flat", borderwidth=1,
                        focusthickness=2, focuscolor=c["accent"])
        style.map("TButton", background=[("disabled", "#edf1f7"), ("pressed", "#dce6f5"), ("active", "#eaf0fa")],
                  foreground=[("disabled", "#8b98aa")],
                  bordercolor=[("focus", c["accent"])])
        style.configure("Primary.TButton", background=c["accent"], foreground="white",
                        bordercolor=c["accent"], lightcolor=c["accent"], darkcolor=c["accent"],
                        focuscolor="white")
        style.map("Primary.TButton", background=[("disabled", "#dce5f4"), ("pressed", "#1e40af"), ("active", c["hover"])],
                  foreground=[("disabled", "#7185a5")],
                  bordercolor=[("disabled", "#dce5f4"), ("focus", "#17243b"), ("!disabled", c["accent"])])
        style.configure("TCombobox", padding=9, fieldbackground=c["surface"],
                        background=c["surface"], foreground=c["text"],
                        bordercolor=c["border"], arrowcolor=c["muted"])
        style.map("TCombobox", fieldbackground=[("readonly", c["surface"])],
                  selectbackground=[("readonly", c["surface"])],
                  selectforeground=[("readonly", c["text"])],
                  bordercolor=[("focus", c["accent"])])
        style.configure("Vertical.TScrollbar", background="#cad4e2", troughcolor=c["surface"],
                        borderwidth=0, arrowsize=12)
        style.configure("TCheckbutton", background=c["surface"], foreground=c["text"],
                        padding=(4, 6), focuscolor=c["accent"], focusthickness=1)
        style.map("TCheckbutton", background=[("active", "#edf3ff")],
                  foreground=[("disabled", "#8b98aa")])

        # Image indicators keep checkboxes crisp and equally sized across platforms.
        self.checkbox_images = []
        for selected, color in [(False, c["border"]), (False, c["accent"]),
                                (True, c["accent"]), (True, c["hover"])]:
            icon = tk.PhotoImage(master=self.root, width=22, height=22)
            for y in range(2, 20):
                inset = 1 if y in (2, 19) else 0
                icon.put(color, to=(2 + inset, y, 20 - inset, y + 1))
            if selected:
                for x1, y1, x2, y2 in [(6, 11, 9, 14), (9, 14, 16, 7)]:
                    for step in range(21):
                        x = round(x1 + (x2 - x1) * step / 20)
                        y = round(y1 + (y2 - y1) * step / 20)
                        icon.put("white", to=(x - 1, y - 1, x + 1, y + 1))
            else:
                icon.put(c["surface"], to=(4, 4, 18, 18))
            self.checkbox_images.append(icon)
        style.element_create("SafeHarbor.Check.indicator", "image", self.checkbox_images[0],
                             ("selected", "active", self.checkbox_images[3]),
                             ("selected", self.checkbox_images[2]),
                             ("active", self.checkbox_images[1]))
        style.layout("TCheckbutton", [("Checkbutton.padding", {"sticky": "nswe", "children": [
            ("SafeHarbor.Check.indicator", {"side": "left", "sticky": ""}),
            ("Checkbutton.focus", {"side": "left", "sticky": "w", "children": [
                ("Checkbutton.label", {"sticky": "nswe"})]})]})])

    def setup_ui(self):
        c = self.colors
        heading = ttk.Frame(self.root, padding=(28, 24, 28, 18))
        heading.pack(fill=tk.X)
        ttk.Label(heading, text="Android SafeHarbor", style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(heading, text="Keep your apps safe. Restore them when you need them.",
                  style="Muted.TLabel").pack(anchor=tk.W, pady=(6, 0))

        top_frame = ttk.Frame(self.root, style="Card.TFrame", padding=18)
        top_frame.pack(fill=tk.X, padx=28, pady=(0, 18))
        ttk.Label(top_frame, text="Device", style="Section.TLabel").pack(side=tk.LEFT, padx=(0, 16))
        self.device_var = tk.StringVar()
        self.device_dropdown = ttk.Combobox(top_frame, textvariable=self.device_var, state="readonly", width=28)
        self.device_dropdown.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))
        self.refresh_devices_btn = ttk.Button(top_frame, text="Refresh devices", command=self.refresh_devices)
        self.refresh_devices_btn.pack(side=tk.RIGHT)

        mid_frame = ttk.Frame(self.root, style="Card.TFrame", padding=18)
        mid_frame.pack(fill=tk.BOTH, expand=True, padx=28)
        ttk.Label(mid_frame, text="Installed apps", style="Section.TLabel").pack(anchor=tk.W)
        ttk.Label(mid_frame, text="Select the apps you want to back up.", style="Header.TLabel").pack(anchor=tk.W, pady=(6, 16))

        header_frame = ttk.Frame(mid_frame, style="Card.TFrame")
        header_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Checkbutton(header_frame, text="Select all", variable=self.all_selected_var,
                        command=self.toggle_all).pack(side=tk.LEFT)
        ttk.Label(header_frame, text="PACKAGE", style="Header.TLabel").pack(side=tk.LEFT, padx=20)
        ttk.Label(header_frame, text="STATUS", style="Header.TLabel").pack(side=tk.RIGHT, padx=12)

        self.container = ttk.Frame(mid_frame, style="Card.TFrame")
        self.container.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(self.container, highlightthickness=0, background=c["surface"], yscrollincrement=1)
        self.scrollbar = ttk.Scrollbar(self.container, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollable_frame = ttk.Frame(self.canvas, style="Card.TFrame")
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw", tags="inner_frame")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure("inner_frame", width=e.width))
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._scroll_remainder = 0.0
        self._windowing_system = self.root.tk.call("tk", "windowingsystem")
        # Toplevel bindings also receive events from dynamically added rows.
        # Filter by pointer location so other controls keep their own scrolling.
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.root.bind(sequence, self.scroll_apps, add="+")

        bottom_frame = ttk.Frame(self.root, padding=(28, 20))
        bottom_frame.pack(fill=tk.X)
        self.backup_btn = ttk.Button(bottom_frame, text="Back up selected apps", command=self.backup_selected_apps,
                                     state=tk.DISABLED, style="Primary.TButton")
        self.backup_btn.pack(side=tk.LEFT, padx=(0, 12))
        self.restore_btn = ttk.Button(bottom_frame, text="Restore from backup", command=self.restore_selected_app, state=tk.DISABLED)
        self.restore_btn.pack(side=tk.LEFT)
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self.root, textvariable=self.status_var, style="Muted.TLabel",
                  padding=(28, 0, 28, 18), anchor=tk.W).pack(side=tk.BOTTOM, fill=tk.X)
        self.refresh_devices()

    def scroll_apps(self, event):
        widget = self.root.winfo_containing(event.x_root, event.y_root)
        while widget is not None and widget is not self.canvas:
            widget = widget.master
        if widget is None or event.state & 0x0001:
            self._scroll_remainder = 0.0
            return

        if self.canvas.yview() == (0.0, 1.0):
            self._scroll_remainder = 0.0
            return "break"

        if event.num == 4:
            pixels = -36
        elif event.num == 5:
            pixels = 36
        elif self._windowing_system == "aqua":
            pixels = -event.delta
        else:
            pixels = -event.delta * 36 / 120
        # Preserve small trackpad deltas instead of rounding each event to zero.
        self._scroll_remainder += pixels
        distance = int(self._scroll_remainder)
        self._scroll_remainder -= distance
        if distance:
            self.canvas.yview_scroll(distance, "units")
        return "break"

    def update_status(self, text):
        self.status_var.set(text)
        self.root.update_idletasks()

    def refresh_devices(self):
        self.update_status("Refreshing devices...")
        def task():
            out, err = run_adb_command("adb devices")
            lines = out.splitlines()
            self.devices = []
            # Skip the first line (usually "List of devices attached")
            for line in lines[1:]:
                if ":" in line:
                    self.devices.append(line.split(":")[0].strip())
                if "\t" in line:
                    self.devices.append(line.split("\t")[0].strip())


            if not self.devices:
                self.update_status("No devices found.")
            else:
                self.device_dropdown['values'] = self.devices
                if self.devices:
                    self.device_dropdown.current(0)
                    self.update_status(f"Found {len(self.devices)} device(s).")

            self.refresh_apps()

        threading.Thread(target=task).start()

    def refresh_apps(self):
        device = self.device_var.get()
        if not device:
            return

        self.update_status(f"Fetching apps for {device}...")

        # Clear existing checkbuttons
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.check_vars = []
        self.apps = []

        def task():
            # List only 3rd party apps (-3)
            out, err = run_adb_command(f"adb -s {device} shell pm list packages -3")
            if "fail" in out.lower() or err:
                self.update_status(f"Error: {err}")
                return

            packages = [line.strip().replace("package:", "") for line in out.splitlines() if ":" in line]

            for pkg in packages:
                path_out, path_err = run_adb_command(f"adb -s {device} shell pm path {pkg}")
                paths = parse_apk_paths(path_out)
                if paths:
                    app_info = {
                        'package': pkg,
                        'paths': paths,
                        'status': "Not Backed Up",
                        'label_widget': None
                    }
                    self.apps.append(app_info)

                    row = ttk.Frame(self.scrollable_frame, style="Card.TFrame", padding=(0, 6))
                    row.pack(fill=tk.X, expand=True)

                    var = tk.BooleanVar()
                    self.check_vars.append(var)
                    ttk.Checkbutton(row, variable=var).pack(side=tk.LEFT)
                    ttk.Label(row, text=pkg, style="Card.TLabel", anchor=tk.W).pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)

                    # Status label - we store a reference to this so we can update it later
                    status_lbl = ttk.Label(row, text=app_info['status'], style="Card.TLabel", foreground=self.colors["muted"])
                    status_lbl.pack(side=tk.RIGHT, padx=20)
                    app_info['label_widget'] = status_lbl

            self.update_status(f"Loaded {len(self.apps)} apps.")
            self.backup_btn.config(state=tk.NORMAL)
            self.restore_btn.config(state=tk.NORMAL)

        threading.Thread(target=task).start()

    def toggle_all(self):
        state = self.all_selected_var.get()
        for var in self.check_vars:
            var.set(state)

    def backup_selected_apps(self):
        device = self.device_var.get()
        selected_apps = []

        for i, var in enumerate(self.check_vars):
            if var.get():
                selected_apps.append(self.apps[i])

        if not selected_apps:
            messagebox.showwarning("Warning", "Please select at least one app to backup.")
            return

        def task():
            success_count = 0
            fail_count = 0

            for app_data in selected_apps:
                pkg_name = app_data['package']
                self.update_status(f"Backing up {pkg_name}...")
                try:
                    filename = backup_apks(device, pkg_name, app_data['paths'])
                    app_data['status'] = filename
                    if app_data['label_widget']:
                        app_data['label_widget'].config(text=filename, foreground="#15803d")
                    success_count += 1
                except Exception as exc:
                    app_data['status'] = f"Backup failed: {exc}"
                    if app_data['label_widget']:
                        app_data['label_widget'].config(text=app_data['status'], foreground="#b91c1c")
                    fail_count += 1

            self.update_status(f"Backup complete. Success: {success_count}, Failed: {fail_count}")
            messagebox.showinfo("Backup Complete", f"Successfully backed up {success_count} apps.\nFailed: {fail_count}")

        threading.Thread(target=task).start()

    def restore_selected_app(self):
        file_path = filedialog.askopenfilename(
            initialdir=BACKUP_DIR,
            title="Select App Backup to Restore",
            filetypes=(("App backups", "*.apk *.apks"), ("All files", "*.*"))
        )

        if not file_path:
            return

        device = self.device_var.get()
        self.update_status(f"Restoring {os.path.basename(file_path)}...")

        def task():
            try:
                out, err = restore_backup(device, file_path)
            except Exception as exc:
                out, err = "", str(exc)

            if "Success" in out:
                self.update_status("Restore successful!")
                messagebox.showinfo("Success", "App successfully reinstalled.")
            else:
                self.update_status(f"Restore failed: {err}")
                messagebox.showerror("Error", f"Failed to install APK: {err}")

        threading.Thread(target=task).start()

if __name__ == "__main__":
    # Ensure backup directory exists
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

    root = tk.Tk()
    app = AndroidSafeHarborApp(root)
    root.mainloop()
