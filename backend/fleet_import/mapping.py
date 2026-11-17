"""Where each column of the company data template is stored.

"app.Model.field" for a direct copy. The Day 5 import follows this map; the
Day 3 acceptance test proves every column has a real home in the schema.
"""

TEMPLATE_TO_MODEL: dict[str, dict[str, str]] = {
    "vehicles": {
        "plate": "fleet.Vehicle.plate",
        "brand": "fleet.Vehicle.brand",
        "model": "fleet.Vehicle.model",
        "year": "fleet.Vehicle.year",
        "vin": "fleet.Vehicle.vin",
        "odometer_km": "fleet.Vehicle.odometer_km",
        "fuel_type": "fleet.Vehicle.fuel_type",
        "second_fuel_type": "fleet.Vehicle.second_fuel_type",
        "fuel_norm": "fleet.Vehicle.fuel_norm",
        "second_fuel_norm": "fleet.Vehicle.second_fuel_norm",
        "notes": "fleet.Vehicle.notes",
    },
    "drivers": {
        "full_name": "fleet.Driver.full_name",
        "phone": "fleet.Driver.phone",
        "licence_number": "fleet.Driver.licence_number",
        "licence_categories": "fleet.Driver.licence_categories",
        "licence_expiry": "fleet.Driver.licence_expiry",
        "default_plate": "fleet.Driver.default_vehicle",
    },
    "last_service": {
        "plate": "maintenance.ServiceRecord.vehicle",
        "service": "maintenance.ServiceRecord.service",
        "date": "maintenance.ServiceRecord.done_on",
        "odometer_km": "maintenance.ServiceRecord.odometer_km",
        "notes": "maintenance.ServiceRecord.notes",
    },
    "service_intervals": {
        "model": "maintenance.ServiceInterval.vehicle_model",
        "service": "maintenance.ServiceInterval.service",
        "interval_km": "maintenance.ServiceInterval.interval_km",
        "interval_months": "maintenance.ServiceInterval.interval_months",
    },
    "documents": {
        "owner_type": "documents.Document.doc_type",  # decides vehicle vs driver
        "owner": "documents.Document.vehicle",  # or .driver
        "document_type": "documents.Document.doc_type",
        "number": "documents.Document.number",
        "expiry_date": "documents.Document.expires_on",
    },
    "store_opening": {
        "item": "store.StoreItem.name",
        "category": "store.StoreItem.category",
        "unit": "store.StoreItem.unit",
        "min_level": "store.StoreItem.min_level",
        "quantity": "store.StockMovement.quantity",  # kind=opening
        "supplier": "store.StockMovement.supplier",
        "unit_price_uzs": "store.StockMovement.unit_price_uzs",
        "warranty_months": "store.StockMovement.warranty_until",  # today + months
    },
    "geofences": {
        "name": "tracking.Geofence.name",
        "place_type": "tracking.Geofence.kind",
        "address": "tracking.Geofence.address",
        "latitude": "tracking.Geofence.center",
        "longitude": "tracking.Geofence.center",
        "radius_m": "tracking.Geofence.radius_m",
    },
    "approvers": {
        "full_name": "accounts.User.first_name",  # split into first/last
        "phone": "accounts.User.phone",
        "role": "accounts.User.role",
        "daily_data": "accounts.User.approves_daily",
        "fuel": "accounts.User.approves_fuel",
        "service": "accounts.User.approves_service",
        "parts": "accounts.User.approves_parts",
    },
    "settings": {
        "work_start": "core.CompanySettings.work_start",
        "work_end": "core.CompanySettings.work_end",
        "work_days": "core.CompanySettings.work_days",
        "speed_limit_city": "core.CompanySettings.speed_limit_city_kmh",
        "speed_limit_highway": "core.CompanySettings.speed_limit_highway_kmh",
        "retention_months": "core.CompanySettings.retention_months",
        "daily_reminder": "core.CompanySettings.daily_reminder_at",
    },
}
