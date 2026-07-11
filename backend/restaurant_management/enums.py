from django.db import models


class TableStatus(models.TextChoices):
    AVAILABLE = "available", "Available"
    OCCUPIED = "occupied", "Occupied"
    RESERVED = "reserved", "Reserved"
    CLEANING = "cleaning", "Cleaning"
    MAINTENANCE = "maintenance", "Maintenance"


class TableShape(models.TextChoices):
    ROUND = "round", "Round"
    SQUARE = "square", "Square"
    RECTANGULAR = "rectangular", "Rectangular"
    BOOTH = "booth", "Booth"
    OVAL = "oval", "Oval"


class ReservationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    CONFIRMED = "confirmed", "Confirmed"
    SEATED = "seated", "Seated"
    CANCELLED = "cancelled", "Cancelled"
    NO_SHOW = "no_show", "No Show"
    COMPLETED = "completed", "Completed"


class OrderStatus(models.TextChoices):
    NEW = "new", "New"
    IN_PROGRESS = "in_progress", "In Progress"
    READY = "ready", "Ready"
    SERVED = "served", "Served"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class OrderItemStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PREPARING = "preparing", "Sent"
    READY = "ready", "Ready"
    SERVED = "served", "Served"
    CANCELLED = "cancelled", "Cancelled"


class OrderType(models.TextChoices):
    DINE_IN = "dine_in", "Dine In"
    TAKEOUT = "takeout", "Takeout"
    DELIVERY = "delivery", "Delivery"


class CourseType(models.TextChoices):
    STRAIGHT_FIRE = "straight_fire", "Straight Fire"
    STARTER = "starter", "Starter"
    MAIN = "main", "Main"
    DESSERT = "dessert", "Dessert"


class FireState(models.TextChoices):
    HOLD = "hold", "Hold"
    FIRE = "fire", "Fire"


class PosActionType(models.TextChoices):
    OPEN_TABLE = "open_table", "Open Table"
    FIRE_ITEMS = "fire_items", "Fire Items"
    START_PREPARING = "start_preparing", "Start Preparing"
    REPEAT_ITEM = "repeat_item", "Repeat Item"
    DELETE_OR_CANCEL_ITEM = "delete_or_cancel_item", "Delete/Cancel Item"
    SPLIT_CHECK = "split_check", "Split Check"
    MOVE_ITEMS = "move_items", "Move Items"
    VOID_CHECK = "void_check", "Void Check"
    COMP_CHECK = "comp_check", "Comp Check"
    CLEAR_NEW_ITEMS = "clear_new_items", "Clear New Items"



