-- chat_implementation_plan.md §5 / chat_spec.md §4.4's hard boundary: analytics-mcp's DB role gets
-- SELECT on the three summary tables ONLY (app/models/analytics.py) — never on orders, order_items,
-- users, or any other table. This is what actually enforces "no PII, ever," independent of anything
-- the model or the tool's Python code does. Run manually against the target MySQL instance (local
-- dev now; the managed host behind Railway's analytics-mcp service in production) — deliberately
-- NOT an Alembic migration, since a schema-migration downgrade should never imply revoking a DB
-- user's grants, and production grants happen against a host Alembic doesn't manage.
--
-- Usage: mysql -u root -p blackcart < scripts/provision_analytics_ro.sql
-- (edit the password below before running against anything but local dev)

CREATE USER IF NOT EXISTS 'analytics_ro'@'%' IDENTIFIED BY 'change-me-analytics-ro';

-- Revoke everything first so re-running this script after a table rename/drop can't leave a stale
-- grant behind.
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'analytics_ro'@'%';

GRANT SELECT ON blackcart.daily_sales_summary TO 'analytics_ro'@'%';
GRANT SELECT ON blackcart.product_velocity_summary TO 'analytics_ro'@'%';
GRANT SELECT ON blackcart.category_performance_summary TO 'analytics_ro'@'%';

FLUSH PRIVILEGES;
