/**
 * Page IDs matching the seed data in backend/pages/seed.py.
 * These are assigned sequentially by Django's AutoField.
 * Run `python manage.py seed_pages` to populate, then confirm IDs from admin.
 */
export const PAGE_IDS = {
  ITEMS: 1,
  CUSTOMERS: 2,
  VENDORS: 3,
} as const
