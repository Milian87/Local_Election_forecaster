SELECT 
    cc.cc_code,
    cc.council_name
FROM public.county_codes cc
WHERE NOT EXISTS (
    SELECT 1
    FROM public.electoral_wards ew
    JOIN public.geographic_lookup gl 
      ON ew.wd_code = gl.wd_code
    JOIN public.census c 
      ON gl.oa_code = c.oa_code
    WHERE ew.cc_code = cc.cc_code
)
ORDER BY cc.council_name;