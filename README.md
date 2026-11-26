# Sistema Web de Vibraciones 2.0

Sistema web para exámenes con asistencia por vibraciones en tiempo real.

## 📋 Características

- **Panel de Administradores**: Crear y gestionar licencias de usuarios
- **Panel de Clientes**: App web para recibir vibraciones (no requiere instalación)
- **Servidor Python**: Captura de pantalla + IA (Claude) + envío de vibraciones
- **Tiempo Real**: Vibraciones vía Supabase Realtime
- **Multiplataforma**: Funciona en cualquier dispositivo con navegador

## 🚀 Inicio Rápido

1. Lee [docs/CONFIGURACION.md](docs/CONFIGURACION.md) para configurar el sistema
2. Ejecuta el script SQL de [sql/00_todo_junto.sql](sql/00_todo_junto.sql) en Supabase
3. Configura las credenciales en los archivos correspondientes
4. Sube los paneles a hosting (Netlify, Vercel, GitHub Pages)
5. Ejecuta el servidor Python: `cd servidor && python app.py`

## 📁 Estructura del Proyecto

```
carpeta 2.0/
├── panel-admin/          # Panel de administradores
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── panel-cliente/        # Panel de clientes (app web)
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── servidor/            # Servidor Python
│   ├── app.py
│   ├── config.py
│   └── requirements.txt
├── shared/              # Código compartido
└── docs/                # Documentación
    ├── README.md
    ├── CONFIGURACION.md
    └── SQL_SCRIPT.md
```

## 🔧 Dependencias

### Servidor Python
```bash
cd servidor
pip install -r requirements.txt
```

### Frontend
- Supabase JS SDK (CDN)
- No requiere instalación adicional

## 📖 Documentación

- [Guía de Configuración](docs/CONFIGURACION.md) - Instrucciones completas de configuración
- [Script SQL](docs/SQL_SCRIPT.md) - Script para configurar Supabase
- [README de Documentación](docs/README.md) - Resumen técnico del proyecto

## 🎯 Flujo de Uso

1. **Administrador**: Crea licencia en panel-admin
2. **Cliente**: Ingresa credenciales en panel-cliente
3. **Servidor**: Ejecuta servidor Python con mismas credenciales
4. **Uso**: Presiona F8 en servidor → Captura pantalla → Claude analiza → Envía vibración → Panel-cliente vibra

## 🔒 Seguridad

- Autenticación por usuario/contraseña
- Políticas RLS en Supabase
- Filtrado de vibraciones por usuario
- Validación de horarios
- Expiración automática de licencias

## ⚠️ Importante

Antes de usar, configura las credenciales en:
- `panel-admin/app.js` (líneas 2-3)
- `panel-cliente/app.js` (líneas 2-3)
- `servidor/config.py` (líneas 3-5)

## 📞 Soporte

Revisa la documentación en `docs/` para solución de problemas.
