
-- Esquema Operacional - Supply Chain Dashboard MVP


DROP TABLE IF EXISTS movimientos_inventario, envios, detalle_orden_compra,
    ordenes_compra, productos, almacenes, proveedores CASCADE;

CREATE TABLE proveedores (
    proveedor_id   SERIAL PRIMARY KEY,
    nombre         VARCHAR(150) NOT NULL,
    pais           VARCHAR(80),
    calificacion   NUMERIC(3,2) DEFAULT 0
);

CREATE TABLE productos (
    producto_id    SERIAL PRIMARY KEY,
    sku            VARCHAR(50) UNIQUE NOT NULL,
    nombre         VARCHAR(150) NOT NULL,
    categoria      VARCHAR(80),
    costo_unitario NUMERIC(12,2)
);

CREATE TABLE almacenes (
    almacen_id     SERIAL PRIMARY KEY,
    nombre         VARCHAR(100) NOT NULL,
    ubicacion      VARCHAR(150)
);

CREATE TABLE ordenes_compra (
    orden_id             SERIAL PRIMARY KEY,
    proveedor_id         INT REFERENCES proveedores(proveedor_id),
    fecha_orden          TIMESTAMP NOT NULL,
    fecha_entrega_estim  TIMESTAMP,
    fecha_entrega_real   TIMESTAMP,
    estatus              VARCHAR(30) DEFAULT 'PENDIENTE',
    monto_total          NUMERIC(14,2)
);

CREATE TABLE detalle_orden_compra (
    detalle_id       SERIAL PRIMARY KEY,
    orden_id         INT REFERENCES ordenes_compra(orden_id),
    producto_id      INT REFERENCES productos(producto_id),
    cantidad         NUMERIC(12,2),
    precio_unitario  NUMERIC(12,2)
);

CREATE TABLE envios (
    envio_id            SERIAL PRIMARY KEY,
    orden_id            INT REFERENCES ordenes_compra(orden_id),
    proveedor_id        INT REFERENCES proveedores(proveedor_id),
    fecha_salida        TIMESTAMP,
    fecha_llegada_estim TIMESTAMP,
    fecha_llegada_real  TIMESTAMP,
    costo_flete         NUMERIC(12,2)
);

CREATE TABLE movimientos_inventario (
    movimiento_id    SERIAL PRIMARY KEY,
    almacen_id       INT REFERENCES almacenes(almacen_id),
    producto_id      INT REFERENCES productos(producto_id),
    tipo_movimiento  VARCHAR(20) CHECK (tipo_movimiento IN ('ENTRADA','SALIDA')),
    cantidad         NUMERIC(12,2),
    fecha            TIMESTAMP DEFAULT NOW()
);

-- Datos semilla (empresa, simulados)

INSERT INTO proveedores (nombre, pais, calificacion) VALUES
('Global Parts Supply', 'México', 4.50),
('NorthStar Logistics', 'Estados Unidos', 4.10),
('EastAsia Components', 'China', 3.80);

INSERT INTO productos (sku, nombre, categoria, costo_unitario) VALUES
('SKU-001', 'Sensor Industrial A1', 'Electrónica', 125.50),
('SKU-002', 'Motor Eléctrico 2HP', 'Maquinaria', 890.00),
('SKU-003', 'Caja de Empaque Reforzada', 'Empaque', 12.75);

INSERT INTO almacenes (nombre, ubicacion) VALUES
('Almacén Central', 'Ciudad de México'),
('Almacén Norte', 'Monterrey');

INSERT INTO ordenes_compra (proveedor_id, fecha_orden, fecha_entrega_estim, fecha_entrega_real, estatus, monto_total) VALUES
(1, '2026-08-01', '2026-08-10', '2026-08-09', 'ENTREGADA', 5500.00),
(2, '2026-08-05', '2026-08-15', '2026-08-18', 'ENTREGADA', 12300.00),
(3, '2026-08-10', '2026-08-25', NULL, 'PENDIENTE', 3200.00);

INSERT INTO detalle_orden_compra (orden_id, producto_id, cantidad, precio_unitario) VALUES
(1, 1, 40, 125.50),
(2, 2, 12, 890.00),
(3, 3, 250, 12.75);

INSERT INTO envios (orden_id, proveedor_id, fecha_salida, fecha_llegada_estim, fecha_llegada_real, costo_flete) VALUES
(1, 1, '2026-08-06', '2026-08-10', '2026-08-09', 350.00),
(2, 2, '2026-08-12', '2026-08-15', '2026-08-18', 620.00);

INSERT INTO movimientos_inventario (almacen_id, producto_id, tipo_movimiento, cantidad) VALUES
(1, 1, 'ENTRADA', 40),
(1, 1, 'SALIDA', 15),
(2, 2, 'ENTRADA', 12);