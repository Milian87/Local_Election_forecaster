SELECT 
    ew.wd_code,
    ew.ward_name,
    cc.council_name
FROM public.electoral_wards ew
LEFT JOIN public.county_codes cc 
    ON ew.cc_code = cc.cc_code
WHERE NOT EXISTS (
    SELECT 1
    FROM public.election_results er
    WHERE er.wd_code = ew.wd_code
)
ORDER BY cc.council_name, ew.ward_name;