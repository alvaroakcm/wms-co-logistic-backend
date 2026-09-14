from django.db import migrations


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE maestros.ubicacion
                    ADD COLUMN IF NOT EXISTS rack varchar(10) NOT NULL DEFAULT '',
                    ADD COLUMN IF NOT EXISTS posicion varchar(10) NOT NULL DEFAULT '';
                ALTER TABLE maestros.ubicacion ALTER COLUMN rack DROP DEFAULT;
                ALTER TABLE maestros.ubicacion ALTER COLUMN posicion DROP DEFAULT;
            """,
            reverse_sql="""
                ALTER TABLE maestros.ubicacion DROP COLUMN IF EXISTS posicion;
                ALTER TABLE maestros.ubicacion DROP COLUMN IF EXISTS rack;
            """,
        )
    ]
