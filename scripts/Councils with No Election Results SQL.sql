SELECT 
    cc.cc_code,
    cc.council_name
FROM public.county_codes cc
WHERE NOT EXISTS (
    SELECT 1
    FROM public.electoral_wards ew
    JOIN public.election_results er 
      ON ew.wd_code = er.wd_code
    WHERE ew.cc_code = cc.cc_code
)
ORDER BY cc.council_name;