-- Dashboard de Facturación
-- Esquema físico completo para SQLITE
-- Generado desde app/models.py. No editar manualmente.

-- ============================================================
-- TABLA: campanias
-- ============================================================
CREATE TABLE campanias (
	id INTEGER NOT NULL,
	cliente VARCHAR(100) NOT NULL,
	nombre VARCHAR(100) NOT NULL,
	activa BOOLEAN NOT NULL,
	creado_en DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_campanias_cliente_nombre UNIQUE (cliente, nombre)
);

-- ============================================================
-- TABLA: facturacion_anio
-- ============================================================
CREATE TABLE facturacion_anio (
	id INTEGER NOT NULL,
	fecha DATE NOT NULL,
	mes VARCHAR(20) NOT NULL,
	cliente VARCHAR(100) NOT NULL,
	gerente VARCHAR(100),
	jefe_site VARCHAR(100),
	campania VARCHAR(100),
	subcampania VARCHAR(100),
	tipo_negocio VARCHAR(100),
	tipo_jornada VARCHAR(50) NOT NULL,
	horas_objetivo NUMERIC(12, 2) NOT NULL,
	horas_facturadas NUMERIC(12, 2) NOT NULL,
	horas_penalizadas NUMERIC(12, 2),
	valor_hora_objetivo NUMERIC(18, 2),
	valor_hora NUMERIC(18, 2) NOT NULL,
	tarifacion NUMERIC(18, 2),
	importe_fijo NUMERIC(18, 2),
	variable_objetivo NUMERIC(18, 2),
	variable_productivo NUMERIC(18, 2),
	bonos NUMERIC(18, 2),
	penalizaciones NUMERIC(18, 2),
	netx_gen NUMERIC(18, 2),
	otros NUMERIC(18, 2),
	PRIMARY KEY (id)
);

-- ============================================================
-- TABLA: feriados_operativos
-- ============================================================
CREATE TABLE feriados_operativos (
	id INTEGER NOT NULL,
	year INTEGER NOT NULL,
	fecha DATE NOT NULL,
	nombre VARCHAR(160) NOT NULL,
	tipo VARCHAR(30) NOT NULL,
	activo BOOLEAN NOT NULL,
	creado_en DATETIME NOT NULL,
	actualizado_en DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_feriados_operativos_fecha UNIQUE (fecha)
);

CREATE INDEX ix_feriados_operativos_fecha ON feriados_operativos (fecha);

CREATE INDEX ix_feriados_operativos_year ON feriados_operativos (year);

-- ============================================================
-- TABLA: matriz_precios
-- ============================================================
CREATE TABLE matriz_precios (
	id INTEGER NOT NULL,
	site VARCHAR(100),
	cliente VARCHAR(100) NOT NULL,
	campania VARCHAR(100) NOT NULL,
	year INTEGER NOT NULL,
	mes VARCHAR(7) NOT NULL,
	precio_base NUMERIC(18, 2) NOT NULL,
	alcance_porcentaje NUMERIC(9, 4) NOT NULL,
	precio_final NUMERIC(18, 2) NOT NULL,
	importe_fijo_mensual NUMERIC(18, 2) NOT NULL,
	creado_en DATETIME NOT NULL,
	actualizado_en DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_matriz_precios_cliente_campania_mes UNIQUE (cliente, campania, mes)
);

CREATE INDEX ix_matriz_precios_mes ON matriz_precios (mes);

CREATE INDEX ix_matriz_precios_year ON matriz_precios (year);

-- ============================================================
-- TABLA: matriz_proyecciones
-- ============================================================
CREATE TABLE matriz_proyecciones (
	id INTEGER NOT NULL,
	cliente VARCHAR(100) NOT NULL,
	campania VARCHAR(100) NOT NULL,
	year INTEGER NOT NULL,
	mes VARCHAR(7) NOT NULL,
	dotacion_requerida NUMERIC(12, 2) NOT NULL,
	carga_semanal VARCHAR(20) NOT NULL,
	carga_horaria NUMERIC(12, 2) NOT NULL,
	dias_objetivo INTEGER NOT NULL,
	horas_requeridas NUMERIC(12, 2) NOT NULL,
	porcentaje_cumplimiento NUMERIC(9, 4) NOT NULL,
	tiene_nocturnidad BOOLEAN NOT NULL,
	porcentaje_nocturnidad NUMERIC(9, 4) NOT NULL,
	tipo_plp VARCHAR(30),
	horas_carga_manual BOOLEAN NOT NULL,
	dias_objetivo_manual INTEGER,
	horas_requeridas_manual NUMERIC(12, 2),
	creado_en DATETIME NOT NULL,
	actualizado_en DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_matriz_proyecciones_cliente_campania_mes UNIQUE (cliente, campania, mes)
);

CREATE INDEX ix_matriz_proyecciones_mes ON matriz_proyecciones (mes);

CREATE INDEX ix_matriz_proyecciones_year ON matriz_proyecciones (year);

-- ============================================================
-- TABLA: next_gen_dolar
-- ============================================================
CREATE TABLE next_gen_dolar (
	id INTEGER NOT NULL,
	year INTEGER NOT NULL,
	mes VARCHAR(7) NOT NULL,
	valor NUMERIC(18, 6) NOT NULL,
	creado_en DATETIME NOT NULL,
	actualizado_en DATETIME NOT NULL,
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_next_gen_dolar_mes ON next_gen_dolar (mes);

CREATE INDEX ix_next_gen_dolar_year ON next_gen_dolar (year);

-- ============================================================
-- TABLA: next_gen_productos
-- ============================================================
CREATE TABLE next_gen_productos (
	id INTEGER NOT NULL,
	site VARCHAR(100),
	cliente VARCHAR(100) NOT NULL,
	campania VARCHAR(100) NOT NULL,
	producto VARCHAR(160) NOT NULL,
	year INTEGER NOT NULL,
	mes VARCHAR(7) NOT NULL,
	cantidad_usd NUMERIC(18, 2) NOT NULL,
	creado_en DATETIME NOT NULL,
	actualizado_en DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_next_gen_producto_mes UNIQUE (cliente, campania, producto, mes)
);

CREATE INDEX ix_next_gen_productos_mes ON next_gen_productos (mes);

CREATE INDEX ix_next_gen_productos_year ON next_gen_productos (year);

-- ============================================================
-- TABLA: personal_distribucion_horas
-- ============================================================
CREATE TABLE personal_distribucion_horas (
	id INTEGER NOT NULL,
	servicio VARCHAR(100) NOT NULL,
	year INTEGER NOT NULL,
	mes VARCHAR(7) NOT NULL,
	porcentaje_diurno NUMERIC(9, 4) NOT NULL,
	creado_en DATETIME NOT NULL,
	actualizado_en DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_personal_distribucion_servicio_mes UNIQUE (servicio, mes)
);

CREATE INDEX ix_personal_distribucion_horas_mes ON personal_distribucion_horas (mes);

CREATE INDEX ix_personal_distribucion_horas_servicio ON personal_distribucion_horas (servicio);

CREATE INDEX ix_personal_distribucion_horas_year ON personal_distribucion_horas (year);

-- ============================================================
-- TABLA: sites_proyecciones
-- ============================================================
CREATE TABLE sites_proyecciones (
	id INTEGER NOT NULL,
	cliente VARCHAR(100) NOT NULL,
	campania VARCHAR(160) NOT NULL,
	site VARCHAR(100) NOT NULL,
	cliente_destino VARCHAR(100),
	campania_destino VARCHAR(160),
	creado_en DATETIME NOT NULL,
	actualizado_en DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_site_proyeccion_cliente_campania UNIQUE (cliente, campania)
);

-- ============================================================
-- TABLA: tarifaciones_campanias
-- ============================================================
CREATE TABLE tarifaciones_campanias (
	id INTEGER NOT NULL,
	site VARCHAR(100),
	cliente VARCHAR(100) NOT NULL,
	campania VARCHAR(100) NOT NULL,
	concepto VARCHAR(100) NOT NULL,
	year INTEGER NOT NULL,
	mes VARCHAR(7) NOT NULL,
	monto NUMERIC(18, 2) NOT NULL,
	creado_en DATETIME NOT NULL,
	actualizado_en DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_tarifacion_campania_concepto_mes UNIQUE (cliente, campania, concepto, mes)
);

CREATE INDEX ix_tarifaciones_campanias_mes ON tarifaciones_campanias (mes);

CREATE INDEX ix_tarifaciones_campanias_year ON tarifaciones_campanias (year);

-- ============================================================
-- TABLA: usuarios
-- ============================================================
CREATE TABLE usuarios (
	id INTEGER NOT NULL,
	nombre VARCHAR(120) NOT NULL,
	email VARCHAR(160) NOT NULL,
	password_hash VARCHAR(255) NOT NULL,
	rol VARCHAR(30) NOT NULL,
	activo BOOLEAN NOT NULL,
	creado_en DATETIME NOT NULL,
	actualizado_en DATETIME NOT NULL,
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_usuarios_email ON usuarios (email);

-- ============================================================
-- TABLA: variables_campanias
-- ============================================================
CREATE TABLE variables_campanias (
	id INTEGER NOT NULL,
	site VARCHAR(100),
	cliente VARCHAR(100) NOT NULL,
	campania VARCHAR(100) NOT NULL,
	year INTEGER NOT NULL,
	mes VARCHAR(7) NOT NULL,
	porcentaje NUMERIC(9, 4) NOT NULL,
	creado_en DATETIME NOT NULL,
	actualizado_en DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_variables_cliente_campania_mes UNIQUE (cliente, campania, mes)
);

CREATE INDEX ix_variables_campanias_mes ON variables_campanias (mes);

CREATE INDEX ix_variables_campanias_year ON variables_campanias (year);

-- ============================================================
-- TABLA: asignaciones_comerciales
-- ============================================================
CREATE TABLE asignaciones_comerciales (
	id INTEGER NOT NULL,
	campania_id INTEGER NOT NULL,
	cliente VARCHAR(100) NOT NULL,
	gerente VARCHAR(100) NOT NULL,
	jefe_site VARCHAR(100) NOT NULL,
	campania VARCHAR(100) NOT NULL,
	subcampania VARCHAR(100) NOT NULL,
	tipo_negocio VARCHAR(100),
	activa BOOLEAN NOT NULL,
	creado_en DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT fk_asignaciones_campania FOREIGN KEY(campania_id) REFERENCES campanias (id)
);

CREATE INDEX ix_asignaciones_comerciales_campania_id ON asignaciones_comerciales (campania_id);

-- ============================================================
-- TABLA: historial_cambios
-- ============================================================
CREATE TABLE historial_cambios (
	id INTEGER NOT NULL,
	usuario_id INTEGER,
	usuario_nombre VARCHAR(120),
	usuario_email VARCHAR(160),
	accion VARCHAR(30) NOT NULL,
	entidad VARCHAR(80) NOT NULL,
	entidad_id VARCHAR(50),
	resumen VARCHAR(255) NOT NULL,
	detalle TEXT,
	antes TEXT,
	despues TEXT,
	creado_en DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id)
);

CREATE INDEX ix_historial_cambios_creado_en ON historial_cambios (creado_en);

-- ============================================================
-- TABLA: justificaciones_ajustes
-- ============================================================
CREATE TABLE justificaciones_ajustes (
	id INTEGER NOT NULL,
	facturacion_id INTEGER NOT NULL,
	tipo VARCHAR(30) NOT NULL,
	cantidad NUMERIC(18, 4),
	precio NUMERIC(18, 2),
	importe NUMERIC(18, 2) NOT NULL,
	descripcion TEXT NOT NULL,
	creado_en DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(facturacion_id) REFERENCES facturacion_anio (id)
);

-- ============================================================
-- TABLA: matriz_proyecciones_jornadas
-- ============================================================
CREATE TABLE matriz_proyecciones_jornadas (
	id INTEGER NOT NULL,
	proyeccion_id INTEGER NOT NULL,
	dotacion_requerida NUMERIC(12, 2) NOT NULL,
	carga_semanal VARCHAR(30) NOT NULL,
	carga_horaria NUMERIC(12, 2) NOT NULL,
	dias_objetivo INTEGER NOT NULL,
	horas_requeridas NUMERIC(12, 2) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(proyeccion_id) REFERENCES matriz_proyecciones (id)
);

CREATE INDEX ix_matriz_proyecciones_jornadas_proyeccion_id ON matriz_proyecciones_jornadas (proyeccion_id);
