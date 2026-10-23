-- PostgreSQL schema for taxi dataset
-- Database: taxi_db

-- Справочник категорий пассажиров
CREATE TABLE IF NOT EXISTS public.passenger_categories (
    passenger_count INTEGER PRIMARY KEY,
    category_name TEXT NOT NULL
);

-- Основная таблица поездок
CREATE TABLE IF NOT EXISTS public.trips (
    key TEXT PRIMARY KEY,
    fare_amount DOUBLE PRECISION,
    pickup_datetime TIMESTAMP,
    pickup_longitude DOUBLE PRECISION,
    pickup_latitude DOUBLE PRECISION,
    dropoff_longitude DOUBLE PRECISION,
    dropoff_latitude DOUBLE PRECISION,
    passenger_count INTEGER,
    CONSTRAINT fk_trips_passenger_category
        FOREIGN KEY (passenger_count)
        REFERENCES public.passenger_categories (passenger_count)
);

-- Индекс для запросов по дате поездки
CREATE INDEX IF NOT EXISTS idx_trips_pickup_datetime
    ON public.trips (pickup_datetime);