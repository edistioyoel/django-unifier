import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

# === Configuración y Constantes ===
CONFIG_FILE = "config.json"
APP_TITLE = "🐍 Exportador de Código Django"

# Extensiones disponibles para filtrar
AVAILABLE_EXTENSIONS = [
    '.py', '.html', '.css', '.js', '.json', '.yaml', '.yml',
    '.md', '.txt', '.sql', '.xml', '.csv'
]

# Carpetas y patrones a excluir por defecto
DEFAULT_EXCLUDED_FOLDERS = [
    '__pycache__', '.git', 'venv', 'env', '.venv', 'node_modules',
    '.vscode', '.idea', 'static', 'staticfiles', 'media', 'logs',
    '__tests__', '.pytest_cache', 'migrations'
]

# Traducciones de la interfaz
TEXTS = {
    "title": APP_TITLE,
    "lbl_project": "Carpeta Raíz del Proyecto Django:",
    "lbl_output": "Carpeta de Salida (Archivos .txt):",
    "btn_browse": "Examinar...",
    "lbl_extensions": "Extensiones a incluir:",
    "lbl_exclude": "Carpetas a excluir (separadas por coma):",
    "btn_export": "▶ EXPORTAR PROYECTO",
    "lbl_status": "Estado:",
    "lbl_progress": "Progreso:",
    "log_title": "Registro de actividad:",
    "msg_ready": "Listo para comenzar.",
    "msg_success": "✅ Proceso completado con éxito.",
    "msg_error": "❌ Error crítico.",
    "msg_no_project": "Por favor, selecciona una carpeta de proyecto válida.",
    "msg_no_output": "Por favor, selecciona una carpeta de salida válida.",
    "msg_no_manage": "No se encontró 'manage.py'. ¿Es seguro que es un proyecto Django?",
    "msg_no_apps": "No se encontraron aplicaciones Django (carpetas con 'apps.py').",
    "searching_apps": "🔍 Buscando aplicaciones Django en: {path}...",
    "app_found": "✅ App detectada: {name}",
    "processing_app": "⚙️ Procesando app: {name}...",
    "file_saved": "💾 Archivo guardado: {filename}",
    "error_reading": "⚠️ Error leyendo {file}: {error}",
    "structure_header": "=== ESTRUCTURA DE DIRECTORIOS ===\n\n",
    "file_separator": "\n\n=== ARCHIVO: {path} ===\n\n",
    "footer_separator": "\n\n" + "=" * 50 + "\n"
}


# === Funciones de Lógica (Usando pathlib) ===

def load_config():
    """Carga la configuración desde config.json."""
    config_path = Path(CONFIG_FILE)
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error cargando config: {e}")

    return {
        "last_project_folder": "",
        "last_output_folder": "",
        "selected_extensions": ['.py', '.html', '.css', '.js', '.json'],
        "excluded_folders": DEFAULT_EXCLUDED_FOLDERS
    }


def save_config(config_data):
    """Guarda la configuración actual en config.json."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error guardando config: {e}")
        return False


def is_django_project(root_path: Path):
    """Verifica si la carpeta contiene manage.py."""
    return (root_path / "manage.py").is_file()


def find_django_apps(root_path: Path, excluded_folders: list):
    """
    Busca carpetas que sean apps de Django (contienen apps.py).
    Usa pathlib.rglob para buscar recursivamente evitando carpetas excluidas.
    """
    apps = []
    excluded_set = set(excluded_folders)

    # Iteramos sobre todos los archivos 'apps.py' encontrados
    # Nota: rglob puede ser lento en árboles enormes, pero para proyectos Django es eficiente.
    # Alternativa manual con iterdir si se necesita más control sobre exclusión de directorios.

    for apps_py_file in root_path.rglob("apps.py"):
        # Verificar si alguna parte de la ruta está en la lista de excluidos
        # apps_py_file.parts devuelve una tupla ('C:', 'Users', 'Proj', 'App', 'apps.py')
        if any(part in excluded_set for part in apps_py_file.parts):
            continue

        app_dir = apps_py_file.parent
        app_name = app_dir.name

        # Doble verificación por seguridad
        if app_name not in excluded_set:
            apps.append({
                "name": app_name,
                "path": app_dir,
                "rel_path": app_dir.relative_to(root_path)
            })

    return apps


def get_folder_structure(app_path: Path, allowed_extensions: list, excluded_folders: list):
    """Genera un string con el árbol de directorios de la app usando pathlib."""
    structure_lines = []
    excluded_set = set(excluded_folders)

    # Función auxiliar recursiva para construir el árbol respetando exclusiones
    def scan_dir(current_path: Path, level: int):
        try:
            # Obtener entradas ordenadas
            entries = sorted(current_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return

        dirs_to_scan = []

        for entry in entries:
            if entry.name in excluded_set:
                continue

            indent = "  " * level

            if entry.is_dir():
                structure_lines.append(f"{indent}[📁 {entry.name}/]")
                dirs_to_scan.append(entry)
            elif entry.is_file():
                if any(entry.name.endswith(ext) for ext in allowed_extensions):
                    structure_lines.append(f"{indent}  📄 {entry.name}")

        # Recursión
        for d in dirs_to_scan:
            scan_dir(d, level + 1)

    scan_dir(app_path, 0)
    return "\n".join(structure_lines)


def read_file_content(filepath: Path):
    """Intenta leer un archivo con diferentes codificaciones."""
    encodings = ['utf-8', 'latin-1', 'cp1252']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
        except Exception:
            return None
    return None


def export_app_to_file(app_info: dict, output_folder: Path, allowed_extensions: list, excluded_folders: list,
                       log_callback):
    """
    Escribe el contenido de una app en un archivo txt único.
    """
    app_name = app_info["name"]
    app_path: Path = app_info["path"]
    output_filename = f"{app_name}.txt"
    output_filepath = output_folder / output_filename

    try:
        with open(output_filepath, 'w', encoding='utf-8') as out_f:
            # 1. Escribir estructura de carpetas
            out_f.write(TEXTS["structure_header"])
            structure = get_folder_structure(app_path, allowed_extensions, excluded_folders)
            out_f.write(structure)
            out_f.write(TEXTS["footer_separator"])

            # 2. Escribir contenido de archivos
            count = 0
            excluded_set = set(excluded_folders)

            # Recorrido manual para tener control total sobre exclusión de carpetas
            # pathlib.rglob no permite excluir dinámicamente subdirectorios fácilmente sin filtrar después
            for item in app_path.rglob('*'):
                if not item.is_file():
                    continue

                # Verificar si alguna parte del path relativo está excluida
                try:
                    rel_item = item.relative_to(app_path)
                    if any(part in excluded_set for part in rel_item.parts):
                        continue
                except ValueError:
                    continue

                # Verificar extensión
                if not any(item.name.endswith(ext) for ext in allowed_extensions):
                    continue

                content = read_file_content(item)
                if content is not None:
                    # Usar relative_to para la ruta relativa limpia
                    rel_path_str = str(item.relative_to(app_path))

                    out_f.write(TEXTS["file_separator"].format(path=rel_path_str))
                    out_f.write(content)
                    out_f.write("\n")
                    count += 1
                else:
                    log_callback(TEXTS["error_reading"].format(file=item.name, error="Codificación no soportada"),
                                 "warning")

            log_callback(TEXTS["file_saved"].format(filename=output_filename), "success")
            return True, f"App '{app_name}' exportada ({count} archivos)."

    except Exception as e:
        return False, str(e)


# === Clase de la Aplicación GUI ===

class DjangoExporterApp:
    def __init__(self, root):
        self.root = root
        self.root.title(TEXTS["title"])
        self.root.geometry("900x750")
        self.root.minsize(800, 600)

        # Cargar configuración
        self.config = load_config()

        # Variables de control
        self.project_path_var = tk.StringVar(value=self.config.get("last_project_folder", ""))
        self.output_path_var = tk.StringVar(value=self.config.get("last_output_folder", ""))

        # Variables de extensiones
        self.ext_vars = {}
        for ext in AVAILABLE_EXTENSIONS:
            is_selected = ext in self.config.get("selected_extensions", [])
            self.ext_vars[ext] = tk.BooleanVar(value=is_selected)

        # Variable de carpetas excluidas
        self.exclude_var = tk.StringVar(value=", ".join(self.config.get("excluded_folders", DEFAULT_EXCLUDED_FOLDERS)))

        self.create_widgets()
        self.log(TEXTS["msg_ready"], "info")

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Sección 1: Rutas ---
        routes_frame = ttk.LabelFrame(main_frame, text="📂 Ubicación de Archivos", padding="10")
        routes_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(routes_frame, text=TEXTS["lbl_project"]).grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(routes_frame, textvariable=self.project_path_var, width=60).grid(row=0, column=1, padx=5, sticky="ew")
        ttk.Button(routes_frame, text=TEXTS["btn_browse"], command=self.browse_project).grid(row=0, column=2, padx=5)

        ttk.Label(routes_frame, text=TEXTS["lbl_output"]).grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(routes_frame, textvariable=self.output_path_var, width=60).grid(row=1, column=1, padx=5, sticky="ew")
        ttk.Button(routes_frame, text=TEXTS["btn_browse"], command=self.browse_output).grid(row=1, column=2, padx=5)

        routes_frame.columnconfigure(1, weight=1)

        # --- Sección 2: Configuración ---
        config_frame = ttk.LabelFrame(main_frame, text="⚙️ Configuración de Filtrado", padding="10")
        config_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(config_frame, text=TEXTS["lbl_extensions"], font=("Arial", 10, "bold")).grid(row=0, column=0,
                                                                                               sticky="w", pady=5)

        ext_container = ttk.Frame(config_frame)
        ext_container.grid(row=1, column=0, columnspan=2, sticky="w")

        cols = 5
        for i, ext in enumerate(AVAILABLE_EXTENSIONS):
            chk = ttk.Checkbutton(ext_container, text=ext, variable=self.ext_vars[ext])
            chk.grid(row=i // cols, column=i % cols, sticky="w", padx=10, pady=2)

        ttk.Label(config_frame, text=TEXTS["lbl_exclude"], font=("Arial", 10, "bold")).grid(row=0, column=2, sticky="w",
                                                                                            pady=5, padx=(20, 0))
        ttk.Entry(config_frame, textvariable=self.exclude_var, width=40).grid(row=1, column=2, sticky="ew",
                                                                              padx=(20, 0))
        config_frame.columnconfigure(2, weight=1)

        # --- Sección 3: Acción y Progreso ---
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=10)

        self.btn_export = ttk.Button(action_frame, text=TEXTS["btn_export"], command=self.start_export)
        self.btn_export.pack(side=tk.RIGHT, padx=5)

        self.progress_bar = ttk.Progressbar(action_frame, mode='determinate', length=300)
        self.progress_bar.pack(side=tk.RIGHT, padx=10)

        self.status_label = ttk.Label(action_frame, text=TEXTS["lbl_status"] + " " + TEXTS["msg_ready"],
                                      foreground="gray")
        self.status_label.pack(side=tk.LEFT)

        # --- Sección 4: Log ---
        log_frame = ttk.LabelFrame(main_frame, text=TEXTS["log_title"], padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = ScrolledText(log_frame, height=15, font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.log_text.tag_config("info", foreground="black")
        self.log_text.tag_config("success", foreground="green")
        self.log_text.tag_config("warning", foreground="orange")
        self.log_text.tag_config("error", foreground="red")

    def browse_project(self):
        folder = filedialog.askdirectory(title="Seleccionar Proyecto Django", initialdir=self.project_path_var.get())
        if folder:
            self.project_path_var.set(folder)
            if not is_django_project(Path(folder)):
                self.log(TEXTS["msg_no_manage"], "warning")

    def browse_output(self):
        folder = filedialog.askdirectory(title="Seleccionar Carpeta de Salida", initialdir=self.output_path_var.get())
        if folder:
            self.output_path_var.set(folder)

    def log(self, message, level="info"):
        self.log_text.insert(tk.END, message + "\n", level)
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def update_status(self, msg):
        self.status_label.config(text=TEXTS["lbl_status"] + " " + msg)

    def start_export(self):
        project_root_str = self.project_path_var.get().strip()
        output_root_str = self.output_path_var.get().strip()

        if not project_root_str:
            messagebox.showerror("Error", TEXTS["msg_no_project"])
            return
        project_root = Path(project_root_str)
        if not project_root.is_dir():
            messagebox.showerror("Error", TEXTS["msg_no_project"])
            return

        if not output_root_str:
            messagebox.showerror("Error", TEXTS["msg_no_output"])
            return
        output_root = Path(output_root_str)
        if not output_root.is_dir():
            messagebox.showerror("Error", TEXTS["msg_no_output"])
            return

        if not is_django_project(project_root):
            if not messagebox.askyesno("Advertencia", TEXTS["msg_no_manage"] + "\n\n¿Continuar de todas formas?"):
                return

        selected_exts = [ext for ext, var in self.ext_vars.items() if var.get()]
        if not selected_exts:
            messagebox.showwarning("Advertencia", "Debes seleccionar al menos una extensión de archivo.")
            return

        excluded_folders = [x.strip() for x in self.exclude_var.get().split(",") if x.strip()]

        current_config = {
            "last_project_folder": str(project_root),
            "last_output_folder": str(output_root),
            "selected_extensions": selected_exts,
            "excluded_folders": excluded_folders
        }
        save_config(current_config)

        self.log("-" * 40)
        self.log(TEXTS["searching_apps"].format(path=project_root), "info")

        apps = find_django_apps(project_root, excluded_folders)

        if not apps:
            self.log(TEXTS["msg_no_apps"], "error")
            messagebox.showinfo("Info", TEXTS["msg_no_apps"])
            return

        self.log(f"🎯 {len(apps)} aplicaciones encontradas.", "success")

        total_apps = len(apps)
        self.progress_bar['maximum'] = total_apps
        self.progress_bar['value'] = 0
        self.btn_export.config(state=tk.DISABLED)

        success_count = 0
        error_count = 0

        for i, app_info in enumerate(apps):
            self.update_status(f"Procesando {i + 1}/{total_apps}: {app_info['name']}")
            self.log(TEXTS["processing_app"].format(name=app_info['name']), "info")

            success, msg = export_app_to_file(
                app_info,
                output_root,
                selected_exts,
                excluded_folders,
                lambda m, l="info": self.log(m, l)
            )

            if success:
                success_count += 1
                self.log(msg, "success")
            else:
                error_count += 1
                self.log(f"❌ Error en {app_info['name']}: {msg}", "error")

            self.progress_bar['value'] = i + 1
            self.root.update_idletasks()

        self.btn_export.config(state=tk.NORMAL)
        final_status = TEXTS["msg_success"] if error_count == 0 else f"{success_count} éxitos, {error_count} errores"
        self.update_status(final_status)

        final_msg = f"✅ Proceso finalizado.\n\nApps exportadas: {success_count}\nErrores: {error_count}\n\nArchivos guardados en:\n{output_root}"
        self.log(final_msg, "success")
        messagebox.showinfo("Completado", final_msg)


if __name__ == "__main__":
    root = tk.Tk()
    try:
        style = ttk.Style()
        style.theme_use('clam')
    except:
        pass

    app = DjangoExporterApp(root)
    root.mainloop()
