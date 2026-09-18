-- PostgreSQL schema, converted from schema.sql (MySQL dump of irp_election_forecasting)
-- Tables are ordered so referenced tables (candidates, electoral_wards) are created first.

BEGIN;

DROP TABLE IF EXISTS geographic_lookup CASCADE;
DROP TABLE IF EXISTS electoral_wards_history CASCADE;
DROP TABLE IF EXISTS election_results CASCADE;
DROP TABLE IF EXISTS electoral_wards CASCADE;
DROP TABLE IF EXISTS county_codes CASCADE;
DROP TABLE IF EXISTS census_pop CASCADE;
DROP TABLE IF EXISTS census_demographics CASCADE;
DROP TABLE IF EXISTS census CASCADE;
DROP TABLE IF EXISTS candidate_election_snapshots CASCADE;
DROP TABLE IF EXISTS candidate_aliases CASCADE;
DROP TABLE IF EXISTS candidates CASCADE;

-- candidates
CREATE TABLE candidates (
    candidate_id     SERIAL PRIMARY KEY,
    candidate_name   VARCHAR(255) NOT NULL,
    registered_party VARCHAR(255) NOT NULL
);

-- candidate_aliases (references candidates)
CREATE TABLE candidate_aliases (
    alias_id      SERIAL PRIMARY KEY,
    candidate_id  INTEGER,
    alias_name    VARCHAR(255),
    CONSTRAINT candidate_aliases_candidate_id_fkey
        FOREIGN KEY (candidate_id) REFERENCES candidates (candidate_id)
);
CREATE INDEX idx_candidate_aliases_candidate_id ON candidate_aliases (candidate_id);

-- candidate_election_snapshots (references candidates)
CREATE TABLE candidate_election_snapshots (
    candidate_id                     INTEGER NOT NULL,
    election_year                    INTEGER NOT NULL,
    total_prior_campaigns_contested  INTEGER DEFAULT 0,
    total_prior_wins                 INTEGER DEFAULT 0,
    runs_in_current_cc_area          INTEGER DEFAULT 0,
    is_high_profile_figure           BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (candidate_id, election_year),
    CONSTRAINT candidate_election_snapshots_candidate_id_fkey
        FOREIGN KEY (candidate_id) REFERENCES candidates (candidate_id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

-- census
CREATE TABLE census (
    oa_code          VARCHAR(9) NOT NULL,
    census_year      INTEGER NOT NULL,
    pct_age_18_29    NUMERIC(5,2) NOT NULL,
    pct_age_30_65    NUMERIC(5,2) NOT NULL,
    pct_age_over_65  NUMERIC(5,2) NOT NULL,
    pct_male         NUMERIC(5,2) NOT NULL,
    pct_female       NUMERIC(5,2) NOT NULL,
    pct_student      NUMERIC(5,2) NOT NULL,
    pct_bch          NUMERIC(5,2) NOT NULL,
    pct_wk_class     NUMERIC(5,2) NOT NULL,
    pct_mid_class    NUMERIC(5,2) NOT NULL,
    pct_own_hme      NUMERIC(5,2) NOT NULL,
    pct_rent         NUMERIC(5,2) NOT NULL,
    pct_fb           NUMERIC(5,2) NOT NULL,
    pop_den          NUMERIC(12,2),
    oa_pop           INTEGER,
    PRIMARY KEY (oa_code, census_year)
);
COMMENT ON COLUMN census.oa_code IS 'ONS 9-character Output Area (OA) code';
COMMENT ON COLUMN census.pct_age_18_29 IS 'Percentage of population aged 18-29';
COMMENT ON COLUMN census.pct_age_30_65 IS 'Percentage of population aged 30-65';
COMMENT ON COLUMN census.pct_age_over_65 IS 'Percentage of population aged over 65';
COMMENT ON COLUMN census.pct_male IS 'Percentage of population that is male';
COMMENT ON COLUMN census.pct_female IS 'Percentage of population that is female';
COMMENT ON COLUMN census.pct_student IS 'Percentage of population who are students';
COMMENT ON COLUMN census.pct_bch IS 'Percentage of population with a bachelor''s degree or higher';
COMMENT ON COLUMN census.pct_wk_class IS 'Percentage of population in Working Social Class';
COMMENT ON COLUMN census.pct_mid_class IS 'Percentage of population in Middle Social Class';
COMMENT ON COLUMN census.pct_own_hme IS 'Percentage of population who own their home';
COMMENT ON COLUMN census.pct_rent IS 'Percentage of population who rent their home';
COMMENT ON COLUMN census.pct_fb IS 'Percentage of foreign-born population';
CREATE INDEX idx_census_year ON census (census_year);
CREATE INDEX idx_census_oa ON census (oa_code);

-- census_demographics
CREATE TABLE census_demographics (
    oa_code          VARCHAR(12) NOT NULL,
    census_year      SMALLINT NOT NULL,
    ward_pop         INTEGER NOT NULL,
    pop_den          NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    vote_shr         NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    pct_age_18_29    NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    pct_age_30_65    NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    pct_age_over_65  NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    pct_male         NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    pct_female       NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    pct_student      NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    pct_bch          NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    pct_wk_class     NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    pct_mid_class    NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    pct_own_hme      NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    pct_rent         NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    pct_fb           NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    PRIMARY KEY (oa_code, census_year)
);

-- census_pop
CREATE TABLE census_pop (
    oa_code           VARCHAR(20) NOT NULL,
    census_year       INTEGER NOT NULL,
    total_population  INTEGER NOT NULL,
    area_sq_km        NUMERIC(12,6) NOT NULL,
    PRIMARY KEY (oa_code, census_year)
);
CREATE INDEX idx_census_pop_oa_code ON census_pop (oa_code);
CREATE INDEX idx_census_pop_census_year ON census_pop (census_year);

-- county_codes
CREATE TABLE county_codes (
    cc_code       VARCHAR(9) NOT NULL PRIMARY KEY,
    council_name  VARCHAR(150) NOT NULL
);

-- electoral_wards
CREATE TABLE electoral_wards (
    wd_code    VARCHAR(20) NOT NULL PRIMARY KEY,
    ward_name  VARCHAR(255) NOT NULL,
    cc_code    VARCHAR(20),
    lad_code   VARCHAR(20)
);

-- electoral_wards_history
CREATE TABLE electoral_wards_history (
    wd_code        VARCHAR(20) NOT NULL,
    election_year  INTEGER NOT NULL,
    ward_name      VARCHAR(255) NOT NULL,
    cc_code        VARCHAR(20) NOT NULL,
    PRIMARY KEY (wd_code, election_year)
);

-- election_results (references candidates)
CREATE TABLE election_results (
    wd_code                     VARCHAR(20) NOT NULL,
    election_date               DATE NOT NULL,
    candidate_id                INTEGER NOT NULL,
    seats_available             INTEGER,
    is_uncontested              BOOLEAN,
    votes_received              INTEGER,
    vote_share                  NUMERIC(5,2),
    election_year               INTEGER,
    is_elected                  BOOLEAN,
    is_incumbent_cllr           BOOLEAN,
    national_poll_party_share   NUMERIC(5,2),
    prior_ward_closeness_margin NUMERIC(5,2),
    PRIMARY KEY (wd_code, election_date, candidate_id),
    CONSTRAINT election_results_candidate_id_fkey
        FOREIGN KEY (candidate_id) REFERENCES candidates (candidate_id)
);
CREATE INDEX idx_election_results_candidate_id ON election_results (candidate_id);
CREATE INDEX idx_election_results_wd ON election_results (wd_code);

-- geographic_lookup: no FK to electoral_wards, source data references historical wd_codes
-- (only present in electoral_wards_history) for ~41% of rows (MySQL loaded this with checks off).
CREATE TABLE geographic_lookup (
    wd_code             VARCHAR(9) NOT NULL,
    oa_code             VARCHAR(9) NOT NULL,
    lookup_version_year INTEGER NOT NULL,
    PRIMARY KEY (wd_code, oa_code, lookup_version_year)
);
CREATE INDEX idx_lookup_version ON geographic_lookup (lookup_version_year, wd_code);
CREATE INDEX idx_geographic_lookup_wd ON geographic_lookup (wd_code);
CREATE INDEX idx_geographic_lookup_oa ON geographic_lookup (oa_code);

COMMIT;
