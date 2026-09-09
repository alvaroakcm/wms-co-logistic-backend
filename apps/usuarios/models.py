from django.db import models


class Usuario(models.Model):

    id_usuario = models.UUIDField(
        primary_key=True,
        db_column="id_usuario"
    )

    nombre = models.CharField(
        max_length=255,
        db_column="nombre"
    )

    apellido = models.CharField(
        max_length=255,
        db_column="apellido"
    )

    correo = models.EmailField(
        db_column="correo"
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

        # PostgreSQL schema.tabla
        db_table = '"usuarios"."usuario"'

        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"


    def __str__(self):
        return self.correo

class Rol(models.Model):

    id_rol = models.AutoField(
        primary_key=True,
        db_column="id_rol"
    )

    nombre = models.CharField(
        max_length=255,
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
        db_table = '"usuarios"."rol"'

        verbose_name = "Rol"
        verbose_name_plural = "Roles"


    def __str__(self):
        return self.nombre

class Permiso(models.Model):

    id_permiso = models.AutoField(
        primary_key=True,
        db_column="id_permiso"
    )

    nombre = models.CharField(
        max_length=255,
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
        db_table = '"usuarios"."permiso"'

        verbose_name = "Permiso"
        verbose_name_plural = "Permisos"


    def __str__(self):
        return self.nombre

class UsuarioRol(models.Model):

    id_usuario_rol = models.AutoField(
        primary_key=True,
        db_column="id_usuario_rol"
    )

    id_usuario = models.UUIDField(
        db_column="id_usuario"
    )

    id_rol = models.IntegerField(
        db_column="id_rol"
    )


    class Meta:
        managed = False
        db_table = '"usuarios"."usuario_rol"'

        verbose_name = "Usuario Rol"
        verbose_name_plural = "Usuarios Roles"


    def __str__(self):
        return f"{self.id_usuario} - {self.id_rol}"

class RolPermiso(models.Model):

    id_rol_permiso = models.AutoField(
        primary_key=True,
        db_column="id_rol_permiso"
    )

    id_rol = models.IntegerField(
        db_column="id_rol"
    )

    id_permiso = models.IntegerField(
        db_column="id_permiso"
    )


    class Meta:
        managed = False
        db_table = '"usuarios"."rol_permiso"'

        verbose_name = "Rol Permiso"
        verbose_name_plural = "Roles Permisos"


    def __str__(self):
        return f"Rol {self.id_rol} - Permiso {self.id_permiso}"