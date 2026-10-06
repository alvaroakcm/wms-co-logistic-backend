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

## EP-03, EP-04 y EP-05

EP-03 implementa la recepción desde guías, validación física, lotes,
incidencias, asignación de ubicación e impresión del pedido de ingreso. EP-04
implementa existencias filtrables, ubicabilidad, ocupación, vencimientos,
traslados internos confirmables y división/reempaque de pallets con
trazabilidad padre-hijo. EP-05 incorpora pedidos de salida multilínea,
validación y reserva de stock, confirmación de picking y cierre transaccional
del despacho con descuento automático de inventario. También incluye
cancelación con liberación de reservas, sugerencia FEFO, picking por zona,
historial y tiempos, incidencias e impresión del pedido de salida.

Para preparar las estructuras y los permisos de ambos módulos:

```bash
python manage.py migrate
python manage.py bootstrap_access --admin-email admin@cologistic.com
```

## EP-06: Reportes y BI

EP-06 incorpora un dashboard consolidado con inventario, ocupación,
recepciones, despachos, movimientos, incidencias y tiempos operativos. Incluye
ocupación por almacén y zona, actividad por responsable, historial filtrable de
movimientos, trazabilidad integral del producto y exportaciones nativas PDF y
XLSX. Los reportes se calculan sobre las operaciones de EP-03, EP-04 y EP-05;
no mantienen copias paralelas de los saldos.

Los permisos nuevos son `reportes.ver`, `reportes.exportar` y
`trazabilidad.ver`. Ejecuta nuevamente `bootstrap_access` para asignarlos a
Gerencia, Jefe de Operaciones, Analista de Inventarios y Administrador TI.

## EP-07: Planificación y capacidad operativa

EP-07 proyecta la ocupación diaria en pallets equivalentes combinando la
capacidad actual con recepciones y despachos programados. Permite consultar por
almacén, cliente y periodo, comparar el plan con la ocupación real reconstruida
y detectar fechas que superan un umbral configurable. La vista operativa
consolida capacidad disponible, volumen de entrada/salida y documentos
programados para apoyar la asignación de espacios, personal y recursos.

El permiso `planificacion.ver` habilita el módulo para Gerencia, Jefe de
Operaciones, Analista de Inventarios y Administrador TI.

## EP-08: Operaciones técnicas

EP-08 agrega una consola exclusiva para Administrador TI con monitoreo de
disponibilidad, incidentes, telemetría, auditoría exportable, integraciones,
políticas de conservación y despliegues controlados. Los respaldos manuales o
programados registran responsable, tamaño, checksum y resultado.

La restauración real está protegida por `TECHNICAL_ALLOW_RESTORE=false` de
forma predeterminada y exige confirmación exacta. Los despliegues requieren una
versión aprobada, plan de reversión y respaldo válido previo. Ejecuta nuevamente
`bootstrap_access` para asignar los permisos técnicos al rol Administrador TI.

## EP-09: Acondicionamiento de mercadería

EP-09 incorpora solicitudes facturables de repaletizado, registro de su
ejecución con paleta origen/destino, certificación y tarifa, además del
reencajado con cantidades de cajas de origen y destino. Cada servicio conserva
el cliente, stock, responsables y fechas sin alterar el saldo de inventario.

Los servicios completados generan reportes PDF o Excel y pueden marcarse como
enviados a facturación. Los permisos `acondicionamiento.ver`,
`acondicionamiento.solicitar`, `acondicionamiento.ejecutar` y
`acondicionamiento.facturacion` separan las responsabilidades del Cliente,
Operario de almacén y responsables administrativos.

## Pruebas automatizadas

```bash
python manage.py test
```
