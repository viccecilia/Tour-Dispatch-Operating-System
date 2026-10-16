-- Driver continuous M1: preserve separate pickup/dropoff odometer facts for provisional work.
-- Additive only; legacy odometer_km remains readable and is not rewritten.

ALTER TABLE driver_provisional_tasks ADD COLUMN pickup_odometer_km REAL;
ALTER TABLE driver_provisional_tasks ADD COLUMN dropoff_odometer_km REAL;
