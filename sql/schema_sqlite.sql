CREATE TABLE IF NOT EXISTS passenger_categories (
    passenger_count INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS trips (
    key TEXT PRIMARY KEY,
    fare_amount REAL,
    pickup_datetime TEXT,
    pickup_longitude REAL,
    pickup_latitude REAL,
    dropoff_longitude REAL,
    dropoff_latitude REAL,
    passenger_count INTEGER,
    FOREIGN KEY (passenger_count)
        REFERENCES passenger_categories(passenger_count)
);

CREATE INDEX IF NOT EXISTS idx_trips_pickup_datetime
ON trips(pickup_datetime);