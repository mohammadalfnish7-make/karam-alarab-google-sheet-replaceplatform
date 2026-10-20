SEA_STAGES = [
    "📦 WH",
    "STAGE 1",
    "STAGE 2",
    "STAGE 3",
    "STAGE 4",
    "STAGE 6",
    "LOADING",
    "OFF LOADING",
    "WAITING",
    "delivered to customer✅",
]

DEFAULT_SEA_STAGE = "📦 WH"

AIR_STATUSES = [
    "AT AIRPORT",
    "delivered to customer✅",
]

EXIT_STATUSES = [
    "DONE",
    "Submitted",
    "Pending",
    "received docs",
    "CANCELED",
    "NIL",
]

SHIPPING_ROUTES = ["IRAN", "TURKEY"]

# Cont Tracker undocumented stage column (Russian "этап" = stage).
CONTAINER_STAGES = [
    "этап 1",
    "этап 2",
    "этап 3",
    "этап 4",
    "этап 5",
    "этап 6",
]

ENTITY_TYPES = {
    "sea": "sea_cargo",
    "air": "air_cargo",
    "exit": "exit_record",
}
