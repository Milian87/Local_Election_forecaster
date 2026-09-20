SELECT
    c.candidate_name AS "Name",
    c.registered_party AS "Party",
    er.election_date AS "Election Date",
    er.national_poll_party_share AS "Polls",
    -- DENSE_RANK counts the distinct dates remaining from the current row to the oldest row
    DENSE_RANK() OVER (ORDER BY er.election_date ASC) AS "Remaining Elections Countdown"
FROM election_results er
JOIN candidates c ON er.candidate_id = c.candidate_id
WHERE er.election_date < '2022-01-27'
ORDER BY er.election_date DESC;
