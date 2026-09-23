# Pescaderia Urbina's

Aplicacion web movil instalable para una pescaderia. Incluye catalogo de productos, carrito, pedidos, vales de precio y panel separado para vendedor y comprador. Funciona como PWA desde Android o iPhone y usa Python/Flask con SQLite como respaldo.

## Requisitos

- Python 3.10 o superior

## Instalacion en VS Code

1. Abre una terminal en esta carpeta.
2. Crea y activa un entorno virtual:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Instala las dependencias:

   ```powershell
   pip install -r requirements.txt
   ```

4. Ejecuta la aplicacion:

   ```powershell
   python app.py
   ```

5. Abre `http://127.0.0.1:5000` en el navegador.

La base de datos `pescaderia.db` se crea automaticamente al iniciar por primera vez.

## Usuarios de demostracion

- Vendedor: `vendedor@urbinas.local` / `vendedor123`
- Comprador: `cliente@urbinas.local` / `cliente123`

El vendedor puede agregar productos, crear vales y actualizar estados de pedidos. El comprador puede agregar mercaderia al pedido, aplicar un vale y consultar su historial.

Los compradores nuevos pueden registrarse desde `Crear cuenta`. Sus contraseñas se guardan con hash seguro en la tabla `users`; el vendedor mantiene su acceso separado.

## Sincronizacion

Las pantallas abiertas consultan cambios de la base cada 5 segundos. Si el vendedor modifica productos, vales o estados de pedidos, los compradores reciben la vista actualizada automáticamente al siguiente ciclo.

## Instalarla en un telefono

1. Ejecuta la aplicacion en una computadora accesible desde la misma red Wi-Fi.
2. En el telefono abre la direccion de la computadora, por ejemplo `http://192.168.1.20:5000`.
3. En Android usa el menu del navegador y selecciona `Instalar aplicacion`. En iPhone usa `Compartir` y `Anadir a pantalla de inicio`.

La aplicacion movil se sirve desde el mismo backend Python; por eso los pedidos, productos y vales permanecen en `pescaderia.db` y no se separan entre dispositivos.

## Nombre publico

El nombre de despliegue elegido es `pescaderiaurbinas`. En un servicio gratuito compatible puede quedar publicado como `pescaderiaurbinas.onrender.com`. La configuracion esta en `render.yaml` y `Procfile`.

## Logo personalizado

El logo anterior fue eliminado. Cuando tengas tu imagen, colócala en `static/logo.png` y se puede conectar a la cabecera y al icono de la aplicacion sin modificar los pedidos ni la base de datos.
