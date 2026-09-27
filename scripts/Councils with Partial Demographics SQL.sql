SELECT 
    cc.cc_code,
    cc.council_name,
    COUNT(DISTINCT ew.wd_code) AS total_wards,
    COUNT(DISTINCT CASE WHEN c.oa_code IS NOT NULL THEN ew.wd_code END) AS wards_with_data,
    COUNT(DISTINCT ew.wd_code) - COUNT(DISTINCT CASE WHEN c.oa_code IS NOT NULL THEN ew.wd_code END) AS wards_missing_data
FROM public.county_codes cc
LEFT JOIN public.electoral_wards ew 
    ON cc.cc_code = ew.cc_code
LEFT JOIN public.geographic_lookup gl 
    ON ew.wd_code = gl.wd_code
LEFT JOIN public.census c 
    ON gl.oa_code = c.oa_code
GROUP BY cc.cc_code, cc.council_name
HAVING COUNT(c.oa_code) = 0  -- Change to: HAVING COUNT(DISTINCT CASE WHEN c.oa_code IS NOT NULL THEN ew.wd_code END) < COUNT(DISTINCT ew.wd_code) to include partials
ORDER BY cc.council_name;