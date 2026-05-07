USE moodmeal;

INSERT IGNORE INTO food_categories (id, name, parent_id) VALUES
(1,  'breakfast',  NULL),
(2,  'lunch',      NULL),
(3,  'dinner',     NULL),
(4,  'snack',      NULL),
(5,  'dessert',    NULL),
(6,  'beverage',   NULL),
(7,  'side_dish',  NULL),
(8,  'main_dish',  3),
(9,  'soup',       NULL),
(10, 'salad',      NULL);
