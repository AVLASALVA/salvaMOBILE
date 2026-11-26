-- ============================================================
-- 04_EXTENSION_VIBRACIONES_MOBILE.SQL
-- Extensión para Salva Mobile sobre la base de datos compartida
-- con S - Licencias (Supabase)
-- ============================================================
-- NOTA IMPORTANTE:
-- Este script es 100% compatible con el programa de mouse (S - Licencias).
-- NO modifica la tabla de operadores ni altera la lógica de autenticación existente.
-- Solo añade la tabla de vibraciones para la App Web y las columnas para el Bot de Telegram.
-- ============================================================

-- 1. TABLA DE VIBRACIONES (Para la App Web Móvil - PWA)
CREATE TABLE IF NOT EXISTS vibraciones (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    letra TEXT NOT NULL CHECK (letra IN ('A', 'B', 'C', 'D')),
    usuario TEXT NOT NULL,
    id_licencia TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices de rendimiento
CREATE INDEX IF NOT EXISTS idx_vibraciones_usuario ON vibraciones(usuario);
CREATE INDEX IF NOT EXISTS idx_vibraciones_timestamp ON vibraciones(timestamp DESC);

-- Seguridad RLS para vibraciones
ALTER TABLE vibraciones ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Cualquiera puede insertar vibraciones" ON vibraciones;
CREATE POLICY "Cualquiera puede insertar vibraciones"
    ON vibraciones FOR INSERT
    WITH CHECK (true);

DROP POLICY IF EXISTS "Cualquiera puede ver vibraciones" ON vibraciones;
CREATE POLICY "Cualquiera puede ver vibraciones"
    ON vibraciones FOR SELECT
    USING (true);

-- Habilitar Realtime para la tabla vibraciones (para que el móvil vibre al instante)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_publication_tables
        WHERE pubname = 'supabase_realtime'
        AND tablename = 'vibraciones'
    ) THEN
        ALTER PUBLICATION supabase_realtime ADD TABLE vibraciones;
    END IF;
END $$;

-- 2. CAMPOS DE TELEGRAM EN USUARIOS_APP (Para iPhone)
ALTER TABLE usuarios_app 
ADD COLUMN IF NOT EXISTS telegram_chat_id BIGINT,
ADD COLUMN IF NOT EXISTS telegram_username TEXT;

CREATE INDEX IF NOT EXISTS idx_usuarios_app_telegram_chat_id 
ON usuarios_app(telegram_chat_id);

-- 3. FUNCIÓN RPC PARA VINCULAR TELEGRAM
CREATE OR REPLACE FUNCTION vincular_telegram(
    p_usuario TEXT,
    p_chat_id BIGINT,
    p_telegram_user TEXT DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_usuario RECORD;
BEGIN
    SELECT * INTO v_usuario
    FROM usuarios_app
    WHERE LOWER(usuario) = LOWER(TRIM(p_usuario));

    IF NOT FOUND THEN
        RETURN jsonb_build_object(
            'exito', false,
            'mensaje', 'No se encontró ningún usuario con ese nombre en el sistema.'
        );
    END IF;

    UPDATE usuarios_app
    SET telegram_chat_id = p_chat_id,
        telegram_username = p_telegram_user,
        updated_at = NOW()
    WHERE id = v_usuario.id;

    RETURN jsonb_build_object(
        'exito', true,
        'mensaje', '¡iPhone vinculado correctamente!',
        'usuario', v_usuario.usuario
    );
END;
$$;

-- Permisos de ejecución
GRANT EXECUTE ON FUNCTION vincular_telegram(TEXT, BIGINT, TEXT) TO anon;
GRANT EXECUTE ON FUNCTION vincular_telegram(TEXT, BIGINT, TEXT) TO authenticated;
