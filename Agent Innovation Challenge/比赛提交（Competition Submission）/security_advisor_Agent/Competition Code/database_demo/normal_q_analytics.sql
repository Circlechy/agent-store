SELECT event_type, COUNT(*)
FROM public.usage_events
WHERE event_time >= now() - interval '7 days'
GROUP BY event_type;

-- 2
SELECT date_trunc('day', event_time) AS day, COUNT(*)
FROM public.usage_events
WHERE event_time >= now() - interval '30 days'
GROUP BY day
ORDER BY day;

-- 3
SELECT event_type, COUNT(DISTINCT customer_id)
FROM public.usage_events
WHERE event_time >= now() - interval '14 days'
GROUP BY event_type;

-- 4
SELECT COUNT(DISTINCT customer_id)
FROM public.usage_events
WHERE event_time >= now() - interval '1 day';

-- 5
SELECT date_trunc('week', event_time) AS week, COUNT(*)
FROM public.usage_events
WHERE event_time >= now() - interval '90 days'
GROUP BY week;

-- 6
SELECT customer_id, COUNT(*) AS events
FROM public.usage_events
WHERE event_time >= now() - interval '1 day'
GROUP BY customer_id
ORDER BY events DESC
LIMIT 50;

-- 7
SELECT event_type, COUNT(*)
FROM public.usage_events
WHERE customer_id = '11111111-1111-1111-1111-111111111111'
GROUP BY event_type;

-- 8
SELECT date_trunc('hour', event_time), COUNT(*)
FROM public.usage_events
WHERE event_time >= now() - interval '48 hours'
GROUP BY 1
ORDER BY 1;

-- 9
SELECT event_type,
       COUNT(*) FILTER (WHERE event_time >= now() - interval '7 days') AS last_7d
FROM public.usage_events
GROUP BY event_type;

-- 10
SELECT customer_id, MIN(event_time), MAX(event_time)
FROM public.usage_events
GROUP BY customer_id
LIMIT 100;

-- 11
SELECT COUNT(*)
FROM public.usage_events
WHERE event_type = 'login'
  AND event_time >= '2026-01-01'
  AND event_time <  '2026-01-08';

-- 12
SELECT date_trunc('day', event_time), COUNT(DISTINCT customer_id)
FROM public.usage_events
WHERE event_time >= now() - interval '30 days'
GROUP BY 1;

-- 13
SELECT customer_id
FROM public.usage_events
WHERE event_time >= now() - interval '7 days'
GROUP BY customer_id
HAVING COUNT(*) > 10;

-- 14
SELECT event_type, COUNT(*)
FROM public.usage_events
GROUP BY event_type
ORDER BY COUNT(*) DESC;

-- 15
SELECT COUNT(*)
FROM public.usage_events
WHERE event_time >= now() - interval '1 hour';

-- 16
SELECT date_trunc('month', event_time), COUNT(*)
FROM public.usage_events
GROUP BY 1;

-- 17
SELECT customer_id, COUNT(*)
FROM public.usage_events
WHERE event_type = 'purchase'
GROUP BY customer_id;

-- 18
SELECT *
FROM public.usage_events
ORDER BY event_time DESC
LIMIT 100;

-- 19
SELECT COUNT(*)
FROM public.usage_events
WHERE event_type IN ('login', 'logout');

-- 20
SELECT event_type, COUNT(*)
FROM public.usage_events
WHERE event_time BETWEEN '2026-01-01' AND '2026-01-31'
GROUP BY event_type;