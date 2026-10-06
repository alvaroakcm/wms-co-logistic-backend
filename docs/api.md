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

## Recepción y almacenamiento

- `GET /api/receipts/?cliente=&producto=&documento=&estado=&responsable=&fecha_desde=&fecha_hasta=`
  requiere `recepciones.ver` y permite consultar el historial completo.
- `POST /api/receipts/` requiere `recepciones.crear` y registra una guía con
  una o varias líneas.
- `GET /api/receipts/<id>/` requiere `recepciones.ver` y devuelve líneas,
  lotes, discrepancias, ubicaciones asignadas e incidencias.
- `GET /api/receipts/<id>/document/` requiere `recepciones.imprimir` y genera
  los datos inmutables del pedido de ingreso asociado a la guía para su
  impresión.
- `POST /api/receipts/<id>/validate/` requiere `recepciones.validar`, exige
  confirmar el documento y enviar el conteo de todas las líneas. Las
  diferencias generan registros de faltante, sobrante o rechazo.
- `POST /api/receipts/<id>/assign-location/` requiere
  `recepciones.asignar_ubicacion`; crea stock y registra la ubicación física.
  Si el producto controla lote, también exige `id_pedido_ingreso_lote`.
- `POST /api/receipts/<id>/lots/` requiere `recepciones.lotes`, registra uno o
  varios lotes con fabricación, vencimiento y cantidad, y exige que su suma
  coincida con la cantidad aceptada.
- `POST /api/receipts/<id>/incidents/` requiere `recepciones.incidencias`.
- `GET /api/catalogs/reception-options/` devuelve clientes, productos,
  ubicaciones disponibles y estados del flujo.

Ejemplo de registro:

```json
{
  "id_cliente": 1,
  "codigo_documento": "T001-000123",
  "fecha_programada": "2026-09-14",
  "transporte_placa": "ABC-123",
  "transporte_conductor": "Ana Torres",
  "transporte_brevete": "Q12345678",
  "lineas": [
    {
      "id_producto": 8,
      "cantidad_esperada": "48.00",
      "cantidad_pallets": "2.00"
    }
  ]
}
```

Cada línea guarda una copia del código y descripción del producto para que el
historial permanezca entendible aunque el catálogo maestro sea actualizado.
Para productos por caja, el backend toma el factor vigente, calcula las cajas
desde los pallets y guarda ambos valores como parte del documento de ingreso.

Ejemplo de lotes:

```json
{
  "id_pedido_ingreso_detalle": 12,
  "lotes": [
    {
      "codigo": "LOT-2026-001",
      "fecha_fabricacion": "2026-08-01",
      "fecha_vencimiento": "2027-08-01",
      "cantidad": "30.00"
    },
    {
      "codigo": "LOT-2026-002",
      "fecha_fabricacion": null,
      "fecha_vencimiento": "2027-09-01",
      "cantidad": "18.00"
    }
  ]
}
```

## Inventario y movimientos internos

- `GET /api/inventory/stocks/?producto=&cliente=&almacen=&ubicacion=&lote=&fecha_vencimiento=&estado=`
  requiere `inventario.ver` y devuelve cantidad total, reservada y disponible,
  además de cliente, producto, almacén, ubicación, lote y pallet.
- `GET /api/inventory/occupancy/` requiere `inventario.ocupacion` y calcula
  capacidad utilizada, disponible y porcentaje por almacén.
- `GET /api/inventory/expiration-alerts/?dias=30&cliente=&producto=&lote=&ubicacion=&fecha_vencimiento=`
  requiere `inventario.vencimientos`; el umbral es configurable por consulta.
- `GET /api/inventory/movements/` requiere `movimientos.ver` y acepta filtros
  por fecha, tipo, producto, origen, destino, responsable y estado.
- `POST /api/inventory/movements/` requiere `movimientos.crear` y registra un
  traslado en estado `PENDIENTE` sin modificar todavía las existencias.
- `POST /api/inventory/movements/<id>/confirm/` requiere
  `movimientos.confirmar`; bloquea los stocks involucrados, vuelve a comprobar
  el saldo y actualiza origen y destino dentro de una sola transacción.
- `POST /api/inventory/repacking/` requiere `movimientos.reempaque`, divide el
  stock en dos o más pallets hijos y registra un movimiento confirmado.
- `GET /api/catalogs/inventory-options/` devuelve almacenes, ubicaciones y
  estados disponibles para los filtros y formularios.

Ejemplo de traslado:

```json
{
  "motivo": "Reabastecimiento de picking",
  "lineas": [
    {
      "id_stock_origen": 12,
      "id_ubicacion_destino": 31,
      "cantidad": "20.00"
    }
  ]
}
```

Ejemplo de reempaque o división:

```json
{
  "id_stock_origen": 12,
  "motivo": "Pallet de 50 recibido como 20 + 30",
  "fracciones": [
    {"codigo_pallet": "PLT-12-A", "cantidad": "20.00"},
    {"codigo_pallet": "PLT-12-B", "cantidad": "30.00"}
  ]
}
```

Cada pallet resultante guarda `id_pallet_padre`, por lo que el historial puede
reconstruir el pallet original incluso después de múltiples divisiones.

## Pedidos y despacho

- `GET /api/orders/?cliente=&estado=&documento=&responsable=&fecha_desde=&fecha_hasta=`
  requiere `pedidos.ver` y devuelve pedidos, líneas, reservas, picking y
  despacho.
- `POST /api/orders/` requiere `pedidos.crear`; registra la guía de salida con
  una o varias líneas, lote y vencimiento cuando corresponde.
- `POST /api/orders/<id>/validate-stock/` requiere
  `pedidos.validar_stock`; vuelve a comprobar el saldo, reserva existencias por
  ubicación e inicia el picking.
- `POST /api/orders/<id>/prepare/` requiere `pedidos.preparar` y confirma las
  cantidades de todas las reservas. Solo pasa el pedido a `Listo` si la
  preparación está completa.
- `POST /api/orders/<id>/cancel/` requiere `pedidos.cancelar`; libera de forma
  atómica las reservas activas y cambia el pedido a `Cancelado`.
- `GET /api/orders/<id>/document/` requiere `pedidos.imprimir` y genera el
  pedido de salida imprimible con guía, transporte, producto, lote,
  vencimiento, zona, ubicación y cantidad.
- `POST /api/orders/<id>/dispatch/` requiere `despachos.cerrar`; consume las
  reservas, descuenta el stock y cierra pedido y despacho dentro de una misma
  transacción.
- `POST /api/orders/<id>/dispatch/incidents/` requiere
  `despachos.incidencias` y registra tipo, descripción, producto, cantidad,
  responsable y fecha sobre un despacho cerrado.
- `GET /api/dispatches/history/?cliente=&documento=&producto=&responsable=&fecha_desde=&fecha_hasta=`
  requiere `despachos.ver`; devuelve salidas cerradas y promedios de tiempo de
  preparación, despacho y proceso total.
- `GET /api/catalogs/order-options/` devuelve clientes, productos, lotes,
  disponibilidad y estados para formularios y filtros.

Ejemplo de pedido de salida:

```json
{
  "id_cliente": 1,
  "codigo_documento": "GRS-001-000123",
  "fecha_programada": "2026-10-02",
  "transporte_placa": "ABC-123",
  "transporte_conductor": "Ana Torres",
  "lineas": [
    {
      "id_producto": 7,
      "id_lote": 14,
      "cantidad_solicitada": "20.00"
    }
  ]
}
```

El flujo admitido es `Pendiente → En Preparacion → Listo → Despachado`, con
cancelación antes del cierre. La disponibilidad diferencia cantidad total y
reservada. Los lotes disponibles se ordenan por vencimiento y se marca la
sugerencia FEFO, aunque el usuario puede seleccionar el lote solicitado por el
cliente. El cierre rechaza cantidades sin reserva o cambios de saldo
concurrentes para evitar inventario negativo.

## Reportes, BI y trazabilidad

- `GET /api/reports/dashboard/?fecha_desde=&fecha_hasta=&almacen=` requiere
  `reportes.ver` y devuelve KPIs, tendencia diaria, ocupación, alertas,
  tiempos, actividad por responsable y operación reciente.
- `GET /api/reports/occupancy/?almacen=` devuelve capacidad utilizada y
  disponible por almacén, además del desglose de ubicaciones por zona.
- `GET /api/reports/movements/?fecha_desde=&fecha_hasta=&producto=&cliente=&ubicacion=&responsable=&tipo_operacion=&estado=`
  permite analizar el historial operativo con todos los filtros de HU-046.
- `GET /api/reports/traceability/?producto=&lote=&cliente=` requiere
  `trazabilidad.ver` y reconstruye recepciones, lotes, stock actual,
  ubicaciones, traslados, incidencias y despachos del producto.
- `GET /api/reports/export/?tipo=&formato=` requiere `reportes.exportar`.
  `tipo` admite `inventario`, `recepciones`, `movimientos`, `despachos`,
  `ocupacion` o `trazabilidad`; `formato` admite `pdf` o `xlsx`.

Los parámetros de fecha usan `AAAA-MM-DD`. Las exportaciones usan los mismos
filtros que las consultas y entregan archivos descargables, no CSV renombrado.

## Planificación de capacidad

- `GET /api/planning/capacity/?fecha_desde=&fecha_hasta=&almacen=&cliente=&umbral=`
  requiere `planificacion.ver` y devuelve la ocupación real y planificada por
  día, los ingresos y salidas en pallets equivalentes, periodos de riesgo y el
  detalle de operaciones programadas.

El umbral admite valores entre 1 y 100 y el periodo máximo es de 366 días. La
proyección usa la cantidad de pallets declarada en recepciones. Para despachos
convierte unidades mediante el factor comercial del producto; si un documento
histórico carece de esa configuración, utiliza una posición referencial por
línea y el almacén asociado al stock o ubicación disponible del producto.

## Operaciones técnicas

Todos los endpoints requieren sesión y permisos exclusivos de Administrador TI:

- `GET /api/technical/overview/` consolida disponibilidad, componentes activos,
  incidentes, respaldos e integraciones.
- `POST /api/technical/health/check/` ejecuta un diagnóstico y abre o cierra
  incidentes por componente.
- `GET/POST /api/technical/backups/` consulta o genera respaldos; `validate` y
  `restore` verifican integridad y restauran de forma controlada.
- `GET/PATCH /api/technical/backups/schedule/` configura frecuencia y retención.
  `python manage.py run_scheduled_backup` permite integrarlo con cron.
- `GET /api/technical/audit/` consulta acciones críticas y `audit/export`
  descarga el CSV.
- `GET /api/technical/performance/` devuelve latencia, errores, memoria y
  consultas por operación.
- Los recursos `integrations`, `retention`, `releases` y `deployments` permiten
  reintentos autorizados, conservación protegida, aprobación y reversión.

La restauración permanece deshabilitada por defecto. Requiere respaldo válido,
confirmación `RESTAURAR <id>` y `TECHNICAL_ALLOW_RESTORE=true` durante una
ventana de mantenimiento.

## Acondicionamiento de mercadería

- `GET /api/conditioning/options/` entrega clientes activos y stock disponible
  para los formularios.
- `GET /api/conditioning/services/?tipo=&estado=&estado_facturacion=&id_cliente=&q=`
  requiere `acondicionamiento.ver` y lista solicitudes, ejecuciones y cargos.
- `POST /api/conditioning/repallet-requests/` requiere
  `acondicionamiento.solicitar`; registra código, cliente, stock, cantidad,
  especificación de paleta y si el cliente provee la paleta destino.
- `POST /api/conditioning/services/<id>/execute-repallet/` requiere
  `acondicionamiento.ejecutar`; registra paleta destino, cantidad, número de
  paletas, certificación y tarifa.
- `POST /api/conditioning/reboxing/` requiere
  `acondicionamiento.ejecutar`; registra cantidad, cajas de origen/destino y
  tarifa como servicio completado.
- `GET /api/conditioning/services/<id>/report/?formato=pdf|xlsx` genera la
  evidencia facturable de un servicio completado.
- `GET /api/conditioning/billing-report/?formato=pdf|xlsx` consolida los
  servicios completados.
- `POST /api/conditioning/services/<id>/send-billing/` marca el cargo como
  enviado a facturación y evita reenvíos duplicados.

El acondicionamiento mantiene referencias al stock y a los pallets para
trazabilidad, pero no modifica cantidades: el servicio describe un cambio de
embalaje, no un ingreso, traslado o salida de inventario.
