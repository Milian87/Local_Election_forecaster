UPDATE election_results er
SET national_poll_party_share = sub.new_poll_value
FROM (
    VALUES 
        -- 🔴 PUT YOUR NEW VALUES HERE (Party, 'YYYY-MM-DD', New Value)
        ('Green Party', '2016-05-05'::date, 4),
        ('Labour', '2016-05-05'::date, 31),
        ('Conservative', '2016-05-05'::date, 35),
        ('Liberal Democrats', '2016-05-05'::date, 9)
		--('Reform UK', '2018-12-06'::date, 6)
		--('Restore Britian', '2025-05-01'::date, 0),
		--('Great Yarmouth First', '2025-05-01'::date, 0)
        -- You can add as many rows here as you need, just separate them with commas
) AS sub(party_name, target_date, new_poll_value)
JOIN candidates c ON c.registered_party = sub.party_name
WHERE er.candidate_id = c.candidate_id
  AND er.election_date = sub.target_date;

