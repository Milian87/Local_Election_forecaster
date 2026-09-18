UPDATE election_results er
SET national_poll_party_share = sub.new_poll_value
FROM (
    VALUES 
        -- 🔴 PUT YOUR NEW VALUES HERE (Party, 'YYYY-MM-DD', New Value)
        ('Green Party', '2026-05-01'::date, 17),
        ('Labour', '2026-05-01'::date, 17),
        ('Conservative', '2026-05-01'::date, 17),
        ('Liberal Democrates', '2026-05-01'::date, 12),
		('Reform UK', '2026-05-01'::date, 25),
		('Restore Britian', '2026-05-01'::date, 3),
		('Great Yarmouth First', '2026-05-01'::date, 3)
        -- You can add as many rows here as you need, just separate them with commas
) AS sub(party_name, target_date, new_poll_value)
JOIN candidates c ON c.registered_party = sub.party_name
WHERE er.candidate_id = c.candidate_id
  AND er.election_date = sub.target_date;

