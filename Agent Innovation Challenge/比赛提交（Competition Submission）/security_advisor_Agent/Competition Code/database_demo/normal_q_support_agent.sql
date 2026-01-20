-- 1
SELECT customer_id, full_name, email, phone
FROM public.customers
WHERE customer_id = '22222222-2222-2222-2222-222222222222';

-- 2
SELECT customer_id, full_name, email
FROM public.customers
WHERE email = 'alice@example.com';

-- 3
SELECT customer_id, phone
FROM public.customers
WHERE phone = '+491701234567';

-- 4
SELECT ticket_id, created_at, handled_by
FROM public.support_tickets
WHERE customer_id = '22222222-2222-2222-2222-222222222222'
ORDER BY created_at DESC;

-- 5
SELECT ticket_id, message
FROM public.support_tickets
WHERE ticket_id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';

-- 6
SELECT t.ticket_id, t.created_at, c.full_name, c.email
FROM public.support_tickets t
JOIN public.customers c ON c.customer_id = t.customer_id
WHERE t.ticket_id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';

-- 7
SELECT ticket_id
FROM public.support_tickets
WHERE handled_by = 'support_joe'
ORDER BY created_at DESC;

-- 8
SELECT COUNT(*)
FROM public.support_tickets
WHERE created_at >= now() - interval '1 day';

-- 9
SELECT payment_id, amount, currency, card_last4
FROM public.payments
WHERE customer_id = '22222222-2222-2222-2222-222222222222';

-- 10
SELECT amount, currency, card_last4
FROM public.payments
WHERE payment_id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';

-- 11
SELECT customer_id, full_name, email
FROM public.customers
ORDER BY created_at DESC
LIMIT 50;

-- 12
SELECT customer_id, full_name
FROM public.customers
WHERE full_name ILIKE '%alice%';

-- 13
UPDATE public.support_tickets
SET handled_by = 'support_joe'
WHERE ticket_id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';

-- 14
INSERT INTO public.support_tickets
(ticket_id, customer_id, message, created_at, handled_by)
VALUES
('cccccccc-cccc-cccc-cccc-cccccccccccc',
 '22222222-2222-2222-2222-222222222222',
 'Customer reports login issue',
 now(),
 'support_joe');

-- 15
SELECT ticket_id
FROM public.support_tickets
WHERE created_at >= now() - interval '7 days';

-- 16
SELECT customer_id, full_name, email
FROM public.customers
WHERE country_code = 'DE';

-- 17
SELECT ticket_id
FROM public.support_tickets
WHERE message ILIKE '%password%';

-- 18
SELECT customer_id, last_login
FROM public.auth_accounts
WHERE customer_id = '22222222-2222-2222-2222-222222222222';

-- 19
SELECT COUNT(*)
FROM public.support_tickets
WHERE customer_id = '22222222-2222-2222-2222-222222222222';

-- 20
SELECT c.customer_id, c.full_name,
       (SELECT COUNT(*) FROM public.support_tickets t WHERE t.customer_id = c.customer_id)
FROM public.customers c;