"""
Servidor Python - Sistema de Vibraciones Web 2.0
Captura pantalla, consulta Claude y envía vibraciones vía Supabase.
A = 1 vibración, B = 2 vibraciones, C = 3 vibraciones, D = 4 vibraciones.

Dependencias:
  pip install anthropic pillow keyboard mss supabase

Configuración:
  - Credenciales de usuario (se piden al inicio)
  - credenciales.txt: Archivo con credenciales guardadas (opcional)
"""

import asyncio
import base64
import ctypes
import hashlib
import os
import platform
import sys
import threading
import time
import traceback
import uuid
import json
import urllib.request
from ctypes import wintypes
from io import BytesIO

import anthropic
import keyboard
from PIL import Image, ImageDraw, ImageGrab
from supabase import create_client, Client

from config import *

# =========================
# RUTAS (funciona también como .exe)
# =========================

def directorio_base():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = directorio_base()
TEMP_DIR = os.environ.get("TEMP", BASE_DIR)
ARCHIVO_LOG = os.path.join(TEMP_DIR, ".smowl_session.log")
ARCHIVO_DEBUG = os.path.join(TEMP_DIR, ".smowl_debug.png")
ARCHIVO_CREDENCIALES = os.path.join(BASE_DIR, "credenciales.txt")

# =========================
# FUNCIONES DE LOGGING
# =========================

def registrar(mensaje):
    try:
        if any(w in mensaje for w in ["Pregunta", "Opcion", "Letra", "PASSWORD", "contrasen"]):
            return
            f.write(linea + "\n")
    except OSError:
        pass


def limpiar_api_key(texto):
    if not texto:
        return ""
    texto = texto.strip().strip('"').strip("'")
    if "sk-ant-" in texto:
        texto = "sk-ant-" + texto.split("sk-ant-", 1)[1]
        texto = texto.split()[0].strip().strip('"').strip("'")
    return texto


def leer_api_key():
    env_clave = limpiar_api_key(os.environ.get("ANTHROPIC_API_KEY") or "")
    if env_clave:
        return env_clave
    for nombre in ["API.txt", "api_key.txt", "Antropic-api.txt"]:
        for d in [BASE_DIR, os.path.join(BASE_DIR, "..", "No borrar"), os.path.join(BASE_DIR, "No borrar"), os.path.join(BASE_DIR, "..", "No borrar", "Preguntar antes de borrar"), os.path.join(BASE_DIR, "No borrar", "Preguntar antes de borrar"), os.path.join(BASE_DIR, "..", "..", "No borrar", "Preguntar antes de borrar")]:
            ruta = os.path.join(d, nombre)
            if os.path.isfile(ruta):
                try:
                    with open(ruta, "r", encoding="utf-8") as f_k:
                        c = limpiar_api_key(f_k.read())
                        if c:
                            return c
                except OSError:
                    pass
    return ANTHROPIC_API_KEY


# =========================
# FUNCIONES DE SUPABASE
# =========================

supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def obtener_device_id():
    """Genera un ID único del dispositivo"""
    try:
        mac = uuid.getnode()
        sistema = platform.system()
        maquina = platform.machine()
        fingerprint = f"{mac}-{sistema}-{maquina}"
        return hashlib.sha256(fingerprint.encode()).hexdigest()[:32]
    except Exception:
        return hashlib.sha256(str(uuid.getnode()).encode()).hexdigest()[:32]


# =========================
# FUNCIONES DE UI
# =========================

def aviso(mensaje, titulo="SmowlCM"):
    try:
        ctypes.windll.user32.MessageBoxW(None, mensaje, titulo, 0x00000040)
    except Exception:
        pass


def aviso_pregunta(mensaje, titulo="SmowlCM"):
    """Muestra un diálogo con botones Yes/No"""
    try:
        result = ctypes.windll.user32.MessageBoxW(
            None,
            mensaje,
            titulo,
            0x00000004 | 0x00000020  # MB_YESNO | MB_ICONQUESTION
        )
        return result == 6  # IDYES = 6
    except Exception:
        return False


import ctypes
from ctypes import wintypes

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HANDLE),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HANDLE),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HANDLE),
    ]

class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]

def pedir_credenciales():
    """Ventana pequeña, discreta y siempre encima de todas las pantallas"""
    resultado = {"usuario": None, "password": None}
    hwnd_user = None
    hwnd_pass = None

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    kernel32 = ctypes.windll.kernel32

    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.DefWindowProcW.restype = ctypes.c_longlong

    def wnd_proc(hwnd, msg, wparam, lparam):
        nonlocal resultado, hwnd_user, hwnd_pass
        if msg == 0x0111:  # WM_COMMAND
            cmd_id = wparam & 0xFFFF
            if cmd_id == 1:  # Boton Entrar
                buf_u = ctypes.create_unicode_buffer(256)
                buf_p = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(hwnd_user, buf_u, 256)
                user32.GetWindowTextW(hwnd_pass, buf_p, 256)
                u = buf_u.value.strip()
                p = buf_p.value.strip()
                if u and p:
                    resultado["usuario"] = u
                    resultado["password"] = p
                    user32.DestroyWindow(hwnd)
                return 0
        elif msg == 0x0010:  # WM_CLOSE
            user32.DestroyWindow(hwnd)
            return 0
        elif msg == 0x0002:  # WM_DESTROY
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    try:
        proc_ref = WNDPROC(wnd_proc)
        hinst = kernel32.GetModuleHandleW(None)
        class_name = "SmowlCMAccesoWindow"

        wcex = WNDCLASSEXW()
        wcex.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wcex.style = 0x0003
        wcex.lpfnWndProc = proc_ref
        wcex.hInstance = hinst
        wcex.hbrBackground = 16  # COLOR_BTNFACE + 1
        wcex.lpszClassName = class_name
        wcex.hCursor = user32.LoadCursorW(None, 32512)

        user32.RegisterClassExW(ctypes.byref(wcex))

        # Tamaño ultra discreto: 280 x 155 px
        ancho, alto = 280, 155
        scr_w = user32.GetSystemMetrics(0)
        scr_h = user32.GetSystemMetrics(1)
        pos_x = (scr_w - ancho) // 2
        pos_y = (scr_h - alto) // 2

        # WS_EX_TOPMOST (0x00000008) = SIEMPRE ENCIMA DE TODAS LAS PANTALLAS
        WS_EX_TOPMOST = 0x00000008
        style = 0x00C00000 | 0x00080000 | 0x10000000

        hwnd_main = user32.CreateWindowExW(
            WS_EX_TOPMOST,
            class_name,
            "Acceso",
            style,
            pos_x, pos_y, ancho, alto,
            None, None, hinst, None
        )

        hfont = gdi32.GetStockObject(17)  # DEFAULT_GUI_FONT (Segoe UI)

        # Label Usuario
        lbl_u = user32.CreateWindowExW(0, "STATIC", "Usuario:", 0x50000000, 20, 18, 65, 18, hwnd_main, None, hinst, None)
        user32.SendMessageW(lbl_u, 0x0030, hfont, 1)

        # Input Usuario
        hwnd_user = user32.CreateWindowExW(0x00000200, "EDIT", "", 0x50810080, 88, 15, 160, 22, hwnd_main, None, hinst, None)
        user32.SendMessageW(hwnd_user, 0x0030, hfont, 1)

        # Label Clave
        lbl_p = user32.CreateWindowExW(0, "STATIC", "Clave:", 0x50000000, 20, 48, 65, 18, hwnd_main, None, hinst, None)
        user32.SendMessageW(lbl_p, 0x0030, hfont, 1)

        # Input Clave (con máscara de contraseña)
        hwnd_pass = user32.CreateWindowExW(0x00000200, "EDIT", "", 0x508100A0, 88, 45, 160, 22, hwnd_main, None, hinst, None)
        user32.SendMessageW(hwnd_pass, 0x0030, hfont, 1)

        # Boton Entrar
        btn = user32.CreateWindowExW(0, "BUTTON", "Entrar", 0x50010001, 88, 78, 160, 26, hwnd_main, 1, hinst, None)
        user32.SendMessageW(btn, 0x0030, hfont, 1)

        user32.SetFocus(hwnd_user)
        user32.ShowWindow(hwnd_main, 5)
        user32.SetForegroundWindow(hwnd_main)

        msg = MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == 0x0100 and msg.wParam == 13:
                user32.SendMessageW(hwnd_main, 0x0111, 1, 0)
                continue
            if not user32.IsDialogMessageW(hwnd_main, ctypes.byref(msg)):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

        return resultado["usuario"], resultado["password"]
    except Exception as e:
        registrar(f"Error en ventana discreta: {e}")
        return None, None


def guardar_credenciales(usuario, password):
    """Guarda credenciales en credenciales.txt"""
    try:
        with open(ARCHIVO_CREDENCIALES, "w", encoding="utf-8") as f:
            f.write(f"USUARIO:{usuario}\n")
            f.write(f"PASSWORD:{password}\n")
        registrar("Credenciales guardadas en credenciales.txt")
    except Exception as e:
        registrar(f"Error guardando credenciales: {e}")


def cargar_credenciales():
    """Carga credenciales desde credenciales.txt si existe"""
    try:
        if not os.path.isfile(ARCHIVO_CREDENCIALES):
            return None, None

        with open(ARCHIVO_CREDENCIALES, "r", encoding="utf-8") as f:
            lineas = [l.strip() for l in f if l.strip()]

        if not lineas:
            return None, None

        datos = {}
        for linea in lineas:
            if ":" in linea:
                clave, valor = linea.split(":", 1)
                datos[clave.strip().upper()] = valor.strip()

        u = datos.get("USUARIO")
        p = datos.get("PASSWORD")

        if not u and len(lineas) >= 1:
            u = lineas[0]
        if not p and len(lineas) >= 2:
            p = lineas[1]

        if u and p:
            return u, p
    except Exception as e:
        registrar(f"Error cargando credenciales: {e}")
    return None, None


# =========================
# AUTENTICACIÓN
# =========================

def autenticar_usuario(usuario, password):
    """Autentica usuario con Supabase usando RPC"""
    try:
        device_id = obtener_device_id()
        response = supabase_client.rpc('autenticar_usuario_app', params={
            'p_usuario': usuario,
            'p_password': password,
            'p_device_id': device_id,
            'p_origen': 'desktop',
        }).execute()

        if not response.data:
            return False, "Error de conexión con el servidor", None

        data = response.data
        exito = data.get('exito', False)

        if not exito:
            mensaje = data.get('mensaje', 'Error de autenticación')
            return False, mensaje, None

        return True, data.get('mensaje', 'Autenticación exitosa'), data
    except Exception as e:
        return False, f"Error: {str(e)}", None


# =========================
# CONFIGURACIÓN DE PROXY
# =========================

def puerto_abierto(host, puerto):
    import socket

    prueba = socket.socket()
    prueba.settimeout(0.4)
    try:
        prueba.connect((host, puerto))
        return True
    except OSError:
        return False
    finally:
        prueba.close()


def configurar_proxy():
    if not USAR_PROXY:
        registrar("Proxy desactivado.")
        return
    if not puerto_abierto(PROXY_HOST, PROXY_PORT):
        registrar(
            "Proxy SOCKS5 no está en %s:%s. Conexión directa."
            % (PROXY_HOST, PROXY_PORT)
        )
        return
    try:
        import socks
        import socket

        socks.set_default_proxy(socks.SOCKS5, PROXY_HOST, PROXY_PORT)
        socket.socket = socks.socksocket
        registrar("Proxy SOCKS5 activo en %s:%s" % (PROXY_HOST, PROXY_PORT))
    except ImportError:
        registrar("Falta pysocks. Conexión directa.")


configurar_proxy()

# =========================
# VARIABLES GLOBALES
# =========================

NOMBRE_USUARIO = None
DATOS_USUARIO = None
API_KEY = leer_api_key()
cliente = anthropic.Anthropic(api_key=API_KEY, timeout=60.0)

# =========================
# =========================
# AUTENTICACION AL INICIO
# =========================

# 1. Intentar cargar desde credenciales.txt primero
usuario, password = cargar_credenciales()
ok = False
datos = None

if usuario and password:
    registrar(f"Intentando autenticación con credenciales guardadas de: {usuario}")
    ok, mensaje, datos = autenticar_usuario(usuario, password)
    if not ok:
        registrar(f"Credenciales guardadas inválidas ({mensaje}), solicitando de nuevo...")
        usuario, password = None, None

# 2. Si no hay guardadas o no eran válidas, pedir con la ventana nativa
if not usuario or not password:
    usuario, password = pedir_credenciales()
    if not usuario or not password:
        sys.exit(0)

    ok, mensaje, datos = autenticar_usuario(usuario, password)
    if not ok:
        aviso(mensaje, "Error de autenticacion")
        sys.exit(1)

    # 3. Guardar las credenciales válidas en credenciales.txt para futuros inicios
    guardar_credenciales(usuario, password)

NOMBRE_USUARIO = datos.get('usuario')
PASSWORD_USUARIO = password
DATOS_USUARIO = datos
registrar(f"Usuario autenticado: {NOMBRE_USUARIO}")


# CAPTURA DE PANTALLA
# =========================

def capturar_pantalla():
    try:
        import mss

        with mss.MSS() as sct:
            monitor = sct.monitors[1]
            shot = sct.grab(monitor)
            imagen = Image.frombytes("RGB", shot.size, shot.rgb)
            return imagen, int(monitor["left"]), int(monitor["top"])
    except Exception as e:
        registrar("mss no disponible, usando ImageGrab: " + str(e))
        imagen = ImageGrab.grab()
        return imagen, 0, 0


def reducir_imagen(imagen):
    ancho, alto = imagen.size
    escala = min(1.0, LADO_MAX / max(ancho, alto))
    if escala < 1.0:
        nueva = (round(ancho * escala), round(alto * escala))
        imagen = imagen.resize(nueva, Image.Resampling.LANCZOS)
    return imagen


def imagen_a_b64(imagen):
    buffer = BytesIO()
    imagen.save(buffer, format="PNG", optimize=True)
    return base64.b64encode(buffer.getvalue()).decode()


# =========================
# CONSULTA A CLAUDE
# =========================

ERRORES_REINTENTABLES = (
    anthropic.RateLimitError,
    anthropic.InternalServerError,
    anthropic.APIConnectionError,
    anthropic.NotFoundError,
)

_bloqueo = threading.Lock()


def consultar_ia(imagen_b64):
    ultimo_error = None
    for modelo in MODELOS:
        try:
            registrar("Consultando modelo: " + modelo)
            resp = cliente.messages.create(
                model=modelo,
                max_tokens=MAX_TOKENS,
                system=PROMPT_SISTEMA,
                tools=[HERRAMIENTA],
                tool_choice={"type": "tool", "name": HERRAMIENTA["name"]},
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": imagen_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "Omite TODA pregunta que ya tenga una opción marcada. "
                                "Usa SOLO la primera pregunta sin marcar, de arriba "
                                "hacia abajo. Resuélvela y selecciona su opción."
                            ),
                        },
                    ],
                }],
            )
            for bloque in resp.content:
                if bloque.type == "tool_use":
                    return bloque.input
            raise ValueError("La respuesta no incluyó tool_use")
        except anthropic.AuthenticationError as e:
            registrar("API key inválida: " + str(e))
            aviso(
                "Error de autenticación con Anthropic.\n\n"
                "Contacta al soporte técnico."
            )
            raise
        except ERRORES_REINTENTABLES as e:
            ultimo_error = e
            registrar("Modelo " + modelo + " falló, reintento: " + str(e))
            continue
    raise RuntimeError("Todos los modelos fallaron: " + str(ultimo_error))


# =========================
# ENVÍO A SUPABASE Y TELEGRAM
# =========================

def obtener_telegram_chat_id():
    global DATOS_USUARIO
    if not NOMBRE_USUARIO:
        return None
    chat_id = DATOS_USUARIO.get('telegram_chat_id') if DATOS_USUARIO else None
    if not chat_id:
        # 1. Intentar desde archivo local de sesiones de telegram
        try:
            for ruta in [
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "sesiones_telegram.json"),
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sesiones_telegram.json")
            ]:
                if os.path.exists(ruta):
                    with open(ruta, "r", encoding="utf-8") as f:
                        sesiones = json.load(f)
                        if NOMBRE_USUARIO and NOMBRE_USUARIO.lower() in sesiones:
                            chat_id = sesiones[NOMBRE_USUARIO.lower()]
                            break
        except Exception:
            pass
    if not chat_id:
        try:
            resp = supabase_client.table("usuarios_app").select("telegram_chat_id").eq("usuario", NOMBRE_USUARIO).limit(1).execute()
            if resp.data and len(resp.data) > 0:
                chat_id = resp.data[0].get("telegram_chat_id")
                if chat_id and DATOS_USUARIO:
                    DATOS_USUARIO['telegram_chat_id'] = chat_id
        except Exception:
            pass
    return chat_id


def _disparar_telegram_thread(chat_id, letra):
    try:
        from config import TELEGRAM_BOT_TOKEN
        if not TELEGRAM_BOT_TOKEN or "AQUI" in TELEGRAM_BOT_TOKEN:
            return
        mapa_conteo = {"A": 1, "B": 2, "C": 3, "D": 4}
        cantidad = mapa_conteo.get(letra.upper(), 1)
        for i in range(1, cantidad + 1):
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = json.dumps({
                "chat_id": chat_id,
                "text": f"📳 ({i}/{cantidad})",
                "disable_notification": False
            }).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                pass
            if i < cantidad:
                time.sleep(5.0)
    except Exception as e:
        registrar(f"Error enviando vibración a Telegram: {e}")


def enviar_vibracion_telegram(letra):
    try:
        chat_id = obtener_telegram_chat_id()
        if chat_id:
            threading.Thread(target=_disparar_telegram_thread, args=(chat_id, letra), daemon=True).start()
    except Exception as e:
        registrar(f"Error disparando hilo de Telegram: {e}")


def enviar_a_supabase(letra):
    """Envía la letra a Supabase con el usuario para que el panel web la reciba."""
    try:
        if NOMBRE_USUARIO:
            supabase_client.table("vibraciones").insert({
                "letra": letra,
                "usuario": NOMBRE_USUARIO,
                "id_licencia": NOMBRE_USUARIO,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }).execute()
            registrar(f"Letra {letra} enviada a Supabase (usuario: {NOMBRE_USUARIO})")
        else:
            registrar(f"ADVERTENCIA: No se envió vibración a Supabase (sin usuario)")
        return True
    except Exception as e:
        registrar("Error al enviar a Supabase: " + str(e))
        return False


# =========================
# CICLO PRINCIPAL
# =========================

def puede_vibrar_ahora():
    """Verifica en Supabase si el usuario tiene permiso para vibrar ahora mismo (licencia activa, no expirada y en horario)"""
    try:
        device_id = obtener_device_id()
        resp = supabase_client.rpc('autenticar_usuario_app', params={
            'p_usuario': NOMBRE_USUARIO,
            'p_password': PASSWORD_USUARIO,
            'p_device_id': device_id,
            'p_origen': 'desktop_check',
        }).execute()
        if resp.data and resp.data.get('exito'):
            return resp.data.get('puede_vibrar', False)
    except Exception as e:
        registrar(f"Error verificando permisos de vibración: {e}")
    return False


def ejecutar_ciclo():
    if not _bloqueo.acquire(blocking=False):
        registrar("Ya hay un ciclo en curso.")
        return

    try:
        if not puede_vibrar_ahora():
            registrar("Vibración bloqueada: cuenta inactiva, licencia expirada o fuera de horario de examen.")
            return

        registrar("Capturando pantalla...")
        imagen, orig_x, orig_y = capturar_pantalla()
        img_proc = reducir_imagen(imagen)

        datos = consultar_ia(imagen_a_b64(img_proc))

        omitidas = str(datos.get("preguntas_omitidas", "")).strip()
        if omitidas:
            registrar("Preguntas ya marcadas (omitidas): " + omitidas)
        registrar("Pregunta pendiente: " + str(datos.get("pregunta", "")))
        registrar("Más preguntas debajo: " + str(datos.get("hay_mas_preguntas", "")))
        registrar("Opción: " + str(datos.get("texto", "")))
        registrar("Letra: " + str(datos.get("letra", "")))

        letra = datos.get("letra", "")
        if letra:
            enviar_a_supabase(letra)
            enviar_vibracion_telegram(letra)
            registrar(f"Respuesta enviada: {letra}")
        else:
            registrar("No se pudo determinar la respuesta")

    except Exception as e:
        registrar("Error en ciclo: " + str(e))
        traceback.print_exc()
    finally:
        _bloqueo.release()


# =========================
# HOTKEYS
# =========================

for hotkey in HOTKEYS_CAPTURA:
    keyboard.add_hotkey(hotkey, ejecutar_ciclo)

def cerrar_programa():
    registrar("Cerrando programa por atajo de teclado...")
    os._exit(0)

hotkeys_salida = ["ctrl+shift+c", "ctrl+shift+q", "ctrl+alt+q"]
for hk in hotkeys_salida:
    try:
        keyboard.add_hotkey(hk, cerrar_programa)
    except Exception as e:
        registrar(f"Error registrando hotkey salida {hk}: {e}")

# =========================
# ICONO EN ADMINISTRADOR
# =========================

if sys.platform == "win32":
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass
    try:
        ctypes.windll.kernel32.SetConsoleTitleW("SmowlCM")
    except Exception:
        pass

_ICONO_TAREAS = {}


def mostrar_icono_en_administrador():
    """Ventana oculta con el icono del .exe para que salga en el Administrador de tareas."""
    if sys.platform != "win32":
        return
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        shell32 = ctypes.windll.shell32

        LRESULT = ctypes.c_ssize_t
        WNDPROC = ctypes.WINFUNCTYPE(
            LRESULT, wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM
        )

        @WNDPROC
        def wnd_proc(hwnd, msg, wparam, lparam):
            if msg == 0x0010:  # WM_CLOSE
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [
                ("style", ctypes.c_uint),
                ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE),
                ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR),
            ]

        hicon_grande = wintypes.HICON()
        hicon_chico = wintypes.HICON()
        if getattr(sys, "frozen", False):
            origen = sys.executable
        else:
            origen = os.path.join(BASE_DIR, "Smowl.ico")
            if not os.path.isfile(origen):
                origen = os.path.join(BASE_DIR, "..", "Smowl.ico")
            if not os.path.isfile(origen):
                origen = os.path.join(BASE_DIR, "unnamed.ico")
            if not os.path.isfile(origen):
                origen = os.path.join(BASE_DIR, "unnamed.png")
        shell32.ExtractIconExW(
            origen, 0, ctypes.byref(hicon_grande), ctypes.byref(hicon_chico), 1
        )

        hinstance = kernel32.GetModuleHandleW(None)
        clase = "SmowlCM"
        wc = WNDCLASSW()
        wc.lpfnWndProc = wnd_proc
        wc.hInstance = hinstance
        wc.hIcon = hicon_grande
        wc.lpszClassName = clase
        user32.RegisterClassW(ctypes.byref(wc))

        WS_POPUP = 0x80000000
        WS_EX_TOOLWINDOW = 0x00000080
        WS_EX_NOACTIVATE = 0x08000000
        hwnd = user32.CreateWindowExW(
            WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
            clase,
            "SmowlCM",
            WS_POPUP,
            0,
            0,
            0,
            0,
            None,
            None,
            hinstance,
            None,
        )
        if hwnd:
            WM_SETICON = 0x0080
            user32.SendMessageW(hwnd, WM_SETICON, 1, hicon_grande)
            user32.SendMessageW(hwnd, WM_SETICON, 0, hicon_chico or hicon_grande)
            user32.ShowWindow(hwnd, 0)

        _ICONO_TAREAS["wnd_proc"] = wnd_proc
        _ICONO_TAREAS["hwnd"] = hwnd
        _ICONO_TAREAS["hicon_grande"] = hicon_grande
        _ICONO_TAREAS["hicon_chico"] = hicon_chico
    except Exception:
        registrar("No se pudo registrar el icono en el Administrador de tareas.")


mostrar_icono_en_administrador()

# =========================
# MAIN LOOP
# =========================

registrar("Servidor iniciado. Presiona . para capturar pantalla.")
registrar("Presiona Ctrl+Shift+C para salir.")

try:
    keyboard.wait()
except KeyboardInterrupt:
    registrar("Interrumpido por el usuario")
    sys.exit(0)

