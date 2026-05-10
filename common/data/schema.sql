-- Tabla principal de organizaciones (ej. Cruz Roja)
CREATE TABLE organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    website TEXT,
    global_phone TEXT
);

-- Tabla de sedes físicas (puntos en el mapa)
CREATE TABLE branches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER,
    city TEXT NOT NULL,
    address TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    opening_hours TEXT,
    local_phone TEXT,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

-- Catálogo de tipos de servicios
CREATE TABLE services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL, -- 'Legal', 'Salud', 'Alojamiento', 'Comida'
    name TEXT NOT NULL
);

-- Relación: Qué sede ofrece qué servicio y qué pide a cambio
CREATE TABLE branch_services (
    branch_id INTEGER,
    service_id INTEGER,
    requirements TEXT, -- 'Necesita empadronamiento', 'Solo con cita OAR'
    notes TEXT,
    PRIMARY KEY (branch_id, service_id),
    FOREIGN KEY (branch_id) REFERENCES branches(id),
    FOREIGN KEY (service_id) REFERENCES services(id)
);

-- Idiomas disponibles por sede (Crucial para el Guidance Agent)
CREATE TABLE languages_served (
    branch_id INTEGER,
    language_code TEXT, -- 'es', 'en', 'ar', 'fr'
    PRIMARY KEY (branch_id, language_code),
    FOREIGN KEY (branch_id) REFERENCES branches(id)
);