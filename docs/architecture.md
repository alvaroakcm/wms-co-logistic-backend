# Arquitectura de seguridad

```text
React SPA -> Supabase Auth -> access token JWT
React SPA -> Django REST API -> Supabase PostgreSQL
                |
                +-> valida JWT con JWKS
                +-> verifica usuario activo
                +-> calcula roles y permisos
                +-> aplica reglas del WMS
```

## Responsabilidades

- Supabase Auth es la fuente de identidad y administra credenciales y sesiones.
- Django es la fuente de autorización y de todas las reglas de negocio.
- PostgreSQL almacena el perfil, roles, permisos y datos logísticos.
- React no contiene secretos ni decide si una operación está autorizada.

Los permisos mostrados en el frontend son informativos. Cada endpoint de
Django debe volver a comprobar la autorización correspondiente.

Las operaciones administrativas de identidad usan `SUPABASE_SECRET_KEY`
únicamente desde Django. La llave privilegiada nunca se envía al navegador.
Registro y edición aplican compensación entre Supabase Auth y PostgreSQL para
reducir el riesgo de identidades o perfiles desincronizados.
