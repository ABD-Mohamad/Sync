# apps/notifications/signals.py
# Signals for the notifications app are registered via apps/tasks/signals.py
# This file is intentionally left minimal — it exists only to allow
# AppConfig.ready() to import without error.