SELECT 
    ew.wd_code,
    ew.ward_name,
    cc.council_name,
    CASE 
        WHEN COUNT(c.oa_code) > 0 THEN 'Has Demographics'
        ELSE 'Missing Demographics'
    END AS data_status,
    COUNT(DISTINCT gl.oa_code) AS matched_output_areas
FROM public.electoral_wards ew
LEFT JOIN public.county_codes cc 
    ON ew.cc_code = cc.cc_code
LEFT JOIN public.geographic_lookup gl 
    ON ew.wd_code = gl.wd_code
LEFT JOIN public.census c 
    ON gl.oa_code = c.oa_code
GROUP BY ew.wd_code, ew.ward_name, cc.council_name
ORDER BY data_status DESC, cc.council_name, ew.ward_name;