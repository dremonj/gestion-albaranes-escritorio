# 📦 Gestión de Albaranes (aplicación de escritorio)

Aplicación de escritorio para Windows hecha en **Python** para crear **albaranes de entrega**, gestionar **clientes** y
controlar el **inventario**. Cada persona tiene **su propia cuenta** (usuario y contraseña) y solo ve sus datos.

> Existe también una versión web anterior: [gestion-albaranes](https://github.com/dremonj/gestion-albaranes).

## Funcionalidades

- **Cuentas de usuario**: crear cuenta, iniciar y cerrar sesión, cambiar la contraseña. Cada cuenta tiene sus propios
  albaranes, clientes, productos y numeración. Las contraseñas se guardan cifradas (PBKDF2-SHA256 con sal).
- **Albaranes**
  - Varias líneas por albarán: productos del inventario o conceptos libres (por ejemplo, «Portes»).
  - Precio, descuento e IVA (21, 10, 4 o 0 %) por línea, con totales y desglose de IVA automáticos.
  - Albarán **valorado** (con precios) o **sin valorar** (solo cantidades).
  - Estados: **Borrador → Emitido (pendiente de entrega) → Entregado**, o **Anulado**.
  - Numeración correlativa por año (`ALB-2026-0001`) con prefijo configurable.
  - **PDF** en formato A4 listo para imprimir, con recuadro de firma «Recibí conforme».
  - Duplicar, buscar y filtrar por estado, e historial de cambios.
- **Inventario**
  - Alta, edición y baja de productos (referencia, precio, IVA, unidad de medida y stock mínimo).
  - **Modificar unidades**: botones −1 / +1 o ajuste de entrada, salida o recuento exacto, con motivo.
  - Al emitir un albarán se descuentan las unidades; al anularlo se devuelven. No deja emitir sin stock suficiente.
  - Avisos de stock bajo mínimos e historial de movimientos de cada producto.
- **Clientes**: alta, edición, búsqueda y creación rápida desde el propio albarán.
- **Mi empresa y cuenta**: datos de la empresa que aparecen en los albaranes, cambio de contraseña, copias de seguridad
  y datos de ejemplo.
- **Acerca de**: qué es un albarán y cómo funciona la aplicación.

## Cuenta de prueba

La primera vez que se abre la aplicación en un ordenador se crea sola una cuenta de prueba con datos de ejemplo:

| Usuario | Contraseña |
|---------|------------|
| `demo`  | `demo1234` |

En la pantalla de inicio de sesión también aparece el botón **«Entrar con la cuenta de prueba»**.

## Cómo ejecutarla

### Opción 1: el `.exe` (no hace falta instalar nada)

1. Ve a [**Releases**](https://github.com/dremonj/gestion-albaranes-escritorio/releases) y descarga `GestionAlbaranes.exe`.
2. Haz doble clic en él. Si Windows muestra «Windows protegió su PC», pulsa **Más información → Ejecutar de todas formas**.
   El aviso sale porque el programa no está firmado digitalmente.

### Opción 2: desde el código, con doble clic (necesita Python)

1. Instala [Python 3.11 o superior](https://www.python.org/downloads/) y marca **«Add python.exe to PATH»**.
2. Descarga el proyecto (**Code → Download ZIP**) y descomprímelo.
3. Haz doble clic en **`ejecutar.bat`**. La primera vez tarda un minuto en instalar las librerías.

### Opción 3: desde la terminal

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Cómo probarla

1. Entra con la **cuenta de prueba** (`demo` / `demo1234`), o crea tu propia cuenta en **«Crear cuenta»**. Si marcas
   **«Rellenar mi cuenta con datos de ejemplo»**, tendrás clientes, productos y albaranes con los que practicar.
2. Pulsa **＋ Nuevo albarán**, elige un cliente y un producto, cambia la cantidad y pulsa **Guardar y emitir**.
   Recibirá un número y el stock bajará (compruébalo en **Inventario**).
3. En el albarán, pulsa **Ver / imprimir PDF**.
4. Pulsa **Marcar como entregado** y luego **Anular**: el stock vuelve a subir.
5. Cierra sesión, crea una segunda cuenta y comprueba que no ve los datos de la primera.

**Pruebas automáticas:**

```bash
pip install -r requirements-dev.txt
pytest
```

## Dónde se guardan los datos

En una base de datos SQLite en `%APPDATA%\GestionAlbaranes\albaranes.db`, la misma para el `.exe` y para el código.
Desde **Mi empresa y cuenta → Guardar copia…** puedes hacer copias de seguridad.
Si ocurre un error inesperado, se muestra un aviso y el detalle se guarda en `errores.log`, en esa misma carpeta.

## Crear el `.exe`

Haz doble clic en `construir_exe.bat`. El resultado queda en `dist\GestionAlbaranes.exe`.

## Estructura

```
main.py                         Punto de entrada
gestion_albaranes/
  db.py                         Base de datos SQLite, esquema y copias de seguridad
  auth.py                       Cuentas: registro, inicio de sesión y contraseñas
  logica.py                     Reglas de negocio (albaranes, stock, clientes), siempre filtradas por usuario
  pdf.py                        Generación del albarán en PDF
  ui/                           Interfaz (CustomTkinter): login, ventana principal, pantallas y diálogos
  recursos/                     Icono
tests/                          Pruebas automáticas (pytest)
ejecutar.bat                    Arranque con doble clic
construir_exe.bat               Genera el .exe con PyInstaller
```

## Licencia

MIT
