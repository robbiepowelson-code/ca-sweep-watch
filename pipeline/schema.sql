-- ca-sweep-watch tracking database (SQLite)
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS agencies (
    id INTEGER PRIMARY KEY,
    agency_name TEXT UNIQUE NOT NULL,
    jurisdiction_type TEXT CHECK (jurisdiction_type IN ('city','county','state')),
    county TEXT,
    cpra_email TEXT,
    cpra_portal_url TEXT,
    pd_records_email TEXT,
    lat REAL, lon REAL,              -- city hall / county seat, for map fallback
    notes TEXT
);

CREATE TABLE IF NOT EXISTS ordinances (
    id INTEGER PRIMARY KEY,
    agency_id INTEGER REFERENCES agencies(id),
    code_section TEXT NOT NULL,
    ordinance_name TEXT,
    category TEXT,                    -- camping, lodging, sit-lie, vehicle, property storage...
    summary TEXT,
    status TEXT,
    date_enacted TEXT,
    penalty TEXT,
    source TEXT,
    verification_status TEXT,
    UNIQUE (agency_id, code_section)
);

CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY,
    agency_id INTEGER NOT NULL REFERENCES agencies(id),
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    sent_date TEXT,
    method TEXT,                      -- email, portal, mail
    determination_due TEXT,           -- sent_date + 10 days (Gov C 7922.535)
    extension_claimed INTEGER DEFAULT 0,
    extended_due TEXT,                -- + 14 days if extension invoked
    status TEXT DEFAULT 'draft'       -- draft, sent, acknowledged, extended,
                                      -- partial_production, complete, denied,
                                      -- overdue, escalated, litigation
        CHECK (status IN ('draft','sent','acknowledged','extended',
                          'partial_production','complete','denied',
                          'overdue','escalated','litigation')),
    tracking_ref TEXT,                -- portal reference number
    notes TEXT
);

CREATE TABLE IF NOT EXISTS request_events (
    id INTEGER PRIMARY KEY,
    request_id INTEGER NOT NULL REFERENCES requests(id),
    event_date TEXT NOT NULL,
    event_type TEXT,                  -- sent, ack, extension, production, denial, followup, escalation
    detail TEXT
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    request_id INTEGER REFERENCES requests(id),
    agency_id INTEGER REFERENCES agencies(id),
    file_path TEXT UNIQUE NOT NULL,
    sha256 TEXT,
    file_type TEXT,
    received_date TEXT,
    ocr_done INTEGER DEFAULT 0,
    extracted_text TEXT,
    exif_lat REAL, exif_lon REAL, exif_timestamp TEXT,
    summary TEXT,
    processed INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS enforcement_actions (
    id INTEGER PRIMARY KEY,
    agency_id INTEGER REFERENCES agencies(id),
    document_id INTEGER REFERENCES documents(id),
    action_type TEXT,                 -- citation, arrest, sweep, property_removal, notice
    code_section TEXT,
    action_date TEXT,
    location_text TEXT,
    lat REAL, lon REAL,
    geocode_source TEXT,              -- exif, report_text, gis_file, geocoded_address, agency_centroid
    people_affected INTEGER,
    property_destroyed INTEGER,       -- boolean-ish
    summary TEXT,
    confidence TEXT DEFAULT 'low'     -- low/medium/high (extraction confidence)
);

-- Map export view: one row per plottable event
CREATE VIEW IF NOT EXISTS v_map_events AS
SELECT ea.id, a.agency_name, a.county, ea.action_type, ea.code_section,
       ea.action_date, ea.summary,
       COALESCE(ea.lat, a.lat) AS lat,
       COALESCE(ea.lon, a.lon) AS lon,
       ea.geocode_source, ea.confidence
FROM enforcement_actions ea
JOIN agencies a ON a.id = ea.agency_id
WHERE COALESCE(ea.lat, a.lat) IS NOT NULL;

-- Compliance view for the accountability layer of the map
CREATE VIEW IF NOT EXISTS v_agency_compliance AS
SELECT a.id, a.agency_name, a.county, a.jurisdiction_type, a.lat, a.lon,
       COUNT(r.id)                                            AS requests_sent,
       SUM(CASE WHEN r.status IN ('complete','partial_production') THEN 1 ELSE 0 END) AS produced,
       SUM(CASE WHEN r.status IN ('overdue','escalated') THEN 1 ELSE 0 END)           AS overdue,
       SUM(CASE WHEN r.status = 'denied' THEN 1 ELSE 0 END)   AS denied
FROM agencies a LEFT JOIN requests r ON r.agency_id = a.id
GROUP BY a.id;
