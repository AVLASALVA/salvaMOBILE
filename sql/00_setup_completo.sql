-- ============================================================
-- SCRIPT DE CONFIGURACIÓN COMPLETO PARA SUPABASE
-- Sistema de Licencias - Asistente de Automatización
-- ============================================================

-- 1. TABLA DE OPERADORES (ADMINISTRADORES)
CREATE TABLE IF NOT EXISTS operadores (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. TABLA DE USUARIOS / LICENCIAS
CREATE TABLE IF NOT EXISTS usuarios_app (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    usuario TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    plan TEXT DEFAULT 'Horario semanal',
    fecha_expiracion TIMESTAMP WITH TIME ZONE NOT NULL,
    horario_activacion JSONB DEFAULT '{}',
    estado TEXT DEFAULT 'activo' CHECK (estado IN ('activo', 'inactivo')),
    device_id TEXT,
    ultimo_latido TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. ÍNDICES DE RENDIMIENTO
CREATE INDEX IF NOT EXISTS idx_usuarios_app_usuario ON usuarios_app(usuario);
CREATE INDEX IF NOT EXISTS idx_usuarios_app_estado ON usuarios_app(estado);
CREATE INDEX IF NOT EXISTS idx_usuarios_app_expiracion ON usuarios_app(fecha_expiracion);

-- 4. FUNCIÓN RPC: AUTENTICAR Y VALIDAR LICENCIA
CREATE OR REPLACE FUNCTION autenticar_usuario_app(
    p_usuario TEXT,
    p_password TEXT,
    p_device_id TEXT DEFAULT NULL,
    p_origen TEXT DEFAULT 'desktop'
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_usuario RECORD;
    v_tiempo_local TIMESTAMP;
    v_hora_local INTEGER;
    v_minuto_local INTEGER;
    v_minutos_actual INTEGER;
    v_dia_semana INTEGER;
    v_dia_actual TEXT;
    v_licencia_vigente BOOLEAN := true;
    v_en_horario BOOLEAN := true;
    v_puede_ejecutar BOOLEAN := false;
    v_estado_licencia TEXT := 'activo';
    v_mensaje_estado TEXT := 'Licencia activa y lista para usar.';
    v_clase JSONB;
    v_hora_ini_str TEXT;
    v_hora_fin_str TEXT;
    v_ini_h INTEGER;
    v_ini_m INTEGER;
    v_fin_h INTEGER;
    v_fin_m INTEGER;
    v_ini_total_min INTEGER;
    v_fin_total_min INTEGER;
    v_rango_inicio INTEGER;
    v_rango_fin INTEGER;
    v_coincide_horario BOOLEAN := false;
    v_tiene_materias BOOLEAN := false;
    v_dia_key TEXT;
BEGIN
    -- 1. Buscar usuario por credenciales (insensible a mayúsculas en el usuario)
    SELECT * INTO v_usuario
    FROM usuarios_app
    WHERE LOWER(usuario) = LOWER(p_usuario)
      AND password = p_password;

    -- Si las credenciales no coinciden, se rechaza
    IF NOT FOUND THEN
        RETURN jsonb_build_object(
            'exito', false,
            'mensaje', 'Credenciales inválidas. Verifica tu usuario y contraseña.'
        );
    END IF;

    -- 2. CONTROL DE CONCURRENCIA (NO 2 COMPUTADORES A LA VEZ)
    IF p_device_id IS NOT NULL THEN
        IF v_usuario.device_id IS NOT NULL 
           AND v_usuario.device_id != p_device_id 
           AND v_usuario.ultimo_latido IS NOT NULL 
           AND (NOW() - v_usuario.ultimo_latido) < INTERVAL '60 seconds'
        THEN
            RETURN jsonb_build_object(
                'exito', false,
                'puede_ejecutar', false,
                'mensaje', 'Esta cuenta está en uso en otro computador en este momento. No se permite el uso simultáneo.'
            );
        ELSE
            UPDATE usuarios_app
            SET device_id = p_device_id,
                ultimo_latido = NOW(),
                updated_at = NOW()
            WHERE id = v_usuario.id;
        END IF;
    END IF;

    -- 3. Verificar expiración global
    IF v_usuario.fecha_expiracion < NOW() THEN
        v_licencia_vigente := false;
        v_estado_licencia := 'licencia_expirada';
        v_mensaje_estado := 'Tu tiempo de licencia ha terminado.';
    END IF;

    -- 4. Verificar estado manual (pausa por admin)
    IF v_usuario.estado != 'activo' THEN
        v_estado_licencia := 'cuenta_inactiva';
        v_mensaje_estado := 'Tu cuenta se encuentra pausada o inactiva por el administrador.';
    END IF;

    -- 5. VERIFICACIÓN ESTRICTA DE HORARIOS (CORRECCIÓN DE BUG)
    -- Si NO es una prueba de 15 minutos, EXIGE tener materias configuradas
    IF v_usuario.plan NOT ILIKE '%minuto%' THEN
        IF v_usuario.horario_activacion IS NULL
           OR jsonb_typeof(v_usuario.horario_activacion) != 'object'
           OR v_usuario.horario_activacion = '{}'::jsonb
        THEN
            v_en_horario := false;
            v_estado_licencia := 'sin_horario';
            v_mensaje_estado := 'Esta licencia de horario semanal no tiene materias asignadas.';
        ELSE
            v_tiene_materias := false;
            FOR v_dia_key IN SELECT jsonb_object_keys(v_usuario.horario_activacion)
            LOOP
                IF jsonb_typeof(v_usuario.horario_activacion -> v_dia_key) = 'array'
                   AND jsonb_array_length(v_usuario.horario_activacion -> v_dia_key) > 0
                THEN
                    v_tiene_materias := true;
                    EXIT;
                END IF;
            END LOOP;

            IF NOT v_tiene_materias THEN
                v_en_horario := false;
                v_estado_licencia := 'sin_horario';
                v_mensaje_estado := 'Esta licencia no tiene materias programadas en ningún día.';
            END IF;
        END IF;
    END IF;

    -- 6. Si tiene materias válidas, verificar si está en la ventana de clase de hoy (-5 min / +15 min)
    IF v_en_horario AND v_usuario.plan NOT ILIKE '%minuto%' THEN
        v_tiempo_local := NOW() AT TIME ZONE 'America/Bogota';
        v_hora_local := EXTRACT(HOUR FROM v_tiempo_local)::INTEGER;
        v_minuto_local := EXTRACT(MINUTE FROM v_tiempo_local)::INTEGER;
        v_minutos_actual := (v_hora_local * 60) + v_minuto_local;

        v_dia_semana := EXTRACT(ISODOW FROM v_tiempo_local)::INTEGER;
        v_dia_actual := CASE v_dia_semana
            WHEN 1 THEN 'lunes'
            WHEN 2 THEN 'martes'
            WHEN 3 THEN 'miércoles'
            WHEN 4 THEN 'jueves'
            WHEN 5 THEN 'viernes'
            WHEN 6 THEN 'sábado'
            WHEN 7 THEN 'domingo'
        END;

        IF v_usuario.horario_activacion ? v_dia_actual 
           AND jsonb_array_length(v_usuario.horario_activacion -> v_dia_actual) > 0 
        THEN
            v_coincide_horario := false;
            FOR v_clase IN SELECT * FROM jsonb_array_elements(v_usuario.horario_activacion -> v_dia_actual)
            LOOP
                v_hora_ini_str := TRIM(SPLIT_PART(v_clase ->> 'hora', '-', 1));
                v_hora_fin_str := TRIM(SPLIT_PART(v_clase ->> 'hora', '-', 2));

                IF v_hora_ini_str != '' AND v_hora_fin_str != '' THEN
                    v_ini_h := SPLIT_PART(v_hora_ini_str, ':', 1)::INTEGER;
                    v_ini_m := SPLIT_PART(v_hora_ini_str, ':', 2)::INTEGER;
                    v_fin_h := SPLIT_PART(v_hora_fin_str, ':', 1)::INTEGER;
                    v_fin_m := SPLIT_PART(v_hora_fin_str, ':', 2)::INTEGER;

                    v_ini_total_min := (v_ini_h * 60) + v_ini_m;
                    v_fin_total_min := (v_fin_h * 60) + v_fin_m;

                    IF v_fin_total_min <= v_ini_total_min THEN
                        v_fin_total_min := v_fin_total_min + 1440;
                    END IF;

                    v_rango_inicio := v_ini_total_min - 5;
                    v_rango_fin := v_fin_total_min + 15;

                    IF v_minutos_actual >= v_rango_inicio AND v_minutos_actual <= v_rango_fin THEN
                        v_coincide_horario := true;
                        EXIT;
                    END IF;
                END IF;
            END LOOP;

            IF NOT v_coincide_horario THEN
                v_en_horario := false;
                IF v_estado_licencia = 'activo' THEN
                    v_estado_licencia := 'fuera_de_horario';
                    v_mensaje_estado := 'Fuera de horario de examen. Disponible 5 min antes y hasta 15 min después.';
                END IF;
            END IF;
        ELSE
            v_en_horario := false;
            IF v_estado_licencia = 'activo' THEN
                v_estado_licencia := 'sin_clases_hoy';
                v_mensaje_estado := 'No tienes horarios o clases programadas para hoy (' || v_dia_actual || ').';
            END IF;
        END IF;
    END IF;

    -- 7. Determinar permiso efectivo
    IF v_usuario.estado = 'activo' AND v_licencia_vigente AND v_en_horario THEN
        v_puede_ejecutar := true;
        v_estado_licencia := 'activo';
        v_mensaje_estado := 'Licencia activa y autorizada.';
    ELSE
        v_puede_ejecutar := false;
    END IF;

    -- 8. Respuesta
    RETURN jsonb_build_object(
        'exito', true,
        'mensaje', 'Inicio de sesión exitoso',
        'usuario', v_usuario.usuario,
        'plan', v_usuario.plan,
        'fecha_expiracion', v_usuario.fecha_expiracion,
        'estado', v_usuario.estado,
        'horario_activacion', v_usuario.horario_activacion,
        'puede_ejecutar', v_puede_ejecutar,
        'estado_licencia', v_estado_licencia,
        'mensaje_estado', v_mensaje_estado,
        'licencia_vigente', v_licencia_vigente,
        'en_horario', v_en_horario
    );
END;
$$;

-- 5. FUNCIÓN PARA LIBERAR SESIÓN
CREATE OR REPLACE FUNCTION cerrar_sesion_app(
    p_usuario TEXT,
    p_device_id TEXT DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    UPDATE usuarios_app
    SET ultimo_latido = NULL
    WHERE LOWER(usuario) = LOWER(p_usuario);

    RETURN jsonb_build_object('exito', true, 'mensaje', 'Sesión liberada');
END;
$$;

-- 6. POLÍTICAS DE SEGURIDAD (RLS)
ALTER TABLE operadores ENABLE ROW LEVEL SECURITY;
ALTER TABLE usuarios_app ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Permitir lectura operadores" ON operadores;
CREATE POLICY "Permitir lectura operadores" ON operadores
    FOR SELECT USING (true);

DROP POLICY IF EXISTS "Operadores gestionan usuarios" ON usuarios_app;
CREATE POLICY "Operadores gestionan usuarios" ON usuarios_app
    FOR ALL TO authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Cualquiera puede autenticarse" ON usuarios_app;
CREATE POLICY "Cualquiera puede autenticarse"
    ON usuarios_app FOR SELECT
    USING (true);

DROP POLICY IF EXISTS "Actualizar device_id en autenticacion" ON usuarios_app;
CREATE POLICY "Actualizar device_id en autenticacion"
    ON usuarios_app FOR UPDATE
    USING (true)
    WITH CHECK (true);

GRANT EXECUTE ON FUNCTION autenticar_usuario_app(TEXT, TEXT, TEXT, TEXT) TO anon;
GRANT EXECUTE ON FUNCTION autenticar_usuario_app(TEXT, TEXT, TEXT, TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION cerrar_sesion_app(TEXT, TEXT) TO anon;
GRANT EXECUTE ON FUNCTION cerrar_sesion_app(TEXT, TEXT) TO authenticated;
