-- MySQL dump 10.13  Distrib 8.0.44, for Win64 (x86_64)
--
-- Host: localhost    Database: irp_election_forecasting
-- ------------------------------------------------------
-- Server version	8.0.44

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `candidate_aliases`
--

DROP TABLE IF EXISTS `candidate_aliases`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `candidate_aliases` (
  `alias_id` int NOT NULL AUTO_INCREMENT,
  `candidate_id` int DEFAULT NULL,
  `alias_name` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`alias_id`),
  KEY `candidate_id` (`candidate_id`),
  CONSTRAINT `candidate_aliases_ibfk_1` FOREIGN KEY (`candidate_id`) REFERENCES `candidates` (`candidate_id`)
) ENGINE=InnoDB AUTO_INCREMENT=55 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `candidate_election_snapshots`
--

DROP TABLE IF EXISTS `candidate_election_snapshots`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `candidate_election_snapshots` (
  `candidate_id` int NOT NULL,
  `election_year` int NOT NULL,
  `total_prior_campaigns_contested` int DEFAULT '0',
  `total_prior_wins` int DEFAULT '0',
  `runs_in_current_cc_area` int DEFAULT '0',
  `is_high_profile_figure` tinyint(1) DEFAULT '0',
  PRIMARY KEY (`candidate_id`,`election_year`),
  CONSTRAINT `candidate_election_snapshots_ibfk_1` FOREIGN KEY (`candidate_id`) REFERENCES `candidates` (`candidate_id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `candidates`
--

DROP TABLE IF EXISTS `candidates`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `candidates` (
  `candidate_id` int NOT NULL AUTO_INCREMENT,
  `candidate_name` varchar(255) NOT NULL,
  `registered_party` varchar(255) NOT NULL,
  PRIMARY KEY (`candidate_id`)
) ENGINE=InnoDB AUTO_INCREMENT=15504 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `census`
--

DROP TABLE IF EXISTS `census`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `census` (
  `oa_code` varchar(9) NOT NULL COMMENT 'ONS 9-character Output Area (OA) code',
  `census_year` int NOT NULL,
  `pct_age_18_29` decimal(5,2) NOT NULL COMMENT 'Percentage of population aged 18-29',
  `pct_age_30_65` decimal(5,2) NOT NULL COMMENT 'Percentage of population aged 30-65',
  `pct_age_over_65` decimal(5,2) NOT NULL COMMENT 'Percentage of population aged over 65',
  `pct_male` decimal(5,2) NOT NULL COMMENT 'Percentage of population that is male',
  `pct_female` decimal(5,2) NOT NULL COMMENT 'Percentage of population that is female',
  `pct_student` decimal(5,2) NOT NULL COMMENT 'Percentage of population who are students',
  `pct_bch` decimal(5,2) NOT NULL COMMENT 'Percentage of population with a bachelor’s degree or higher',
  `pct_wk_class` decimal(5,2) NOT NULL COMMENT 'Percentage of population in Working Social Class',
  `pct_mid_class` decimal(5,2) NOT NULL COMMENT 'Percentage of population in Middle Social Class',
  `pct_own_hme` decimal(5,2) NOT NULL COMMENT 'Percentage of population who own their home',
  `pct_rent` decimal(5,2) NOT NULL COMMENT 'Percentage of population who rent their home',
  `pct_fb` decimal(5,2) NOT NULL COMMENT 'Percentage of foreign-born population',
  `pop_den` decimal(12,2) DEFAULT NULL,
  `oa_pop` int DEFAULT NULL,
  PRIMARY KEY (`oa_code`,`census_year`),
  KEY `idx_census_year` (`census_year`),
  KEY `idx_census_oa` (`oa_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `census_demographics`
--

DROP TABLE IF EXISTS `census_demographics`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `census_demographics` (
  `oa_code` varchar(12) NOT NULL,
  `census_year` smallint NOT NULL,
  `ward_pop` int NOT NULL,
  `pop_den` decimal(10,2) NOT NULL DEFAULT '0.00',
  `vote_shr` decimal(10,2) NOT NULL DEFAULT '0.00',
  `pct_age_18_29` decimal(10,2) NOT NULL DEFAULT '0.00',
  `pct_age_30_65` decimal(10,2) NOT NULL DEFAULT '0.00',
  `pct_age_over_65` decimal(10,2) NOT NULL DEFAULT '0.00',
  `pct_male` decimal(10,2) NOT NULL DEFAULT '0.00',
  `pct_female` decimal(10,2) NOT NULL DEFAULT '0.00',
  `pct_student` decimal(10,2) NOT NULL DEFAULT '0.00',
  `pct_bch` decimal(10,2) NOT NULL DEFAULT '0.00',
  `pct_wk_class` decimal(10,2) NOT NULL DEFAULT '0.00',
  `pct_mid_class` decimal(10,2) NOT NULL DEFAULT '0.00',
  `pct_own_hme` decimal(10,2) NOT NULL DEFAULT '0.00',
  `pct_rent` decimal(10,2) NOT NULL DEFAULT '0.00',
  `pct_fb` decimal(10,2) NOT NULL DEFAULT '0.00',
  PRIMARY KEY (`oa_code`,`census_year`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `census_pop`
--

DROP TABLE IF EXISTS `census_pop`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `census_pop` (
  `oa_code` varchar(20) NOT NULL,
  `census_year` int NOT NULL,
  `total_population` int NOT NULL,
  `area_sq_km` decimal(12,6) NOT NULL,
  PRIMARY KEY (`oa_code`,`census_year`),
  KEY `oa_code` (`oa_code`),
  KEY `census_year` (`census_year`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `county_codes`
--

DROP TABLE IF EXISTS `county_codes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `county_codes` (
  `cc_code` varchar(9) NOT NULL,
  `council_name` varchar(150) NOT NULL,
  PRIMARY KEY (`cc_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `election_results`
--

DROP TABLE IF EXISTS `election_results`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `election_results` (
  `wd_code` varchar(20) NOT NULL,
  `election_date` date NOT NULL,
  `candidate_id` int NOT NULL,
  `seats_available` int DEFAULT NULL,
  `is_uncontested` tinyint(1) DEFAULT NULL,
  `votes_received` int DEFAULT NULL,
  `vote_share` decimal(5,2) DEFAULT NULL,
  `election_year` int DEFAULT NULL,
  `is_elected` tinyint(1) DEFAULT NULL,
  `is_incumbent_cllr` tinyint(1) DEFAULT NULL,
  `national_poll_party_share` decimal(5,2) DEFAULT NULL,
  `prior_ward_closeness_margin` decimal(5,2) DEFAULT NULL,
  PRIMARY KEY (`wd_code`,`election_date`,`candidate_id`),
  KEY `candidate_id` (`candidate_id`),
  KEY `idx_election_results_wd` (`wd_code`),
  CONSTRAINT `election_results_ibfk_1` FOREIGN KEY (`candidate_id`) REFERENCES `candidates` (`candidate_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `electoral_wards`
--

DROP TABLE IF EXISTS `electoral_wards`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `electoral_wards` (
  `wd_code` varchar(20) NOT NULL,
  `ward_name` varchar(255) NOT NULL,
  `cc_code` varchar(20) DEFAULT NULL,
  `lad_code` varchar(20) DEFAULT NULL,
  PRIMARY KEY (`wd_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `electoral_wards_history`
--

DROP TABLE IF EXISTS `electoral_wards_history`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `electoral_wards_history` (
  `wd_code` varchar(20) NOT NULL,
  `election_year` int NOT NULL,
  `ward_name` varchar(255) NOT NULL,
  `cc_code` varchar(20) NOT NULL,
  PRIMARY KEY (`wd_code`,`election_year`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `geographic_lookup`
--

DROP TABLE IF EXISTS `geographic_lookup`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `geographic_lookup` (
  `wd_code` varchar(9) NOT NULL,
  `oa_code` varchar(9) NOT NULL,
  `lookup_version_year` int NOT NULL,
  PRIMARY KEY (`wd_code`,`oa_code`,`lookup_version_year`),
  KEY `idx_lookup_version` (`lookup_version_year`,`wd_code`),
  KEY `idx_geographic_lookup_wd` (`wd_code`),
  KEY `idx_geographic_lookup_oa` (`oa_code`),
  CONSTRAINT `geographic_lookup_ibfk_1` FOREIGN KEY (`wd_code`) REFERENCES `electoral_wards` (`wd_code`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping events for database 'irp_election_forecasting'
--

--
-- Dumping routines for database 'irp_election_forecasting'
--
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-08-25 11:44:30
