# API de autenticación

## `GET /api/auth/me/`

Devuelve el perfil y el acceso efectivo del usuario autenticado.

### Encabezados

```http
Authorization: Bearer <supabase_access_token>
```

### Respuesta `200`

```json
{
  "id": "3f09a7b9-e9fd-48dc-b134-20a4f909e629",
  "correo": "operador@empresa.com",
  "nombre": "Ana",
  "apellido": "Torres",
  "roles": [{"id_rol": 1, "nombre": "Operador"}],
  "permisos": ["inventario.ver"]
}
```

### Errores

- `401`: token ausente, inválido o expirado; perfil inexistente o inactivo.
- `503`: Supabase Auth o la consulta del perfil no están disponibles.

## Usuarios

- `GET /api/users/?search=` requiere `usuarios.ver`.
- `POST /api/users/` requiere `usuarios.crear`; si asigna roles también exige
  `usuarios.asignar_roles`.
- `PATCH /api/users/<uuid>/` requiere `usuarios.editar`.
- `PUT /api/users/<uuid>/roles/` requiere `usuarios.asignar_roles`.
- `PATCH /api/users/<uuid>/status/` requiere `usuarios.desactivar`. Recibe
  `{"estado": false}` para desactivar o `{"estado": true}` para reactivar.
  Un administrador no puede desactivar su propia cuenta.

El alta crea primero la identidad en Supabase Auth y después el perfil WMS. Si
la segunda operación falla, Django elimina la identidad recién creada para no
dejar cuentas huérfanas.

La desactivación aplica un bloqueo administrativo en Supabase Auth y cambia el
estado del perfil dentro de una operación compensable. Django también revisa
el estado en cada petición, por lo que un token emitido previamente deja de
tener acceso a la API de inmediato.

## Roles y permisos

- `GET /api/roles/` y `GET /api/permissions/` requieren `roles.ver`.
- `POST /api/roles/` y `PATCH /api/roles/<id>/` requieren `roles.gestionar`.

## Clientes

- `GET /api/clients/?search=&estado=` requiere `clientes.ver`. La búsqueda
  incluye razón social, RUC y contacto; `estado` acepta `true` o `false`.
- `POST /api/clients/` requiere `clientes.crear`.
- `PATCH /api/clients/<id>/` requiere `clientes.editar`.

El RUC debe contener exactamente 11 dígitos y no puede repetirse.

## Productos

- `GET /api/products/?codigo=&nombre=&cliente=&estado=` requiere
  `productos.ver`.
- `POST /api/products/` requiere `productos.crear`.
- `PATCH /api/products/<id>/` requiere `productos.editar`.
- `POST /api/products/<id>/calculate-boxes/` requiere `productos.ver` y recibe
  `{"cantidad_pallets": "3.00"}`.
- `GET /api/catalogs/product-options/` requiere `productos.ver`.

El filtro `codigo` busca tanto por SKU como por EAN y `cliente` busca por razón
social o RUC. El SKU es único dentro de cada cliente y el EAN es único en todo
el catálogo. Las actualizaciones conservan el identificador del registro para
no romper sus relaciones históricas.

La unidad comercial solo puede ser `CJ` (Caja) o `UND` (Unidad). Los productos
por caja requieren `factor_conversion` mayor que cero y mantienen una
conversión `PLT -> CJ`; el cálculo devuelve
`cantidad_cajas = cantidad_pallets * factor_conversion`. Los productos por
unidad no admiten factor ni conversión desde pallets.

## Almacenes, zonas y ubicaciones

- `GET /api/warehouses/?search=&estado=` requiere `almacenes.ver`.
- `POST /api/warehouses/` requiere `almacenes.crear`.
- `GET /api/zones/?almacen=` requiere `ubicaciones.ver`.
- `POST /api/zones/` requiere `ubicaciones.crear`.
- `GET /api/locations/?almacen=&zona=&rack=&estado=` requiere
  `ubicaciones.ver`. `estado` acepta `disponible`, `ocupada` o `inactiva`.
- `POST /api/locations/` requiere `ubicaciones.crear`.
- `PATCH /api/locations/<id>/` requiere `ubicaciones.editar`.
- `GET /api/catalogs/location-options/` devuelve almacenes y zonas para los
  formularios.

La respuesta incluye almacén, zona, pasillo, rack, nivel, posición,
capacidades, stock total y estado operativo. Una ubicación con
`cantidad_total > 0` en inventario no puede desactivarse.

## Importación de datos maestros

`POST /api/imports/master-data/` requiere `importaciones.ejecutar` y recibe
`multipart/form-data` con:

- `tipo`: `clientes`, `productos`, `almacenes` o `ubicaciones`.
- `archivo`: CSV UTF-8 de hasta 2 MB y 5,000 filas.

La respuesta contiene `procesados`, `cargados`, `rechazados` y
`detalle_rechazados`. Cada fila se procesa dentro de su propia transacción,
por lo que una fila inválida no revierte las filas correctas.

La plantilla de productos incluye `factor_conversion`: es obligatoria cuando
`unidad_codigo` es `CJ` y debe quedar vacía cuando es `UND`.
