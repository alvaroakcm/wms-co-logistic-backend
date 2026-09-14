from django.db import models


# =====================================================
# CLIENTE
# =====================================================

class Cliente(models.Model):

    id_cliente = models.AutoField(
        primary_key=True,
        db_column="id_cliente"
    )

    razon_social = models.CharField(
        max_length=150,
        db_column="razon_social"
    )

    ruc = models.CharField(
        max_length=11,
        db_column="ruc"
    )

    contacto_nombre = models.CharField(
        max_length=100,
        db_column="contacto_nombre",
        null=True,
        blank=True
    )

    contacto_telefono = models.CharField(
        max_length=20,
        db_column="contacto_telefono",
        null=True,
        blank=True
    )

    estado = models.BooleanField(
        db_column="estado"
    )

    fecha_registro = models.DateTimeField(
        db_column="fecha_registro"
    )

    fecha_actualizacion = models.DateTimeField(
        db_column="fecha_actualizacion"
    )


    class Meta:
        managed = False
        db_table = '"maestros"."cliente"'

        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"


    def __str__(self):
        return self.razon_social



# =====================================================
# CATEGORIA PRODUCTO
# =====================================================

class CategoriaProducto(models.Model):

    id_categoria = models.AutoField(
        primary_key=True,
        db_column="id_categoria"
    )

    nombre = models.CharField(
        max_length=100,
        db_column="nombre"
    )

    descripcion = models.TextField(
        db_column="descripcion",
        null=True,
        blank=True
    )

    estado = models.BooleanField(
        db_column="estado"
    )


    class Meta:
        managed = False
        db_table = '"maestros"."categoria_producto"'

        verbose_name = "Categoría Producto"
        verbose_name_plural = "Categorías Producto"


    def __str__(self):
        return self.nombre



# =====================================================
# UNIDAD MEDIDA
# =====================================================

class UnidadMedida(models.Model):

    id_unidad_medida = models.AutoField(
        primary_key=True,
        db_column="id_unidad_medida"
    )

    codigo = models.CharField(
        max_length=10,
        db_column="codigo"
    )

    nombre = models.CharField(
        max_length=50,
        db_column="nombre"
    )

    estado = models.BooleanField(
        db_column="estado"
    )


    class Meta:
        managed = False
        db_table = '"maestros"."unidad_medida"'

        verbose_name = "Unidad Medida"
        verbose_name_plural = "Unidades Medida"


    def __str__(self):
        return self.nombre



# =====================================================
# PRODUCTO
# =====================================================

class Producto(models.Model):

    id_producto = models.AutoField(
        primary_key=True,
        db_column="id_producto"
    )

    id_cliente = models.IntegerField(
        db_column="id_cliente"
    )

    id_categoria = models.IntegerField(
        db_column="id_categoria",
        null=True,
        blank=True
    )

    id_unidad_medida = models.IntegerField(
        db_column="id_unidad_medida"
    )

    sku = models.CharField(
        max_length=50,
        db_column="sku"
    )

    codigo_ean = models.CharField(
        max_length=13,
        db_column="codigo_ean"
    )

    nombre = models.CharField(
        max_length=150,
        db_column="nombre"
    )

    descripcion = models.TextField(
        db_column="descripcion",
        null=True,
        blank=True
    )

    controla_lote = models.BooleanField(
        db_column="controla_lote"
    )

    estado = models.BooleanField(
        db_column="estado"
    )

    fecha_registro = models.DateTimeField(
        db_column="fecha_registro"
    )

    fecha_actualizacion = models.DateTimeField(
        db_column="fecha_actualizacion"
    )


    class Meta:
        managed = False
        db_table = '"maestros"."producto"'


    def __str__(self):
        return self.nombre
# =====================================================
# PRODUCTO CONVERSION
# =====================================================

class ProductoConversion(models.Model):

    id_producto_conversion = models.AutoField(
        primary_key=True,
        db_column="id_producto_conversion"
    )

    id_producto = models.IntegerField(
        db_column="id_producto"
    )

    id_unidad_origen = models.IntegerField(
        db_column="id_unidad_origen"
    )

    id_unidad_destino = models.IntegerField(
        db_column="id_unidad_destino"
    )

    factor_conversion = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        db_column="factor_conversion"
    )


    class Meta:
        managed = False
        db_table = '"maestros"."producto_conversion"'

        verbose_name = "Producto Conversión"
        verbose_name_plural = "Productos Conversiones"


    def __str__(self):
        return f"Producto {self.id_producto}"



# =====================================================
# ALMACEN
# =====================================================

class Almacen(models.Model):

    id_almacen = models.AutoField(
        primary_key=True,
        db_column="id_almacen"
    )

    codigo = models.CharField(
        max_length=20,
        db_column="codigo"
    )

    nombre = models.CharField(
        max_length=100,
        db_column="nombre"
    )

    referencia = models.CharField(
        max_length=150,
        db_column="referencia",
        null=True,
        blank=True
    )

    capacidad_pallets = models.IntegerField(
        db_column="capacidad_pallets"
    )

    estado = models.BooleanField(
        db_column="estado"
    )

    fecha_registro = models.DateTimeField(
        db_column="fecha_registro"
    )

    fecha_actualizacion = models.DateTimeField(
        db_column="fecha_actualizacion"
    )


    class Meta:
        managed = False
        db_table = '"maestros"."almacen"'

        verbose_name = "Almacén"
        verbose_name_plural = "Almacenes"


    def __str__(self):
        return self.nombre



# =====================================================
# ZONA
# =====================================================

class Zona(models.Model):

    id_zona = models.AutoField(
        primary_key=True,
        db_column="id_zona"
    )

    id_almacen = models.IntegerField(
        db_column="id_almacen"
    )

    codigo = models.CharField(
        max_length=20,
        db_column="codigo"
    )

    nombre = models.CharField(
        max_length=100,
        db_column="nombre"
    )

    tipo = models.CharField(
        max_length=50,
        db_column="tipo"
    )

    estado = models.BooleanField(
        db_column="estado"
    )

    fecha_registro = models.DateTimeField(
        db_column="fecha_registro"
    )

    fecha_actualizacion = models.DateTimeField(
        db_column="fecha_actualizacion"
    )


    class Meta:
        managed = False
        db_table = '"maestros"."zona"'

        verbose_name = "Zona"
        verbose_name_plural = "Zonas"


    def __str__(self):
        return self.nombre

# =====================================================
# UBICACION
# =====================================================

class Ubicacion(models.Model):

    id_ubicacion = models.AutoField(
        primary_key=True,
        db_column="id_ubicacion"
    )

    id_zona = models.IntegerField(
        db_column="id_zona"
    )

    codigo = models.CharField(
        max_length=50,
        db_column="codigo"
    )

    pasillo = models.CharField(
        max_length=10,
        db_column="pasillo"
    )

    rack = models.CharField(
        max_length=10,
        db_column="rack"
    )

    nivel = models.CharField(
        max_length=10,
        db_column="nivel"
    )

    columna = models.CharField(
        max_length=10,
        db_column="columna"
    )

    posicion = models.CharField(
        max_length=10,
        db_column="posicion"
    )

    capacidad_volumen = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        db_column="capacidad_volumen"
    )

    capacidad_peso = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        db_column="capacidad_peso"
    )

    estado = models.BooleanField(
        db_column="estado"
    )

    fecha_registro = models.DateTimeField(
        db_column="fecha_registro"
    )

    fecha_actualizacion = models.DateTimeField(
        db_column="fecha_actualizacion"
    )


    class Meta:
        managed = False
        db_table = '"maestros"."ubicacion"'

        verbose_name = "Ubicación"
        verbose_name_plural = "Ubicaciones"


    def __str__(self):
        return self.codigo



# =====================================================
# PALLET
# =====================================================

class Pallet(models.Model):

    id_pallet = models.AutoField(
        primary_key=True,
        db_column="id_pallet"
    )

    codigo_barras = models.CharField(
        max_length=255,
        db_column="codigo_barras"
    )

    tipo = models.CharField(
        max_length=255,
        db_column="tipo"
    )

    capacidad_referencial = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        db_column="capacidad_referencial"
    )

    id_pallet_padre = models.IntegerField(
        db_column="id_pallet_padre",
        null=True,
        blank=True
    )

    estado = models.BooleanField(
        db_column="estado"
    )

    fecha_registro = models.DateTimeField(
        db_column="fecha_registro"
    )

    fecha_actualizacion = models.DateTimeField(
        db_column="fecha_actualizacion"
    )


    class Meta:
        managed = False
        db_table = '"maestros"."pallet"'

        verbose_name = "Pallet"
        verbose_name_plural = "Pallets"


    def __str__(self):
        return self.codigo_barras
