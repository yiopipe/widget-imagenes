import os
import json
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
from PIL import Image, ImageOps, ImageTk

# ---------- CONFIGURACIÓN BÁSICA ----------
ANCHO = 400
ALTO = 300
POS_X = 100
POS_Y = 100
# ------------------------------------------

CARPETA = os.path.dirname(os.path.abspath(__file__))
CARPETA_IMG = os.path.join(CARPETA, "imagenes")
ARCHIVO_CONFIG = os.path.join(CARPETA, "config.json")

CONFIG_INICIAL = {
    "intervalo": 15,  # segundos entre imágenes de una misma franja
    "franjas": [
        {"nombre": "Madrugada", "inicio": 1, "fin": 7, "imagenes": ["madrugada.jpg"]},
        {"nombre": "Mañana", "inicio": 7, "fin": 12, "imagenes": ["manana.jpg"]},
        {"nombre": "Tarde", "inicio": 12, "fin": 20, "imagenes": ["tarde.jpg"]},
        {"nombre": "Noche", "inicio": 20, "fin": 1, "imagenes": ["noche.jpg"]},
    ],
}

os.makedirs(CARPETA_IMG, exist_ok=True)


# ---------- Guardar y leer configuración ----------
def guardar_config():
    with open(ARCHIVO_CONFIG, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def leer_config():
    try:
        with open(ARCHIVO_CONFIG, "r", encoding="utf-8") as f:
            datos = json.load(f)
        if "franjas" in datos and "intervalo" in datos:
            return datos
    except (OSError, ValueError):
        pass
    return json.loads(json.dumps(CONFIG_INICIAL))  # copia del valor inicial


config = leer_config()
guardar_config()

ancho = int(config.get("ancho", ANCHO))
alto = int(config.get("alto", ALTO))
MIN_ANCHO, MIN_ALTO = 160, 120
MARGEN = 8  # grosor (en píxeles) de la zona de borde que permite redimensionar


# ---------- Lógica de imágenes ----------
def indice_franja_actual():
    """Devuelve la posición de la franja que corresponde a la hora actual."""
    hora = datetime.now().hour
    for i, franja in enumerate(config["franjas"]):
        inicio, fin = franja["inicio"], franja["fin"]
        if inicio < fin:
            if inicio <= hora < fin:
                return i
        else:  # cruza la medianoche, por ejemplo 20 a 1
            if hora >= inicio or hora < fin:
                return i
    return len(config["franjas"]) - 1


def imagenes_validas(franja):
    """Lista de rutas de la franja que realmente existen en disco."""
    rutas = []
    for nombre in franja["imagenes"]:
        ruta = os.path.join(CARPETA_IMG, nombre)
        if os.path.isfile(ruta):
            rutas.append(ruta)
    return rutas


def abrir_original(ruta):
    """Abre la imagen original (limitada a 1920 px para ir rápido)."""
    try:
        if ruta is None:
            raise ValueError("sin imagen")
        imagen = Image.open(ruta).convert("RGB")
        imagen.thumbnail((1920, 1920))
        return imagen
    except Exception:
        return Image.new("RGB", (800, 600), (60, 60, 60))


def ajustar(original):
    """Recorta y escala la imagen al tamaño actual del widget, sin deformarla."""
    return ImageOps.fit(original, (ancho, alto), method=Image.BILINEAR)


def copiar_a_carpeta(origen):
    """Copia una imagen a la carpeta 'imagenes' y devuelve su nombre."""
    nombre = os.path.basename(origen)
    destino = os.path.join(CARPETA_IMG, nombre)
    if os.path.abspath(origen) == os.path.abspath(destino):
        return nombre
    base, ext = os.path.splitext(nombre)
    n = 1
    while os.path.exists(destino):
        destino = os.path.join(CARPETA_IMG, f"{base}_{n}{ext}")
        n += 1
    shutil.copy2(origen, destino)
    return os.path.basename(destino)


# ---------- Ventana principal ----------
ventana = tk.Tk()
ventana.title("Widget de imágenes")
ventana.overrideredirect(True)
ventana.attributes("-topmost", True)
ventana.geometry(f"{ancho}x{alto}+{POS_X}+{POS_Y}")

etiqueta = tk.Label(ventana, bd=0, bg="#222222")
etiqueta.place(x=0, y=0, relwidth=1, relheight=1)

# Vista pequeña que se muestra al minimizar
vista_mini = tk.Label(
    ventana, text="▣", bg="#222222", fg="white",
    font=("Sans", 16, "bold"), cursor="hand2",
)

# Variables de estado
foto = None
imagen_actual = None
original_actual = None
ruta_actual = None
id_transicion = 0
id_tick = None
franja_previa = None
indice = 0
minimizado = False
ventana_config = None
refresco_pendiente = False


# ---------- Transición suave ----------
def transicion(nueva, paso=0, id_t=None):
    global foto, imagen_actual, id_transicion
    if id_t is None:
        id_transicion += 1
        id_t = id_transicion
        if imagen_actual is None:  # primera imagen: sin transición
            imagen_actual = nueva
            foto = ImageTk.PhotoImage(nueva)
            etiqueta.config(image=foto)
            return
    if id_t != id_transicion:  # llegó otra transición más nueva
        return
    pasos_totales = 20
    if paso <= pasos_totales:
        mezcla = Image.blend(imagen_actual, nueva, paso / pasos_totales)
        foto = ImageTk.PhotoImage(mezcla)
        etiqueta.config(image=foto)
        ventana.after(50, transicion, nueva, paso + 1, id_t)
    else:
        imagen_actual = nueva


def mostrar(ruta):
    global ruta_actual, original_actual
    if ruta == ruta_actual and imagen_actual is not None:
        return
    ruta_actual = ruta
    original_actual = abrir_original(ruta)
    transicion(ajustar(original_actual))


def refrescar_imagen():
    """Vuelve a ajustar la imagen actual al tamaño nuevo de la ventana."""
    global refresco_pendiente, imagen_actual, foto, id_transicion
    refresco_pendiente = False
    if original_actual is None:
        return
    id_transicion += 1  # cancela cualquier transición en curso
    imagen_actual = ajustar(original_actual)
    foto = ImageTk.PhotoImage(imagen_actual)
    etiqueta.config(image=foto)


def pedir_refresco():
    """Pide redibujar la imagen, como máximo unas 25 veces por segundo."""
    global refresco_pendiente
    if not refresco_pendiente:
        refresco_pendiente = True
        ventana.after(40, refrescar_imagen)


def aplicar_tamano(x, y, w, h):
    global ancho, alto
    ancho, alto = int(w), int(h)
    ventana.geometry(f"{ancho}x{alto}+{int(x)}+{int(y)}")
    pedir_refresco()


# ---------- Ciclo principal: elegir qué imagen toca ----------
def tick():
    global id_tick, indice, franja_previa
    i = indice_franja_actual()
    rutas = imagenes_validas(config["franjas"][i])
    if i != franja_previa:
        indice = 0
        franja_previa = i
    else:
        indice += 1
    mostrar(rutas[indice % len(rutas)] if rutas else None)
    id_tick = ventana.after(int(config["intervalo"]) * 1000, tick)


def aplicar_cambios():
    """Reinicia el ciclo para que los cambios se vean de inmediato."""
    global franja_previa, ruta_actual
    if id_tick is not None:
        ventana.after_cancel(id_tick)
    franja_previa = None
    ruta_actual = None
    tick()


# ---------- Minimizar y restaurar ----------
def minimizar():
    global minimizado
    x, y = ventana.winfo_x(), ventana.winfo_y()
    etiqueta.place_forget()
    vista_mini.place(x=0, y=0, relwidth=1, relheight=1)
    ventana.geometry(f"44x44+{x}+{y}")
    minimizado = True


def restaurar():
    global minimizado
    x, y = ventana.winfo_x(), ventana.winfo_y()
    vista_mini.place_forget()
    etiqueta.place(x=0, y=0, relwidth=1, relheight=1)
    ventana.geometry(f"{ancho}x{alto}+{x}+{y}")
    minimizado = False


# ---------- Mover y cambiar de tamaño ----------
CURSORES = {
    "": "",
    "n": "top_side", "s": "bottom_side", "w": "left_side", "e": "right_side",
    "nw": "top_left_corner", "ne": "top_right_corner",
    "sw": "bottom_left_corner", "se": "bottom_right_corner",
}

estado = {"zona": "", "px": 0, "py": 0, "x": 0, "y": 0,
          "w": 0, "h": 0, "ox": 0, "oy": 0, "movido": False}


def zona(evento):
    """Dice si el ratón está en un borde o esquina (n, s, e, w, nw, ne, sw, se)."""
    if minimizado:
        return ""
    z = ""
    if evento.y < MARGEN:
        z += "n"
    elif evento.y > ventana.winfo_height() - MARGEN:
        z += "s"
    if evento.x < MARGEN:
        z += "w"
    elif evento.x > ventana.winfo_width() - MARGEN:
        z += "e"
    return z


def mover_cursor(evento):
    etiqueta.config(cursor=CURSORES[zona(evento)])


def al_presionar(evento):
    estado.update(
        zona=zona(evento), px=evento.x_root, py=evento.y_root,
        x=ventana.winfo_x(), y=ventana.winfo_y(),
        w=ventana.winfo_width(), h=ventana.winfo_height(),
        ox=evento.x, oy=evento.y, movido=False,
    )


def al_arrastrar(evento):
    estado["movido"] = True
    z = estado["zona"]

    if z == "":  # no es borde: mover la ventana completa
        x = evento.x_root - estado["ox"]
        y = evento.y_root - estado["oy"]
        ventana.geometry(f"+{x}+{y}")
        return

    dx = evento.x_root - estado["px"]
    dy = evento.y_root - estado["py"]
    w, h = estado["w"], estado["h"]
    if "e" in z:
        w += dx
    if "w" in z:
        w -= dx
    if "s" in z:
        h += dy
    if "n" in z:
        h -= dy
    w = max(MIN_ANCHO, w)
    h = max(MIN_ALTO, h)

    # Con Shift presionado en una esquina se conserva la proporción
    if len(z) == 2 and evento.state & 0x1:
        proporcion = estado["w"] / estado["h"]
        h = max(MIN_ALTO, int(w / proporcion))
        w = max(MIN_ANCHO, int(h * proporcion))

    x, y = estado["x"], estado["y"]
    if "w" in z:
        x += estado["w"] - w  # el borde derecho se queda quieto
    if "n" in z:
        y += estado["h"] - h  # el borde inferior se queda quieto
    aplicar_tamano(x, y, w, h)


def al_soltar(evento):
    if minimizado:
        if not estado["movido"]:  # un clic sin arrastrar restaura
            restaurar()
        return
    if estado["zona"] != "" and estado["movido"]:
        config["ancho"], config["alto"] = ancho, alto
        guardar_config()


for componente in (etiqueta, vista_mini):
    componente.bind("<Button-1>", al_presionar)
    componente.bind("<B1-Motion>", al_arrastrar)
    componente.bind("<ButtonRelease-1>", al_soltar)
etiqueta.bind("<Motion>", mover_cursor)


# ---------- Botones sobre la imagen ----------
def crear_boton(texto, comando, desplazamiento):
    boton = tk.Label(
        etiqueta, text=texto, bg="#222222", fg="white",
        font=("Sans", 10, "bold"), width=2, cursor="hand2",
    )
    boton.place(relx=1.0, x=desplazamiento, y=4, anchor="ne")
    boton.bind("<Button-1>", lambda e: comando())
    return boton


# ---------- Ventana de configuración de imágenes ----------
def abrir_config():
    global ventana_config
    if ventana_config is not None and ventana_config.winfo_exists():
        ventana_config.lift()
        return

    win = tk.Toplevel(ventana)
    ventana_config = win
    win.title("Configurar imágenes")
    win.geometry("470x430")
    win.attributes("-topmost", True)

    nombres = [
        f"{f['nombre']} ({f['inicio']}:00 a {f['fin']}:00)"
        for f in config["franjas"]
    ]

    ttk.Label(win, text="Horario:").pack(anchor="w", padx=12, pady=(12, 2))
    combo = ttk.Combobox(win, values=nombres, state="readonly")
    combo.current(indice_franja_actual())
    combo.pack(fill="x", padx=12)

    ttk.Label(win, text="Imágenes de este horario:").pack(anchor="w", padx=12, pady=(12, 2))
    marco_lista = ttk.Frame(win)
    marco_lista.pack(fill="both", expand=True, padx=12)
    lista = tk.Listbox(marco_lista, height=8, exportselection=False)
    barra = ttk.Scrollbar(marco_lista, orient="vertical", command=lista.yview)
    lista.config(yscrollcommand=barra.set)
    lista.pack(side="left", fill="both", expand=True)
    barra.pack(side="right", fill="y")

    def franja_elegida():
        return config["franjas"][combo.current()]

    def refrescar_lista():
        lista.delete(0, "end")
        for nombre in franja_elegida()["imagenes"]:
            existe = os.path.isfile(os.path.join(CARPETA_IMG, nombre))
            lista.insert("end", nombre if existe else f"{nombre}  (no encontrada)")

    def guardar_y_aplicar():
        guardar_config()
        refrescar_lista()
        aplicar_cambios()

    tipos = [("Imágenes", "*.jpg *.jpeg *.png *.webp *.bmp *.gif"), ("Todos", "*.*")]

    def agregar():
        archivos = filedialog.askopenfilenames(parent=win, title="Elige imágenes", filetypes=tipos)
        for origen in archivos:
            franja_elegida()["imagenes"].append(copiar_a_carpeta(origen))
        if archivos:
            guardar_y_aplicar()

    def reemplazar():
        seleccion = lista.curselection()
        if not seleccion:
            messagebox.showinfo("Reemplazar", "Primero elige una imagen de la lista.", parent=win)
            return
        origen = filedialog.askopenfilename(parent=win, title="Elige la nueva imagen", filetypes=tipos)
        if origen:
            franja_elegida()["imagenes"][seleccion[0]] = copiar_a_carpeta(origen)
            guardar_y_aplicar()

    def quitar():
        seleccion = lista.curselection()
        if not seleccion:
            messagebox.showinfo("Quitar", "Primero elige una imagen de la lista.", parent=win)
            return
        del franja_elegida()["imagenes"][seleccion[0]]
        guardar_y_aplicar()

    botones = ttk.Frame(win)
    botones.pack(fill="x", padx=12, pady=10)
    ttk.Button(botones, text="Agregar…", command=agregar).pack(side="left", padx=(0, 6))
    ttk.Button(botones, text="Reemplazar…", command=reemplazar).pack(side="left", padx=6)
    ttk.Button(botones, text="Quitar", command=quitar).pack(side="left", padx=6)

    # Intervalo entre imágenes
    marco_int = ttk.Frame(win)
    marco_int.pack(fill="x", padx=12, pady=(0, 10))
    ttk.Label(marco_int, text="Cambiar de imagen cada").pack(side="left")
    var_int = tk.StringVar(value=str(config["intervalo"]))
    spin = ttk.Spinbox(marco_int, from_=5, to=3600, width=6, textvariable=var_int)
    spin.pack(side="left", padx=6)
    ttk.Label(marco_int, text="segundos").pack(side="left")

    def guardar_intervalo(evento=None):
        try:
            valor = max(5, int(var_int.get()))
        except ValueError:
            return
        config["intervalo"] = valor
        guardar_config()
        aplicar_cambios()

    ttk.Button(marco_int, text="Aplicar", command=guardar_intervalo).pack(side="left", padx=10)

    ttk.Button(win, text="Cerrar", command=win.destroy).pack(pady=(0, 12))

    combo.bind("<<ComboboxSelected>>", lambda e: refrescar_lista())
    refrescar_lista()


crear_boton("✕", ventana.destroy, -4)   # cerrar / eliminar widget
crear_boton("–", minimizar, -34)         # minimizar
crear_boton("⚙", abrir_config, -64)      # configurar imágenes

# ---------- Arrancar ----------
tick()
ventana.mainloop()