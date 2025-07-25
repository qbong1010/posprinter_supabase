-- SQLite 스키마
CREATE TABLE IF NOT EXISTS company (
  company_id INTEGER PRIMARY KEY AUTOINCREMENT,
  company_name TEXT NOT NULL,
  required_signature INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS menu_category (
  menu_category_id INTEGER PRIMARY KEY AUTOINCREMENT,
  category_name TEXT NOT NULL,
  indv_select_yn INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS menu_item (
  menu_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
  menu_name TEXT NOT NULL,
  menu_price INTEGER NOT NULL,
  menu_description TEXT,
  menu_category_id INTEGER NOT NULL,
  is_available INTEGER DEFAULT 1,
  menu_image_url TEXT,
  FOREIGN KEY (menu_category_id) REFERENCES menu_category(menu_category_id)
);

CREATE TABLE IF NOT EXISTS option_group (
  option_group_id INTEGER PRIMARY KEY AUTOINCREMENT,
  option_group_name TEXT NOT NULL,
  allow_multiple INTEGER DEFAULT 0,
  memo TEXT
);

CREATE TABLE IF NOT EXISTS menu_item_option_group (
  menu_item_id INTEGER NOT NULL,
  option_group_id INTEGER NOT NULL,
  is_required INTEGER DEFAULT 0,
  display_order INTEGER,
  PRIMARY KEY (menu_item_id, option_group_id),
  FOREIGN KEY (menu_item_id) REFERENCES menu_item(menu_item_id),
  FOREIGN KEY (option_group_id) REFERENCES option_group(option_group_id)
);

CREATE TABLE IF NOT EXISTS option_item (
  option_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
  option_item_name TEXT NOT NULL,
  option_price INTEGER DEFAULT 0,
  memo TEXT
);

CREATE TABLE IF NOT EXISTS option_group_item (
  option_group_id INTEGER NOT NULL,
  option_item_id INTEGER NOT NULL,
  PRIMARY KEY (option_group_id, option_item_id),
  FOREIGN KEY (option_group_id) REFERENCES option_group(option_group_id),
  FOREIGN KEY (option_item_id) REFERENCES option_item(option_item_id)
);

CREATE TABLE IF NOT EXISTS "order" (
  order_id INTEGER PRIMARY KEY AUTOINCREMENT,
  company_id INTEGER NOT NULL,
  is_dine_in INTEGER DEFAULT 1,
  total_price INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  is_printed INTEGER DEFAULT 0,
  signature_data TEXT,
  print_status VARCHAR(20) DEFAULT '신규',
  print_attempts INTEGER DEFAULT 0,
  last_print_attempt TIMESTAMP,
  is_approved INTEGER DEFAULT 0,
  approved_at TIMESTAMP,
  approved_by TEXT,
  FOREIGN KEY (company_id) REFERENCES company(company_id)
);

CREATE TABLE IF NOT EXISTS order_item (
  order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL,
  menu_item_id INTEGER NOT NULL,
  quantity INTEGER DEFAULT 1,
  item_price INTEGER NOT NULL,
  FOREIGN KEY (order_id) REFERENCES "order"(order_id),
  FOREIGN KEY (menu_item_id) REFERENCES menu_item(menu_item_id)
);

CREATE TABLE IF NOT EXISTS order_item_option (
  order_item_option_id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_item_id INTEGER NOT NULL,
  option_item_id INTEGER NOT NULL,
  quantity INTEGER DEFAULT 1,
  total_price INTEGER DEFAULT 0,
  FOREIGN KEY (order_item_id) REFERENCES order_item(order_item_id),
  FOREIGN KEY (option_item_id) REFERENCES option_item(option_item_id)
);

CREATE TABLE IF NOT EXISTS cache_meta (
  key TEXT PRIMARY KEY,
  value TEXT
); 