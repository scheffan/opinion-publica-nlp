-- Permisos del usuario de solo lectura que usa Grafana.
-- El usuario lo crea cargar_bd.py (con la contraseña del secreto GRAFANA_DB_PASSWORD).
-- Solo puede leer las vistas del tablero: no ve las tablas, no escribe, no crea nada.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'grafana_lector') THEN
    GRANT USAGE ON SCHEMA opinion TO grafana_lector;
    GRANT SELECT ON
      opinion.v_bsky_semanal_tema, opinion.v_bsky_mensual_tema, opinion.v_bsky_mensual_conteos,
      opinion.v_bsky_emociones_semanal, opinion.v_bsky_emociones_mensual,
      opinion.v_bsky_cobertura, opinion.v_bsky_resumen
    TO grafana_lector;
  END IF;
END $$;
