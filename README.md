# WMS Co-Logistic Backend

API empresarial del WMS construida con Django REST Framework. Supabase Auth
autentica a los usuarios y esta API valida sus JWT antes de aplicar el estado,
los roles y los permisos almacenados en PostgreSQL.

## Configuración local

1. Crea y activa un entorno virtual.
2. Instala las dependencias con `pip install -r requirements.txt`.
3. Crea `.env` y completa PostgreSQL, `SUPABASE_URL` y
   `SUPABASE_SECRET_KEY`.
4. En Supabase Auth configura una llave asimétrica RS256 o ES256.
5. Inicia el servidor con `python manage.py runserver`.

El backend obtiene las llaves públicas desde el endpoint JWKS de Supabase. La
llave `SUPABASE_SECRET_KEY=sb_secret_...` se usa solo en el servidor para las
altas y actualizaciones de Supabase Auth. Nunca debe incluirse en React, Git,
capturas ni mensajes.

## Autenticación

Las solicitudes protegidas deben enviar:

```http
Authorization: Bearer <supabase_access_token>
```

`GET /api/auth/me/` valida el token, verifica que exista un perfil activo en
`usuarios.usuario` y devuelve sus roles y permisos efectivos.

El UUID de `usuarios.usuario.id_usuario` debe ser igual al UUID del usuario en
`auth.users.id` de Supabase.

## HU-002, HU-003 y HU-004

- `GET/POST /api/users/`: consulta y registro sincronizado de usuarios.
- `PATCH /api/users/<uuid>/`: actualización sincronizada del perfil y Auth.
- `PUT /api/users/<uuid>/roles/`: reemplazo controlado de roles.
- `PATCH /api/users/<uuid>/status/`: desactivación o reactivación sincronizada
  con Supabase Auth.
- `GET/POST/PATCH /api/roles/`: administración de roles y permisos.
- `GET /api/permissions/`: catálogo de permisos activos.

Cada operación comprueba su permiso en Django. Para inicializar el primer
administrador de forma idempotente:

```bash
python manage.py bootstrap_access --admin-email admin@cologistic.com
```

Una cuenta inactiva queda bloqueada en Supabase Auth y Django continúa
rechazando cualquier access token previamente emitido al comprobar
`usuarios.usuario.estado` en cada solicitud.

## EP-02: catálogos maestros

- `GET/POST /api/clients/`: consulta y registro de clientes.
- `PATCH /api/clients/<id>/`: actualización sin reemplazar el registro ni sus
  relaciones históricas.
- `GET/POST /api/products/`: consulta filtrable y registro de productos.
- `PATCH /api/products/<id>/`: actualización conservando la identidad del
  producto.
- `POST /api/products/<id>/calculate-boxes/`: cálculo de cajas a partir de
  pallets usando el factor comercial configurado.
- `GET /api/catalogs/product-options/`: clientes, categorías y unidades para
  los formularios.
- `GET/POST /api/warehouses/`: consulta y registro de almacenes.
- `GET/POST /api/zones/`: consulta y registro de zonas.
- `GET/POST /api/locations/`: consulta filtrable y registro de ubicaciones.
- `PATCH /api/locations/<id>/`: actualización o desactivación; rechaza la
  desactivación cuando existe stock activo.
- `POST /api/imports/master-data/`: importación CSV de clientes, productos,
  almacenes o ubicaciones con reporte por fila.

Los clientes validan RUC peruano de 11 dígitos y unicidad. Los productos
validan SKU único por cliente y código EAN único. Para crear las unidades de
medida iniciales y la categoría general de forma idempotente:

```bash
python manage.py bootstrap_master_catalogs
```

La estructura de ubicaciones requiere ejecutar las migraciones versionadas:

```bash
python manage.py migrate maestros
```

La importación admite CSV UTF-8 de hasta 2 MB y 5,000 filas. Las plantillas se
descargan desde la pantalla `Importaciones` para conservar los encabezados.

## Pruebas

```bash
python manage.py test apps.usuarios apps.maestros
```
