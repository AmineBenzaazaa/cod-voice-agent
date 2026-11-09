-- Demo data only: fictional customers, phone numbers in the reserved 0600-0000xx range.
TRUNCATE call_events, orders;

INSERT INTO orders (id, customer_name, phone, city, address, items, total_mad) VALUES
('CMD-1042', 'Yassine El Amrani', '+212600000101', 'Casablanca', '27 Rue Ibn Battouta, Maarif',
 '[{"name": "Wireless earbuds", "qty": 1, "price_mad": 249}]', 249),
('CMD-1043', 'Salma Bennani', '+212600000102', 'Rabat', 'Avenue Fal Ould Oumeir, Agdal, apt 4',
 '[{"name": "Running shoes, size 39", "qty": 1, "price_mad": 399}, {"name": "Sport socks", "qty": 2, "price_mad": 35}]', 469),
('CMD-1044', 'Omar Tazi', '+212600000103', 'Marrakech', 'Lot Massira 1, villa 112',
 '[{"name": "Argan oil gift set", "qty": 2, "price_mad": 180}]', 360),
('CMD-1045', 'Nadia Chraibi', '+212600000104', 'Tangier', 'Boulevard Mohammed V, residence Nour, 3rd floor',
 '[{"name": "Phone case", "qty": 1, "price_mad": 89}, {"name": "Screen protector", "qty": 1, "price_mad": 49}]', 138),
('CMD-1046', 'Karim Idrissi', '+212600000105', 'Fes', 'Route Imouzzer, Hay Narjiss, n 58',
 '[{"name": "Smartwatch", "qty": 1, "price_mad": 599}]', 599);
