# Deploy ItsComing - Cloudflare Tunnel + Vercel

## Arquitectura

```
Vercel (Frontend React) → Cloudflare Tunnel → Tu PC (Django + PostgreSQL)
```

## Lo que ya está configurado

- ✅ `requirements.txt` con `gunicorn`
- ✅ `settings.py` con `ALLOWED_HOSTS=['*']`, `STATIC_ROOT`, `CORS_ALLOW_ALL_ORIGINS=True`
- ✅ `start_server.bat` para iniciar todo con un click
- ✅ Frontend usa `VITE_API_URL` desde env var

---

## Pasos que DEBES hacer manualmente

### 1. Instalar Cloudflare Tunnel

Abre PowerShell como administrador y ejecuta:

```powershell
winget install Cloudflare.cloudflared
```

Cierra y abre una nueva terminal para que el comando esté disponible.

### 2. Instalar gunicorn en tu venv

```powershell
cd C:\Users\jared\OneDrive\Documentos\itssccc\itscomming
venv\Scripts\activate
pip install gunicorn
```

### 3. Subir código a GitHub

```powershell
git add .
git commit -m "config for cloudflare tunnel deploy"
git push
```

### 4. Deploy Frontend a Vercel

1. Ve a [vercel.com](https://vercel.com) → "Add New Project"
2. Importa tu repo de GitHub
3. Configura:
   - **Framework Preset**: Vite
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
4. **NO deployes todavía** — necesitas la URL del tunnel primero

### 5. Iniciar el Servidor

1. **Doble click en `start_server.bat`**
2. Se abrirán 2 ventanas:
   - **Django Backend** — Gunicorn corriendo en puerto 8001
   - **Cloudflare Tunnel** — Muestra la URL pública

3. **Espera a que Cloudflare muestre la URL**, algo como:
   ```
   +-------------------------------------------------------------------+
   |  Your quick Tunnel has been created! Visit it at:                 |
   |  https://abc123-def456.trycloudflare.com                          |
   +-------------------------------------------------------------------+
   ```

4. **Copia esa URL** (sin el `https://`)

### 6. Configurar VITE_API_URL en Vercel

1. En Vercel, ve a tu proyecto → **Settings** → **Environment Variables**
2. Agrega:
   - **Key**: `VITE_API_URL`
   - **Value**: `https://abc123-def456.trycloudflare.com` (la URL que copiaste)
3. Guarda

### 7. Deploy en Vercel

1. Ve a **Deployments** → **Redeploy** (o haz un nuevo push a GitHub)
2. Espera a que termine el build
3. ¡Listo! Tu frontend está live

---

## Cada vez que reinicies el servidor

1. **Doble click en `start_server.bat`**
2. Cloudflare generará una **nueva URL** (cambia cada vez)
3. **Actualiza `VITE_API_URL` en Vercel** con la nueva URL
4. **Redeploy en Vercel**

> **Tip**: Si quieres una URL permanente, puedes comprar un dominio (~$10/año) y configurarlo en Cloudflare.

---

## Verificar que funciona

1. Abre la URL de tu frontend en Vercel (ej: `https://tu-app.vercel.app`)
2. Deberías ver el dashboard con datos
3. Si ves errores de red, verifica:
   - El tunnel está corriendo (ventana de Cloudflare abierta)
   - Django está corriendo (ventana de Gunicorn sin errores)
   - La `VITE_API_URL` en Vercel coincide con la URL del tunnel

---

## Solución de Problemas

### Error: "cloudflared no se reconoce"
- Reinicia la terminal después de instalar
- Verifica con: `cloudflared --version`

### Error: "gunicorn no se reconoce"
- Activa el venv: `venv\Scripts\activate`
- Instala: `pip install gunicorn`

### Error: "CORS blocked" en el navegador
- Verifica que `CORS_ALLOW_ALL_ORIGINS = True` en `settings.py`
- Reinicia Django

### Error: "Connection refused" en Vercel
- Verifica que el tunnel está corriendo
- Verifica que la URL en `VITE_API_URL` es correcta
- Abre `https://tu-url.trycloudflare.com/api/v1/today/` en el navegador — debería funcionar

### La PC se duerme y el servidor se cae
- Ve a **Configuración de energía** → **Suspender** → **Nunca**
- Desactiva el protector de pantalla
