CREATE TABLE `timetable` (
  `Destination-Airport` varchar(255) DEFAULT NULL,
  `Scheduled-Arrival-Time` varchar(255) DEFAULT NULL,
  `Cost/Fare` varchar(255) DEFAULT NULL,
  `Taxi-Time` varchar(255) DEFAULT NULL,
  `Runway-Time` varchar(255) DEFAULT NULL,
  `Ascent/Descent` varchar(255) DEFAULT NULL,
  `Cruising-Speed` varchar(255) DEFAULT NULL,
  `Heading` varchar(255) DEFAULT NULL,
  `Turnaround-Time` varchar(255) DEFAULT NULL
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_uca1400_ai_ci